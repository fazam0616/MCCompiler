"""MCL Assembly Generator

Generates assembly code from AST nodes.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, List, Dict, Optional, Union
from enum import Enum
from .ast_nodes import *
from .symbol_table import SymbolTable, Symbol, SymbolKind, StorageLocation


class InstructionType(Enum):
    # Data movement
    LOAD = "LOAD"  # LOAD A, B - Load data at register A into RAM address B
    READ = "READ"  # READ A, B - Load data at RAM address A into register B
    MVR = "MVR"    # MVR A, B - Copy register A to register B
    MVM = "MVM"    # MVM A, B - Copy RAM address A to RAM address B
    
    # Input/Output
    KEYIN = "KEYIN" # KEYIN A - Load system input into address A
    
    # Arithmetic
    ADD = "ADD"
    SUB = "SUB"
    MULT = "MULT"
    DIV = "DIV"
    SHL = "SHL"    # Shift left
    SHR = "SHR"    # Shift right
    SHLR = "SHLR"  # Shift left rotate?
    
    # Bitwise operations
    AND = "AND"    # Bitwise AND
    OR = "OR"      # Bitwise OR
    XOR = "XOR"    # Bitwise XOR
    NOT = "NOT"    # Bitwise NOT
    
    # Control flow
    JMP = "JMP"    # Unconditional jump
    JAL = "JAL"    # Jump and link
    JBT = "JBT"    # Jump if greater than
    JZ = "JZ"      # Jump if zero
    JNZ = "JNZ"    # Jump if not zero
    HALT = "HALT"  # Halt execution
    
    # GPU commands
    DRLINE = "DRLINE"
    DRGRD = "DRGRD"
    CLRGRID = "CLRGRID"
    LDSPR = "LDSPR"
    DRSPR = "DRSPR"
    LDTXT = "LDTXT"
    DRTXT = "DRTXT"
    SCRLBFR = "SCRLBFR"


@dataclass
class Operand:
    """Assembly instruction operand."""
    value: Union[int, str]  # Register number, address, or label
    is_immediate: bool = False  # True if prefixed with 'i:'
    
    def __str__(self) -> str:
        if self.is_immediate:
            return f"i:{self.value}"
        return str(self.value)


@dataclass
class Instruction:
    """Assembly instruction."""
    opcode: InstructionType
    operands: List[Operand]
    comment: Optional[str] = None
    label: Optional[str] = None
    
    def __str__(self) -> str:
        result = ""
        if self.label:
            result += f"{self.label}:"

        if self.opcode:
            if self.label and self.opcode:
                result += " "
            result += self.opcode.value
            if self.operands:
                result += " " + ", ".join(str(op) for op in self.operands)

        if self.comment:
            # Special-case raw assembly emission: comment starts with RAW_ASM:
            if isinstance(self.comment, str) and self.comment.startswith('RAW_ASM:'):
                # Emit the raw assembly line after the marker
                raw = self.comment[len('RAW_ASM:'):]
                # If nothing else on the line, return raw as-is
                if not self.opcode and not self.label:
                    return raw
                # If it's a label-only raw line and label matches, emit label only
                if self.label and raw == f"{self.label}:":
                    return f"{self.label}:"
                # Otherwise append as comment
                result += f"  // {raw}"
            else:
                result += f"  // {self.comment}"
        
        return result


class AssemblyGenerator(ASTVisitor):
    """Generates assembly code from AST."""
    
    # Memory region constants
    STATIC_START = 0x1000    # Static data starts at 4KB
    HEAP_START = 0x1800      # Heap starts at 6KB (2KB for static)
    STACK_BASE = 0x7000      # Stack starts at 28KB
    STACK_TOP = 0x7FFF       # Stack ends at 32KB-1 (grows downward)
    STACK_POINTER_REG = 3    # R3 is the stack pointer (R0,R1 for ALU, R2 for return addr)
    FRAME_POINTER_REG = 4    # R4 is the frame pointer (FP)
    EPILOGUE_SAVE_REG = 5    # R5 is used during epilogue to preserve return value across pop ops

    # Binary operator → instruction type mapping (class-level constant, built once).
    # AND/OR/XOR appear twice intentionally: the keyword forms (AND, OR, XOR) and the
    # symbol forms (BITWISE_AND, BITWISE_OR, BITWISE_XOR) both map to the same opcode.
    _BINARY_OP_MAP: Dict = {}   # populated in __init_subclass__ / filled below class body

    # GPU function name → instruction type mapping (class-level constant, built once).
    _GPU_FUNC_MAP: Dict = {}    # populated below class body
    
    def __init__(self, ram_start: int = 0x1000, ram_size: int = 0x1000):
        self.instructions: List[Instruction] = []
        self.symbol_table = SymbolTable(ram_start, ram_size)
        self.label_counter = 0
        self.current_function = None
        self.break_labels: List[str] = []
        self.continue_labels: List[str] = []
        self.has_recursion_warning = False  # Track if we've warned about recursion
        self.current_local_frame_depth = 0  # Tracks cumulative stack frame depth for local vars

        self.symbol_table.register_allocator.set_emit_callback(self.emit)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def _safe_free(self, reg: Optional[int]) -> None:
        """Free *reg* only if it is not None and not a reserved register."""
        if reg is None:
            return
        ra = self.symbol_table.register_allocator
        if reg not in ra.RESERVED_REGISTERS:
            ra.free_temporary_register(reg)

    def _emit_sp_decrement(self, n: int = 1, comment: str = None) -> None:
        """Emit the 3-instruction sequence that decrements SP by *n*.
        SUB SP, i:n  →  MVR 0, R1  →  MVR R1, SP
        """
        self.emit(InstructionType.SUB, self.STACK_POINTER_REG, Operand(n, True),
                 comment=comment or f"Decrement SP by {n}")
        self.emit(InstructionType.MVR, 0, 1, comment="R1 = new SP")
        self.emit(InstructionType.MVR, 1, self.STACK_POINTER_REG, comment="SP = R1")

    def _emit_sp_increment(self, n: int = 1, comment: str = None) -> None:
        """Emit the 3-instruction sequence that increments SP by *n*.
        ADD SP, i:n  →  MVR 0, R1  →  MVR R1, SP
        """
        self.emit(InstructionType.ADD, self.STACK_POINTER_REG, Operand(n, True),
                 comment=comment or f"Increment SP by {n}")
        self.emit(InstructionType.MVR, 0, 1, comment="R1 = new SP")
        self.emit(InstructionType.MVR, 1, self.STACK_POINTER_REG, comment="SP = R1")

    @contextmanager
    def _expression_scope(self):
        """Context manager that brackets enter/exit_expression_scope."""
        self.symbol_table.enter_expression_scope()
        try:
            yield
        finally:
            self.symbol_table.exit_expression_scope()

    def _rescue_r0(self, reg: int, comment: str = "Save R0 to temp") -> int:
        """If *reg* is R0 (ALU output), copy it into a fresh temp and return
        that temp.  Otherwise return *reg* unchanged.
        Use this wherever the next operation might clobber R0 before the value
        stored there has been consumed.
        """
        if reg != 0:
            return reg
        ra = self.symbol_table.register_allocator
        temp = ra.save_alu_result(pin_live=False)
        return temp

    def _emit_array_address(self, base: Union[int, str], index_reg: int,
                             comment: str = None, base_is_reg: bool = False) -> int:
        """Emit code to compute *base* + *index_reg* into a fresh temp register.
        *base* is either:
          - an ``int`` immediate RAM address (when ``base_is_reg=False``, the default), or
          - a register number already holding the base pointer (when ``base_is_reg=True``).

        Returns the temp register that holds the computed address (R0 also
        holds it immediately after the ADD).
        """
        ra = self.symbol_table.register_allocator
        # Allocate the address register while protecting the index register so
        # the spiller cannot evict it during the allocation.
        addr_reg = ra.allocate_protected(index_reg) if index_reg not in ra.RESERVED_REGISTERS \
            else self.symbol_table.allocate_temporary()
        if not base_is_reg:
            # base is an immediate RAM address
            self.emit_immediate(InstructionType.MVR, base, addr_reg,
                               comment=comment or "Base address")
            self.emit(InstructionType.ADD, addr_reg, index_reg,
                     comment="Add index to base")
        else:
            # base is already in a register — ADD writes result to R0.
            self.emit(InstructionType.ADD, base, index_reg,
                     comment=comment or "Add index to base")
        self.emit(InstructionType.MVR, 0, addr_reg, comment="Save array address to temp")
        return addr_reg

    def generate_label(self, prefix: str = "L") -> str:
        """Generate a unique label."""
        label = f"{prefix}{self.label_counter}"
        self.label_counter += 1
        return label
    
    def emit_label(self, label: str) -> None:
        """Emit a label (as a no-op instruction with label)."""
        self.emit(None, comment=f"Label: {label}", label=label)
    
    def emit(self, opcode, *operands, comment: str = None, label: str = None) -> None:
        """Emit an assembly instruction."""
        # Allow callers (e.g. spill/reload callbacks) to pass opcode as a string name
        if isinstance(opcode, str):
            opcode = InstructionType(opcode)
        ops = []
        for op in operands:
            if isinstance(op, int):
                ops.append(Operand(op))
            elif isinstance(op, str):
                ops.append(Operand(op))
            elif isinstance(op, Operand):
                ops.append(op)
            else:
                ops.append(Operand(str(op)))
        
        instruction = Instruction(opcode, ops, comment, label)
        self.instructions.append(instruction)
    
    def emit_immediate(self, opcode: InstructionType, immediate_value, dest_register, comment: str = None) -> None:
        """Emit instruction with immediate value as source and register as destination."""
        ops = [
            Operand(immediate_value, True),  # First operand is immediate (source)
            Operand(dest_register)           # Second operand is register (destination)
        ]
        
        instruction = Instruction(opcode, ops, comment)
        self.instructions.append(instruction)
    
    def _emit_push(self, source_reg: int, comment: str = None) -> None:
        """Push a register value onto the stack.

        Special case for source_reg == 0 (R0 / ALU result register):
        ``SUB SP, 1`` writes SP-1 back into R0, clobbering the value we
        want to push before ``LOAD 0, SP`` can save it.  We therefore save
        R0 into R1 first, use ``MVR 0, SP`` to fold the SP update into one
        instruction (avoiding the extra R1 round-trip), then store from R1.
        """
        if source_reg == 0:
            # Save R0 before SUB clobbers it, then update SP via R0 directly.
            self.emit(InstructionType.MVR, 0, 1,
                     comment="Preserve R0 before SP decrement")
            self.emit(InstructionType.SUB, self.STACK_POINTER_REG, Operand(1, True),
                     comment="Decrement SP")
            self.emit(InstructionType.MVR, 0, self.STACK_POINTER_REG,
                     comment="Update SP from R0")
            self.emit(InstructionType.LOAD, 1, self.STACK_POINTER_REG,
                     comment=comment or "Push R0 (via R1) to stack")
        else:
            # General case: R0 is not the source, safe to use as scratch.
            self._emit_sp_decrement(comment="Decrement SP")
            self.emit(InstructionType.LOAD, source_reg, self.STACK_POINTER_REG,
                     comment=comment or "Push to stack")
    
    def _emit_pop(self, dest_reg: int, comment: str = None) -> None:
        """Pop a value from the stack into a register."""
        # Load value from current stack pointer
        self.emit(InstructionType.READ, self.STACK_POINTER_REG, dest_reg,
                 comment=comment or "Pop from stack")
        # Increment stack pointer: SP + 1 -> R1 (temp), then R1 -> SP
        # Use R1 as temp to avoid clobbering R0 (return value register)
        self._emit_sp_increment(comment="Increment SP")
    
    def _emit_fp_address(self, frame_offset: int, comment: str = None) -> int:
        """Compute FP + frame_offset into a fresh temporary register and return that register.
        
        After this, R0 holds the computed address (and so does the returned temp reg).
        Uses ADD for non-negative offsets, SUB for negative offsets.
        """
        addr_reg = self.symbol_table.allocate_temporary()
        if frame_offset >= 0:
            self.emit(InstructionType.ADD, self.FRAME_POINTER_REG, Operand(frame_offset, True),
                     comment=comment or f"Compute FP+{frame_offset}")
        else:
            self.emit(InstructionType.SUB, self.FRAME_POINTER_REG, Operand(-frame_offset, True),
                     comment=comment or f"Compute FP-{-frame_offset}")
        # R0 now has the address; save it to addr_reg (MVR does not clobber R0)
        self.emit(InstructionType.MVR, 0, addr_reg, comment="Save address to temp")
        return addr_reg

    def _emit_fp_load(self, frame_offset: int, comment: str = None) -> int:
        """Load the value at FP+frame_offset into a new temporary register and return it.

        Free addr_reg BEFORE allocating dest_reg to prevent a subtle aliasing bug:
        if addr_reg was spilled during _emit_fp_address, its physical register slot
        is reclaimed; dest_reg would then be allocated to that same slot, and the
        subsequent free_temporary_register(addr_reg_slot) would incorrectly evict
        dest_reg — leaving the caller with a dangling register number.
        """
        addr_reg = self._emit_fp_address(frame_offset)
        self.symbol_table.register_allocator.free_temporary_register(addr_reg)
        dest_reg = self.symbol_table.allocate_temporary()
        # R0 still holds the FP-relative address (set by _emit_fp_address via MVR 0, addr_reg).
        # Copy it into dest_reg first so READ has a stable source address register.
        self.emit(InstructionType.MVR, 0, dest_reg,
                 comment="Copy address from R0 into dest (addr_reg freed)")
        self.emit(InstructionType.READ, dest_reg, dest_reg,
                 comment=comment or f"Load from FP{frame_offset:+d}")
        return dest_reg

    def _emit_fp_store(self, value_reg: int, frame_offset: int, comment: str = None) -> int:
        """Store value_reg to FP+frame_offset.  Returns a register holding the stored value.

        Two safety concerns handled here:
          1. If value_reg == 0 (R0), ADD/SUB will clobber it before the LOAD.
          2. If value_reg was freed by a parent expression scope, _emit_fp_address
             might reallocate that exact same register for the address calculation,
             silently overwriting the value we intend to store.

        To handle both: always copy the value into a fresh, definitely-allocated
        temporary before computing the address.
        """
        # Allocate a fresh temp and copy the value into it.
        # Two safety layers:
        #   1. _spill_lru_and_allocate now refuses to evict registers in
        #      `temporary_registers`, so save_reg cannot be evicted when
        #      _emit_fp_address calls allocate_temporary().
        #   2. We still mark save_reg live as an explicit belt-and-suspenders
        #      guard so future changes to the spiller cannot regress this.
        save_reg = self.symbol_table.allocate_temporary()
        self.emit(InstructionType.MVR, value_reg, save_reg,
                 comment="Copy store-value to temp (prevent register aliasing)")

        # Explicit live-pin: ensures save_reg is unreachable by the spiller
        # even if the spill logic is later loosened for unrelated reasons.
        ra = self.symbol_table.register_allocator
        ra.mark_register_live(save_reg)

        addr_reg = self._emit_fp_address(frame_offset)

        ra.mark_register_consumed(save_reg)

        self.emit(InstructionType.LOAD, save_reg, addr_reg,
                 comment=comment or f"Store to FP+({frame_offset})")
        ra.free_temporary_register(addr_reg)

        # save_reg holds the stored value; caller can use it as the result.
        return save_reg

    def _emit_function_epilogue(self) -> None:
        """Emit the standard function epilogue:
            1. Save return value (R0) to EPILOGUE_SAVE_REG (R5)
            2. Restore SP = FP  (deallocates all locals)
            3. Pop old FP  (restores caller's frame pointer)
            4. Pop return address into R2
            5. Restore return value from R5 to R0
            6. JMP R2
        R5 is not touched by _emit_pop (which uses R0 and R1), so it is safe.
        """
        # Preserve return value across the pop operations that clobber R0/R1
        self.emit(InstructionType.MVR, 0, self.EPILOGUE_SAVE_REG,
                 comment="Preserve return value in R5 before epilogue")
        # Restore SP to FP (removes all local variables from stack frame)
        self.emit(InstructionType.MVR, self.FRAME_POINTER_REG, self.STACK_POINTER_REG,
                 comment="Restore SP to FP (deallocate locals)")
        # Restore old frame pointer
        self._emit_pop(self.FRAME_POINTER_REG, comment="Restore caller's FP")
        # Restore return address
        self._emit_pop(2, comment="Restore return address into R2")
        # Restore return value
        self.emit(InstructionType.MVR, self.EPILOGUE_SAVE_REG, 0,
                 comment="Restore return value to R0")
        # Return to caller
        self.emit(InstructionType.JMP, 2, comment="Return to caller")

    def _check_static_bounds(self, size: int, var_name: str) -> bool:
        """Check if static allocation fits in static region."""
        current_static_pos = self.symbol_table.next_global_address
        static_end = self.HEAP_START
        available = static_end - current_static_pos
        
        if current_static_pos + size > static_end:
            raise CodeGenerationError(
                f"Static memory overflow: Variable '{var_name}' requires {size} bytes, "
                f"but only {available} bytes available in static region "
                f"(0x{self.STATIC_START:04X} - 0x{static_end:04X})"
            )
        return True
    
    def _check_heap_bounds(self, size: int) -> bool:
        """Check if heap allocation would overflow into stack."""
        # This is a compile-time warning/estimate
        # Actual runtime checking would need more complex tracking
        heap_end = self.STACK_BASE
        # Emit a comment warning for large allocations
        if size > (heap_end - self.HEAP_START) // 2:
            self.emit(None, comment=f"WARNING: Large allocation ({size} bytes) may cause heap-stack collision")
        return True
    
    def visit_program(self, node: Program) -> None:
        """Generate code for the entire program."""
        self.emit_immediate(InstructionType.MVR, self.STACK_TOP, self.STACK_POINTER_REG, 
                          comment="Initialize stack pointer")
        self.emit_immediate(InstructionType.MVR, self.STACK_TOP, self.FRAME_POINTER_REG,
                          comment="Initialize frame pointer")
        
        for decl in node.declarations:
            if isinstance(decl, FunctionDeclaration):
                func_type = FunctionType(
                    decl.return_type,
                    [param.param_type for param in decl.parameters]
                )
                self.symbol_table.define_function(decl.name, func_type)
        
        # Emit global variable initializers BEFORE jumping to main,
        # so that globals are set up when main runs.
        for decl in node.declarations:
            if not isinstance(decl, FunctionDeclaration):
                decl.accept(self)
        
        self.emit(InstructionType.JMP, "func_main", comment="Jump to main")
        
        for decl in node.declarations:
            if isinstance(decl, FunctionDeclaration):
                decl.accept(self)
    
    def visit_function_declaration(self, node: FunctionDeclaration) -> None:
        """Generate code for function declaration with stack-frame prologue/epilogue."""
        self.current_function = node.name
        # Reset per-function frame depth counter
        self.current_local_frame_depth = 0

        # Function entry label
        self.emit_label(f"func_{node.name}")
        # ------------------------------------------------------------------
        # PROLOGUE  (skipped for main – main is entered via JMP, not JAL)
        # Frame layout after prologue (growing downward):
        #   FP+0 : old FP   (saved R4)
        #   FP+1 : ret addr (saved R2, set by caller's JAL)
        #   FP+2 : param 0  (pushed right-to-left by caller so param0 is on top)
        #   FP+3 : param 1  ...
        # ------------------------------------------------------------------
        self.symbol_table.enter_scope()

        if node.name != "main":
            self._emit_push(2, comment="Save return address (R2) → prologue")
            self._emit_push(self.FRAME_POINTER_REG, comment="Save caller's FP (R4) → prologue")
            self.emit(InstructionType.MVR, self.STACK_POINTER_REG, self.FRAME_POINTER_REG,
                     comment="Set FP = SP (establish new frame)")

        for i, param in enumerate(node.parameters):
            frame_offset = 2 + i
            self.symbol_table.define_parameter_on_stack(
                param.name, param.param_type, frame_offset)

        node.body.accept(self)
        self.symbol_table.exit_scope()

        if not self._ends_with_return(node.body):
            self.emit_immediate(InstructionType.MVR, 0, 0, comment="Default return value = 0")
            if node.name == "main":
                self.emit(InstructionType.HALT, comment="Halt execution")
            else:
                self._emit_function_epilogue()

        self.current_function = None
    
    def visit_variable_declaration(self, node: VariableDeclaration) -> None:
        """Generate code for variable declaration."""
        is_global = (self.symbol_table.current_scope == self.symbol_table.global_scope)

        # Special case: array variable with an ArrayLiteral initializer.
        # Define the symbol FIRST so we know its address, then write each
        # element directly at symbol.address + i.  This avoids the bug where
        # a separate temp allocation is made, its base address is stored as a
        # pointer at symbol.address, but visit_array_access uses symbol.address
        # as the direct element base (not as a pointer), reading the wrong data.
        if isinstance(node.var_type, ArrayType) and isinstance(node.initializer, ArrayLiteral):
            if is_global:
                size = node.var_type.size if hasattr(node.var_type, 'size') else 10
                self._check_static_bounds(size, node.name)
            symbol = self.symbol_table.define_variable(node.name, node.var_type)
            for i, elem in enumerate(node.initializer.elements):
                elem_reg = elem.accept(self)
                self.emit(InstructionType.LOAD, elem_reg,
                         Operand(symbol.address + i, True),
                         comment=f"Init {node.name}[{i}]")
                self._safe_free(elem_reg)
            return
        value_reg = None
        if node.initializer:
            value_reg = node.initializer.accept(self)

        if isinstance(node.var_type, ArrayType):
            # Arrays always go to RAM
            if is_global:
                size = node.var_type.size if hasattr(node.var_type, 'size') else 10
                self._check_static_bounds(size, node.name)
            symbol = self.symbol_table.define_variable(node.name, node.var_type)
            if value_reg is not None:
                if symbol.storage_location == StorageLocation.RAM:
                    self.emit(InstructionType.LOAD, value_reg,
                             Operand(symbol.address, True),
                             comment=f"Initialize array {node.name}")
                else:
                    self.emit(InstructionType.MVR, value_reg, symbol.address,
                             comment=f"Initialize array {node.name} (reg)")

        elif is_global:
            # Global scalar variables go to RAM
            self._check_static_bounds(2, node.name)
            symbol = self.symbol_table.define_variable(node.name, node.var_type)
            if value_reg is not None:
                self.emit(InstructionType.LOAD, value_reg,
                         Operand(symbol.address, True),
                         comment=f"Initialize global {node.name}")
                self._safe_free(value_reg)

        else:
            # Local scalar – lives in the current stack frame
            frame_offset = -(self.current_local_frame_depth + 1)  # -1, -2, -3 …
            self.current_local_frame_depth += 1

            symbol = self.symbol_table.define_variable_on_stack(
                node.name, node.var_type, frame_offset)

            # If the initializer result is in R0, save it to a temp NOW –
            # the upcoming SUB (stack allocation) will clobber R0.
            actual_value_reg = value_reg
            if value_reg is not None and value_reg == 0:
                actual_value_reg = self.symbol_table.allocate_temporary()
                self.emit(InstructionType.MVR, 0, actual_value_reg,
                         comment=f"Preserve init value of {node.name} before SP allocation")

            self._emit_sp_decrement(
                comment=f"Alloc stack slot for {node.name} (FP{frame_offset:+d})")

            # Store initializer value if provided
            if actual_value_reg is not None:
                stored_reg = self._emit_fp_store(actual_value_reg, frame_offset,
                                                  comment=f"Init {node.name}")
                self._safe_free(stored_reg)
                if actual_value_reg != stored_reg:
                    self._safe_free(actual_value_reg)
                if value_reg is not None and value_reg != actual_value_reg:
                    self._safe_free(value_reg)


    
    def visit_block(self, node: Block) -> None:
        """Generate code for block statement."""
        self.symbol_table.enter_scope()
        # Snapshot the frame depth so we can tell how many locals were added in this scope
        depth_at_entry = self.current_local_frame_depth

        for stmt in node.statements:
            stmt.accept(self)

        # Emit cleanup for any locals declared inside this block (SP += N)
        locals_in_scope = self.current_local_frame_depth - depth_at_entry
        if locals_in_scope > 0:
            self._emit_sp_increment(
                locals_in_scope,
                comment=f"Deallocate {locals_in_scope} local(s) on block exit")
        # Restore depth so the enclosing scope can reuse those slots
        self.current_local_frame_depth = depth_at_entry

        self.symbol_table.exit_scope()
    
    def visit_expression_statement(self, node: ExpressionStatement) -> None:
        """Generate code for expression statement.

        The expression result is a temporary register that the caller (here: the
        statement driver) never reads.  Free it immediately so it does not
        occupy a register across the next statement.
        """
        result_reg = node.expression.accept(self)
        # R0 and R1 are the ALU output registers; they are not tracked by the
        # allocator and must not be freed through it.
        self._safe_free(result_reg)
    
    def visit_if_statement(self, node: IfStatement) -> None:
        """Generate code for if statement."""
        condition_reg = node.condition.accept(self)
        
        else_label = self.generate_label("els")
        end_label = self.generate_label("endf")
        
        # Jump to else if condition is zero
        self.emit(InstructionType.JZ, else_label, condition_reg, comment="If condition")
        
        self.symbol_table.register_allocator.free_temporary_register(condition_reg)
        
        # Then branch
        node.then_branch.accept(self)
        self.emit(InstructionType.JMP, end_label, comment="Skip else")
        
        # Else branch
        self.emit_label(else_label)
        if node.else_branch:
            node.else_branch.accept(self)

        # End label
        self.emit_label(end_label)
    
    def visit_while_statement(self, node: WhileStatement) -> None:
        """Generate code for while statement."""
        loop_label = self.generate_label("wh_lp")
        end_label = self.generate_label("wh_lp_nd")
        
        self.continue_labels.append(loop_label)
        self.break_labels.append(end_label)
        
        # Loop start
        self.emit_label(loop_label)

        # Check condition
        condition_reg = node.condition.accept(self)
        self.emit(InstructionType.JZ, end_label, condition_reg, comment="While condition")

        self.symbol_table.register_allocator.free_temporary_register(condition_reg)
        
        # Loop body
        node.body.accept(self)
        
        # Jump back to start
        self.emit(InstructionType.JMP, loop_label, comment="Loop back")
        
        # End label
        self.emit_label(end_label)

        self.continue_labels.pop()
        self.break_labels.pop()

    def visit_for_statement(self, node: ForStatement) -> None:
        """Generate code for for statement."""
        loop_label = self.generate_label("fr_lp")
        continue_label = self.generate_label("fr_cntnu")
        end_label = self.generate_label("fr_lp_nd")
        
        self.continue_labels.append(continue_label)
        self.break_labels.append(end_label)
        
        # Initializer — result register is discarded at statement level.
        ra = self.symbol_table.register_allocator
        if node.initializer:
            init_reg = node.initializer.accept(self)
            self._safe_free(init_reg)
        
        # Loop start
        self.emit_label(loop_label)

        # Check condition
        if node.condition:
            condition_reg = node.condition.accept(self)
            self.emit(InstructionType.JZ, end_label, condition_reg, comment="For condition")
            # Free condition_reg immediately — consumed by branch.
            ra.free_temporary_register(condition_reg)
        
        # Loop body
        node.body.accept(self)
        
        # Continue point (for continue statements)
        self.emit_label(continue_label)

        # Increment — result register is discarded at statement level.
        if node.increment:
            inc_reg = node.increment.accept(self)
            self._safe_free(inc_reg)

        # Jump back to condition
        self.emit(InstructionType.JMP, loop_label, comment="For loop back")

        # End label
        self.emit_label(end_label)
        
        self.continue_labels.pop()
        self.break_labels.pop()
    
    def visit_switch_statement(self, node: SwitchStatement) -> None:
        """Generate code for switch statement."""
        # This is a simplified switch implementation
        # A more sophisticated version would use jump tables
        
        expr_reg = node.expression.accept(self)
        end_label = self.generate_label("swtch_nd")
        
        self.break_labels.append(end_label)
        
        case_labels = []
        default_label = None
        
        # Generate labels for cases
        for case in node.cases:
            if case.value is None:
                default_label = self.generate_label("swtch_dflt")
            else:
                case_labels.append(self.generate_label("swtch_cse"))
        
        # Generate comparison code for each case
        case_idx = 0
        for case in node.cases:
            if case.value is not None:
                value_reg = case.value.accept(self)

                # Compare expression with case value; result goes to R0
                self.emit(InstructionType.SUB, expr_reg, value_reg, 
                         comment=f"Compare case {case_idx}")
                self.emit(InstructionType.JZ, case_labels[case_idx], 0, 
                         comment="Jump if equal")
                
                case_idx += 1
        
        # Jump to default if no cases matched
        if default_label:
            self.emit(InstructionType.JMP, default_label, comment="Jump to default")
        else:
            self.emit(InstructionType.JMP, end_label, comment="No default case")
        
        # Generate case bodies
        case_idx = 0
        for case in node.cases:
            if case.value is None:
                self.emit_label(default_label)
            else:
                self.emit_label(case_labels[case_idx])
                case_idx += 1

            for stmt in case.statements:
                stmt.accept(self)

        # End label
        self.emit_label(end_label)

        self.break_labels.pop()
    
    def visit_return_statement(self, node: ReturnStatement) -> None:
        """Generate code for return statement."""
        if node.value:
            return_reg = node.value.accept(self)
            self.emit(InstructionType.MVR, return_reg, 0, comment="Set return value in R0")
        else:
            self.emit_immediate(InstructionType.MVR, 0, 0, comment="Return 0")

        if self.current_function == "main":
            self.emit(InstructionType.HALT, comment="Halt execution")
        else:
            self._emit_function_epilogue()
    
    def visit_break_statement(self, node: BreakStatement) -> None:
        """Generate code for break statement."""
        if not self.break_labels:
            raise CodeGenerationError("Break statement outside loop or switch")
        
        self.emit(InstructionType.JMP, self.break_labels[-1], comment="Break")
    
    def visit_continue_statement(self, node: ContinueStatement) -> None:
        """Generate code for continue statement."""
        if not self.continue_labels:
            raise CodeGenerationError("Continue statement outside loop")
        
        self.emit(InstructionType.JMP, self.continue_labels[-1], comment="Continue")
    
    def _emit_comparison_result(
        self,
        operator: 'BinaryOperator',
        result_reg: int,
        true_label: str,
        end_label: str,
    ) -> None:
        """Emit the conditional-jump sequence for one comparison operator.

        Assumes the SUB result is already in R0.  Allocates a sign-bit scratch
        register only for the operators that need it, using allocate_protected
        to pin result_reg during scratch allocation.

        After the call the instruction stream is positioned at the fall-through
        (false) path; ``true_label`` and ``end_label`` are emitted by the
        caller.
        """
        ra = self.symbol_table.register_allocator
        if operator == BinaryOperator.EQUALS:
            self.emit(InstructionType.JZ, true_label, 0)
        elif operator == BinaryOperator.NOT_EQUALS:
            self.emit(InstructionType.JNZ, true_label, 0)
        elif operator == BinaryOperator.LESS_THAN:
            temp_reg = ra.allocate_protected(result_reg)
            self.emit_immediate(InstructionType.MVR, 0x8000, temp_reg, comment="Load sign bit mask")
            self.emit(InstructionType.AND, 0, temp_reg, comment="Check sign bit")
            self.emit(InstructionType.JNZ, true_label, 0, comment="Jump if negative (less than)")
            ra.free_temporaries(temp_reg)
        elif operator == BinaryOperator.GREATER_THAN:
            else_label = self.generate_label("nt_grtr")
            self.emit(InstructionType.JZ, else_label, 0, comment="Jump if equal (not greater)")
            temp_reg = ra.allocate_protected(result_reg)
            self.emit_immediate(InstructionType.MVR, 0x8000, temp_reg, comment="Load sign bit mask")
            self.emit(InstructionType.AND, 0, temp_reg, comment="Check sign bit")
            self.emit(InstructionType.JZ, true_label, 0, comment="Jump if positive (greater than)")
            self.emit_label(else_label)
            ra.free_temporaries(temp_reg)
        elif operator == BinaryOperator.LESS_EQUAL:
            self.emit(InstructionType.JZ, true_label, 0, comment="Jump if equal")
            temp_reg = ra.allocate_protected(result_reg)
            self.emit_immediate(InstructionType.MVR, 0x8000, temp_reg, comment="Load sign bit mask")
            self.emit(InstructionType.AND, 0, temp_reg, comment="Check sign bit")
            self.emit(InstructionType.JNZ, true_label, 0, comment="Jump if negative (less than)")
            ra.free_temporaries(temp_reg)
        elif operator == BinaryOperator.GREATER_EQUAL:
            self.emit(InstructionType.JZ, true_label, 0, comment="Jump if equal")
            temp_reg = ra.allocate_protected(result_reg)
            self.emit_immediate(InstructionType.MVR, 0x8000, temp_reg, comment="Load sign bit mask")
            self.emit(InstructionType.AND, 0, temp_reg, comment="Check sign bit")
            self.emit(InstructionType.JZ, true_label, 0, comment="Jump if positive (greater than)")
            ra.free_temporaries(temp_reg)
        else:
            raise CodeGenerationError(f"Unsupported comparison operator: {operator}")

    def visit_binary_expression(self, node: BinaryExpression) -> int:
        """Generate code for binary expression and return result register."""
        with self._expression_scope():
            left_reg = node.left.accept(self)

            # Save left_reg if it could be clobbered by right operand evaluation.
            # Both cases (R0 ALU result AND R4+ temp register) are now handled
            # identically by pushing to the hardware stack.  This prevents register
            # exhaustion from deep expression trees: each nesting level uses one
            # stack slot rather than one register file slot.
            needs_save = (left_reg == 0 or left_reg >= 4)
            if needs_save:
                self._emit_push(left_reg, comment="Save left operand to stack")
                self._safe_free(left_reg)

            right_reg = node.right.accept(self)

            # Restore left operand from the stack.
            if needs_save:
                # right_reg holds the value we need next, but _emit_pop clobbers R0.
                # Pin/save right_reg so it survives the pop.
                ra = self.symbol_table.register_allocator

                if right_reg == 0:
                    right_reg = ra.save_alu_result(pin_live=True)
                else:
                    ra.mark_register_live(right_reg)

                temp_left_reg = self.symbol_table.allocate_temporary()
                self._emit_pop(temp_left_reg, comment="Restore left operand from stack")
                
                ra.mark_register_consumed(right_reg)

                left_reg = temp_left_reg

            # Arithmetic, bitwise, logical, and comparison operations
            ra = self.symbol_table.register_allocator
            if node.operator == BinaryOperator.MODULO:
                # a % b = a - (a / b) * b
                div_reg = ra.allocate_protected(left_reg, right_reg)
                self.emit(InstructionType.DIV, left_reg, right_reg, comment="Modulo: a / b")
                self.emit(InstructionType.MVR, 0, div_reg, comment="Save quotient for modulo")
                self.emit(InstructionType.MULT, div_reg, right_reg, comment="Modulo: (a / b) * b")
                mult_reg = ra.allocate_protected(left_reg, right_reg)
                self.emit(InstructionType.MVR, 0, mult_reg, comment="Save product for modulo")
                self.emit(InstructionType.SUB, left_reg, mult_reg, comment="Modulo: a - (a / b) * b")
                ra.free_temporaries(div_reg, mult_reg, right_reg)
                return 0
            elif node.operator == BinaryOperator.LOGICAL_AND:
                result_reg = ra.allocate_protected(left_reg, right_reg)
                false_label = self.generate_label("lgc_nd_fls")
                end_label = self.generate_label("lgc_nd_nd")
                self.emit(InstructionType.JZ, false_label, left_reg, comment="Logical AND: left zero")
                self.emit(InstructionType.JZ, false_label, right_reg, comment="Logical AND: right zero")
                self.emit_immediate(InstructionType.MVR, 1, result_reg, comment="Logical AND: true")
                self.emit(InstructionType.JMP, end_label)
                self.emit_label(false_label)
                self.emit_immediate(InstructionType.MVR, 0, result_reg, comment="Logical AND: false")
                self.emit_label(end_label)
                ra.free_temporaries(left_reg, right_reg)
                return result_reg
            elif node.operator == BinaryOperator.LOGICAL_OR:
                result_reg = ra.allocate_protected(left_reg, right_reg)
                true_label = self.generate_label("lgc_or_tru")
                end_label = self.generate_label("lgc_or_nd")
                self.emit(InstructionType.JNZ, true_label, left_reg, comment="Logical OR: left nonzero")
                self.emit(InstructionType.JNZ, true_label, right_reg, comment="Logical OR: right nonzero")
                self.emit_immediate(InstructionType.MVR, 0, result_reg, comment="Logical OR: false")
                self.emit(InstructionType.JMP, end_label)
                self.emit_label(true_label)
                self.emit_immediate(InstructionType.MVR, 1, result_reg, comment="Logical OR: true")
                self.emit_label(end_label)
                ra.free_temporaries(left_reg, right_reg)
                return result_reg
            elif node.operator in [
                BinaryOperator.EQUALS, BinaryOperator.NOT_EQUALS,
                BinaryOperator.LESS_THAN, BinaryOperator.GREATER_THAN,
                BinaryOperator.LESS_EQUAL, BinaryOperator.GREATER_EQUAL,
            ]:
                # allocate_protected pins both operands live during result_reg allocation.
                result_reg = ra.allocate_protected(left_reg, right_reg)
                self.emit(InstructionType.SUB, left_reg, right_reg, comment="Comparison")
                true_label = self.generate_label("tru")
                end_label = self.generate_label("cmp_nd")
                self._emit_comparison_result(node.operator, result_reg, true_label, end_label)
                self.emit_immediate(InstructionType.MVR, 0, result_reg)
                self.emit(InstructionType.JMP, end_label)
                self.emit_label(true_label)
                self.emit_immediate(InstructionType.MVR, 1, result_reg, comment="True case")
                self.emit_label(end_label)
                ra.free_temporaries(left_reg, right_reg)
                return result_reg
            else:
                # Arithmetic/bitwise
                if node.operator in self._BINARY_OP_MAP:
                    self.emit(self._BINARY_OP_MAP[node.operator], left_reg, right_reg,
                             comment=f"{node.operator.value} operation")
                    ra.free_temporaries(left_reg, right_reg)
                    return 0  # Result in register 0 (ALU output)
                raise CodeGenerationError(f"Unsupported binary operator: {node.operator}")
    
    def visit_unary_expression(self, node: UnaryExpression) -> int:
        """Generate code for unary expression and return result register."""
        with self._expression_scope():
            operand_reg = node.operand.accept(self)

            if node.operator == UnaryOperator.NEGATE:
                temp_reg = self.symbol_table.allocate_temporary()
                self.emit_immediate(InstructionType.MVR, 0, temp_reg, comment="Load 0 for negation")
                self.emit(InstructionType.SUB, temp_reg, operand_reg, comment="Negate")
                return 0
            elif node.operator == UnaryOperator.NOT:
                # Bitwise NOT
                self.emit(InstructionType.NOT, operand_reg, comment="Bitwise NOT")
                return 0
            elif node.operator == UnaryOperator.LOGICAL_NOT:
                # Logical NOT: result is 1 if operand is zero, else 0
                result_reg = self.symbol_table.allocate_temporary()
                true_label = self.generate_label("lgc_nt_tru")
                end_label = self.generate_label("lgc_nt_nd")
                self.emit(InstructionType.JZ, true_label, operand_reg, comment="Logical NOT: operand zero")
                self.emit_immediate(InstructionType.MVR, 0, result_reg, comment="Logical NOT: false")
                self.emit(InstructionType.JMP, end_label)
                self.emit_label(true_label)
                self.emit_immediate(InstructionType.MVR, 1, result_reg, comment="Logical NOT: true")
                self.emit_label(end_label)
                return result_reg
            elif node.operator == UnaryOperator.ADDRESS_OF:
                # Special handling for address of array element: @arr[index]
                if isinstance(node.operand, ArrayAccess):
                    array_node = node.operand.array
                    index_node = node.operand.index
                    if isinstance(array_node, Identifier):
                        symbol = self.symbol_table.resolve(array_node.name)
                        if symbol and symbol.storage_location == StorageLocation.RAM:
                            # Calculate element address without dereferencing
                            index_reg = index_node.accept(self)
                            addr_reg = self._emit_array_address(
                                symbol.address, index_reg,
                                comment=f"Address of {array_node.name}[index]")
                            self._safe_free(index_reg)
                            return addr_reg

                # Regular address-of for simple variables
                symbol_name = getattr(node.operand, 'name', None)
                if symbol_name:
                    symbol = self.symbol_table.resolve(symbol_name)
                    if symbol:
                        # Stack variables: address is FP + frame_offset
                        if symbol.storage_location == StorageLocation.STACK:
                            return self._emit_fp_address(
                                symbol.frame_offset,
                                comment=f"Address of {symbol_name} (FP{symbol.frame_offset:+d})")
                        # If symbol is an array or RAM variable, return its address as immediate
                        if symbol.kind == SymbolKind.ARRAY or symbol.storage_location == StorageLocation.RAM:
                            result_reg = self.symbol_table.allocate_temporary()
                            self.emit_immediate(InstructionType.MVR, symbol.address, result_reg,
                                               comment=f"Address of {symbol_name} (RAM)")
                            return result_reg
                        # If symbol is in a register, move it to RAM first
                        if symbol.storage_location == StorageLocation.REGISTER:
                            ram_addr = self.symbol_table.memory_manager.allocate_memory(
                                symbol.name, symbol.size)
                            self.emit(InstructionType.LOAD, symbol.address,
                                     Operand(ram_addr, True),
                                     comment=f"Move {symbol_name} from R{symbol.address} to RAM")
                            self.symbol_table.register_allocator.free_register(symbol.address)
                            symbol.storage_location = StorageLocation.RAM
                            symbol.address = ram_addr
                            result_reg = self.symbol_table.allocate_temporary()
                            self.emit_immediate(InstructionType.MVR, ram_addr, result_reg,
                                               comment=f"Address of {symbol_name} (moved to RAM)")
                            return result_reg
                # If not a simple variable, evaluate operand and return its register (address)
                return node.operand.accept(self)
            elif node.operator == UnaryOperator.DEREFERENCE:
                result_reg = self.symbol_table.allocate_temporary()
                self.emit(InstructionType.READ, operand_reg, result_reg, comment="Dereference")
                return result_reg
            else:
                raise CodeGenerationError(f"Unsupported unary operator: {node.operator}")
    
    def visit_assignment_expression(self, node: AssignmentExpression) -> int:
        """Generate code for assignment expression."""
        value_reg = node.value.accept(self)

        # Handle different assignment targets
        if isinstance(node.target, Identifier):
            symbol = self.symbol_table.resolve(node.target.name)
            if not symbol:
                raise CodeGenerationError(f"Undefined variable: {node.target.name}")

            if symbol.storage_location == StorageLocation.STACK:
                # FP-relative store.  _emit_fp_store always copies to a fresh temp
                # and returns that temp; the stored value lives there.
                result_reg = self._emit_fp_store(
                    value_reg, symbol.frame_offset,
                    comment=f"Assign to {node.target.name} (FP{symbol.frame_offset:+d})")
                
                self._safe_free(value_reg)
                # result_reg is a fresh temp holding the stored value; caller owns it.
                return result_reg

            if symbol.storage_location == StorageLocation.RAM:
                self.emit(InstructionType.LOAD, value_reg,
                         Operand(symbol.address, True),
                         comment=f"Assign to {node.target.name} (RAM)")
                return value_reg

            # REGISTER storage
            target_reg = self.symbol_table.register_allocator.access_symbol(node.target.name)
            self.emit(InstructionType.MVR, value_reg, target_reg,
                     comment=f"Assign to {node.target.name} (R{target_reg})")
            return target_reg

        elif isinstance(node.target, ArrayAccess):
            # Array assignment
            array_node = node.target.array
            index_node = node.target.index
            # If array_node is an Identifier, get its symbol and RAM address
            if isinstance(array_node, Identifier):
                symbol = self.symbol_table.resolve(array_node.name)
                if symbol and symbol.storage_location == StorageLocation.RAM:
                    index_reg = index_node.accept(self)
                    addr_reg = self._emit_array_address(
                        symbol.address, index_reg,
                        comment=f"Base address of {array_node.name}")
                    self._safe_free(index_reg)
                    self.emit(InstructionType.LOAD, value_reg, addr_reg, comment="Array assignment")
                    self._safe_free(addr_reg)
                    return value_reg
            # Fallback: treat as pointer arithmetic
            base_reg = array_node.accept(self)
            index_reg = index_node.accept(self)
            addr_reg = self._emit_array_address(base_reg, index_reg,
                                                 comment="Array address (fallback)",
                                                 base_is_reg=True)
            self._safe_free(base_reg)
            self._safe_free(index_reg)
            self.emit(InstructionType.LOAD, value_reg, addr_reg, comment="Array assignment (fallback)")
            self._safe_free(addr_reg)
            return value_reg
        elif isinstance(node.target, UnaryExpression) and node.target.operator == UnaryOperator.DEREFERENCE:
            ptr_reg = node.target.operand.accept(self)
            ptr_reg = self._rescue_r0(ptr_reg, comment="Save pointer address from ALU")
            self.emit(InstructionType.LOAD, value_reg, ptr_reg, comment="Pointer dereference assignment")
            self._safe_free(value_reg)
            return ptr_reg
        else:
            raise CodeGenerationError(f"Invalid assignment target: {type(node.target)}")
    
    def visit_function_call(self, node: FunctionCall) -> int:
        """Generate code for function call using stack-based argument passing.

        Calling convention:
          1. Caller evaluates all arguments and saves them to temp registers.
          2. Caller pushes args right-to-left (last arg first) so parameter 0
             ends up closest to the top of the stack when the callee runs.
          3. JAL is issued → R2 = return address, PC = callee.
          4. Callee prologue: push R2, push old FP, FP = SP  (see visit_function_declaration).
          5. Callee accesses params at FP+2, FP+3, …
          6. On return: caller pops all N arguments by adding N to SP.
        """
        # ------------------------------------------------------------------
        # Step 1 – evaluate every argument and make sure it is in a temp reg
        #          (not in R0, because _emit_push uses SUB which writes R0).
        # ------------------------------------------------------------------
        args_regs = []
        for arg in node.arguments:
            # Handle array-to-pointer decay
            if isinstance(arg, Identifier):
                sym = self.symbol_table.resolve(arg.name)
                if sym and isinstance(sym.symbol_type, ArrayType):
                    arg_reg = self.symbol_table.allocate_temporary()
                    self.emit_immediate(InstructionType.MVR, sym.address, arg_reg,
                                       comment=f"Array-to-pointer decay: {arg.name}")
                    args_regs.append(arg_reg)
                    continue

            arg_reg = arg.accept(self)
            # Rescue R0: _emit_push starts with SUB which clobbers R0.
            args_regs.append(self._rescue_r0(arg_reg, comment="Move arg from R0 to temp"))

        # ------------------------------------------------------------------
        # Step 2 – push arguments right-to-left so param 0 is on top
        # ------------------------------------------------------------------
        for reg in reversed(args_regs):
            self._emit_push(reg, comment="Push argument")

        # Free temp arg registers (value is now safely on the stack)
        for reg in args_regs:
            self.symbol_table.register_allocator.free_temporary_register(reg)

        # ------------------------------------------------------------------
        # Step 3 – call the function
        # ------------------------------------------------------------------
        if isinstance(node.function, Identifier):
            self.emit(InstructionType.JAL, f"func_{node.function.name}",
                     comment=f"Call {node.function.name}")
        else:
            func_reg = node.function.accept(self)
            self.emit(InstructionType.JAL, func_reg, comment="Call function pointer")

        # ------------------------------------------------------------------
        # Step 4 – save return value before SP adjustment clobbers R0
        # ------------------------------------------------------------------
        result_reg = self.symbol_table.allocate_temporary()
        self.emit(InstructionType.MVR, 0, result_reg, comment="Save function return value")

        # ------------------------------------------------------------------
        # Step 5 – caller cleans up: SP += N  (pop the N argument slots)
        # ------------------------------------------------------------------
        n = len(node.arguments)
        if n > 0:
            self._emit_sp_increment(n, comment=f"Pop {n} argument slot(s)")

        return result_reg
    
    def visit_gpu_function_call(self, node) -> int:
        """Generate code for GPU built-in function calls.

        Register management follows the same pattern as binary expressions:

        1. Evaluate arguments left-to-right.  Every argument that lands in R0
           (the ALU output register) is immediately saved to a fresh temp via
           ``ra.save_alu_result(pin_live=True)``, which allocates a temp,
           emits ``MVR 0 temp``, and marks the temp live.  The temp is added to
           ``saved_temps`` so it can be freed after codegen.

        2. ALL collected arg registers are pinned live with ``ra.pin_register``
           before the GPU-specific codegen runs.  This prevents the allocator
           from spilling or reusing them as scratch inside the GPU paths.

        3. Scratch registers needed during GPU codegen (e.g. ``masked_gpu_reg``
           for the setGPUBuffer edit-buffer path) are allocated with
           ``ra.allocate_protected(*arg_regs)`` which re-pins the args for the
           duration of that single allocation then unpins them again.

        4. Cleanup: all arg pins are released via ``ra.unpin_register``, then
           saved temps are freed via ``ra.free_temporaries``.
        """
        ra = self.symbol_table.register_allocator

        # ------------------------------------------------------------------
        # Step 1 – evaluate arguments, preserving any R0 results in temps
        # ------------------------------------------------------------------
        arg_regs = []
        saved_temps = []   # temps allocated by save_alu_result (to free later)
        for arg in node.arguments:
            reg = arg.accept(self)
            if reg == 0:
                # R0 will be overwritten by the next evaluation.
                # save_alu_result allocates a temp, emits MVR 0 temp, pins live.
                temp = ra.save_alu_result(pin_live=True)
                arg_regs.append(temp)
                saved_temps.append(temp)
            else:
                arg_regs.append(reg)

        # ------------------------------------------------------------------
        # Step 2 – mark ALL arg registers live before GPU codegen
        # ------------------------------------------------------------------
        # This prevents the allocator from spilling any arg register during
        # the scratch allocations that happen inside the GPU codegen paths.
        for reg in arg_regs:
            ra.mark_register_live(reg)

        # ------------------------------------------------------------------
        # Helper: release live marks and free all arg temps.
        #
        # Every register in arg_regs was either:
        #   (a) produced by save_alu_result() → lives in saved_temps, OR
        #   (b) produced directly by arg.accept(self) → a plain temp.
        #
        # Both categories must be freed here; the GPU instruction has already
        # consumed the values, so the caller has no further need for them.
        # ------------------------------------------------------------------
        def _cleanup():
            for reg in arg_regs:
                ra.mark_register_consumed(reg)
            # Free ALL arg registers (both saved_temps and plain arg temps).
            ra.free_temporaries(*arg_regs)

        # ------------------------------------------------------------------
        # Step 3 – GPU-specific codegen
        # ------------------------------------------------------------------
        if node.function_name == 'setGPUBuffer':
            # setGPUBuffer(buffer_id, value)
            # buffer_id: 0 (edit), 1 (display)
            if len(arg_regs) != 2:
                raise CodeGenerationError("setGPUBuffer requires 2 arguments")
            buffer_id_reg, value_reg = arg_regs[0], arg_regs[1]
            self.emit(InstructionType.MVR, 'GPU', 0, comment="Load GPU register")
            if hasattr(node.arguments[0], 'value'):
                buf_id = node.arguments[0].value
                if buf_id == 0:
                    # Edit buffer: clear bit 1, OR with (value << 1).
                    # SHL clobbers R0 so save AND result to a dedicated temp.
                    # allocate_protected re-pins arg_regs for this one allocation.
                    masked_gpu_reg = ra.allocate_protected(*arg_regs)
                    self.emit(InstructionType.AND, 0, 'i:0xFFFFFFFD', comment="Clear bit 1 (edit)")
                    self.emit(InstructionType.MVR, 0, masked_gpu_reg, comment="Save masked GPU value")
                    self.emit(InstructionType.SHL, value_reg, 'i:1', comment="Shift value for edit buffer")
                    self.emit(InstructionType.OR, 0, masked_gpu_reg, comment="Set edit buffer bit")
                    ra.free_temporaries(masked_gpu_reg)
                elif buf_id == 1:
                    self.emit(InstructionType.AND, 0, 'i:0xFFFFFFFE', comment="Clear bit 0 (display)")
                    self.emit(InstructionType.OR, 0, value_reg, comment="Set display buffer bit")
                else:
                    _cleanup()
                    raise CodeGenerationError("Invalid buffer_id for setGPUBuffer (must be 0 or 1)")
            else:
                # Dynamic buffer_id: save AND result before SHL overwrites R0.
                masked_gpu_reg = ra.allocate_protected(*arg_regs)
                self.emit(InstructionType.AND, 0, 'i:0xFFFFFFFC', comment="Clear both buffer bits")
                self.emit(InstructionType.MVR, 0, masked_gpu_reg, comment="Save masked GPU value to temp")
                self.emit(InstructionType.SHL, value_reg, buffer_id_reg, comment="Shift value by buffer_id")
                self.emit(InstructionType.OR, 0, masked_gpu_reg, comment="Set buffer bit dynamically")
                ra.free_temporaries(masked_gpu_reg)
            self.emit(InstructionType.MVR, 0, 'GPU', comment="Update GPU register")
            _cleanup()
            return 0

        elif node.function_name == 'getGPUBuffer':
            # getGPUBuffer(buffer_id)
            if len(arg_regs) != 1:
                raise CodeGenerationError("getGPUBuffer requires 1 argument")
            buffer_id_reg = arg_regs[0]
            self.emit(InstructionType.MVR, 'GPU', 0, comment="Load GPU register")
            if hasattr(node.arguments[0], 'value'):
                buf_id = node.arguments[0].value
                if buf_id == 0:
                    self.emit(InstructionType.SHR, 0, 'i:1', comment="Shift right for edit buffer")
                    self.emit(InstructionType.AND, 0, 'i:1', comment="Mask edit buffer bit")
                elif buf_id == 1:
                    self.emit(InstructionType.AND, 0, 'i:1', comment="Mask display buffer bit")
                else:
                    _cleanup()
                    raise CodeGenerationError("Invalid buffer_id for getGPUBuffer (must be 0 or 1)")
            else:
                self.emit(InstructionType.SHR, 0, buffer_id_reg, comment="Shift right by buffer_id")
                self.emit(InstructionType.AND, 0, 'i:1', comment="Mask buffer bit dynamically")
            _cleanup()
            return 0

        # Default: other GPU built-ins
        gpu_func_map = self._GPU_FUNC_MAP
        if node.function_name not in gpu_func_map:
            _cleanup()
            raise CodeGenerationError(f"Unknown GPU function: {node.function_name}")
        instruction_type = gpu_func_map[node.function_name]

        # Build operand list: use immediate form for bare literals (non-R0 args
        # that weren't redirected through a saved temp).
        immediate_args = []
        for i, reg in enumerate(arg_regs):
            if reg not in saved_temps and hasattr(node.arguments[i], 'value'):
                immediate_args.append(f"i:{node.arguments[i].value}")
            else:
                immediate_args.append(reg)
        if immediate_args:
            self.emit(instruction_type, *immediate_args, comment=f"GPU: {node.function_name}")
        else:
            self.emit(instruction_type, comment=f"GPU: {node.function_name}")
        _cleanup()
        return 0
    
    def visit_memory_function_call(self, node) -> int:
        """Generate code for memory management function calls (malloc, free)."""
        from .ast_nodes import MemoryFunctionCall
        
        if node.function_name == "malloc":
            # malloc(size) - allocate memory and return pointer
            if len(node.arguments) != 1:
                raise CodeGenerationError("malloc requires exactly 1 argument (size)")
            
            size_expr = node.arguments[0]
            
            # Handle compile-time constant sizes
            if hasattr(size_expr, 'value') and isinstance(size_expr.value, int):
                size = size_expr.value
                
                temp_symbol_name = f"malloc_temp_{self.label_counter}"
                self.label_counter += 1
                
                ram_addr = self.symbol_table.memory_manager.allocate_memory(temp_symbol_name, size)
                if ram_addr is None:
                    raise CodeGenerationError(f"Failed to allocate {size} bytes of memory")
                
                # Return pointer (address) in a register
                result_reg = self.symbol_table.allocate_temporary()
                # MVR immediate_value, register (source, destination)
                ops = [Operand(ram_addr, True), Operand(result_reg)]  # immediate source, register dest
                instruction = Instruction(InstructionType.MVR, ops, f"malloc({size}) -> {ram_addr}")
                self.instructions.append(instruction)
                return result_reg
            else:
                raise CodeGenerationError("malloc with runtime size not supported - size must be compile-time constant")
        
        elif node.function_name == "free":
            # free(ptr) - free memory pointed to by pointer
            if len(node.arguments) != 1:
                raise CodeGenerationError("free requires exactly 1 argument (pointer)")
            
            ptr_reg = node.arguments[0].accept(self)
            
            self.emit(InstructionType.MVR, 0, 0, comment=f"free(R{ptr_reg}) - memory deallocated at compile time")
            
            return 0  # free returns void
        elif node.function_name == "readChar":
            # readChar() - read a single character from input using KEYIN
            if len(node.arguments) != 0:
                raise CodeGenerationError("readChar takes no arguments")

            # Allocate one byte in RAM to receive KEYIN
            temp_symbol_name = f"readchar_temp_{self.label_counter}"
            self.label_counter += 1

            ram_addr = self.symbol_table.memory_manager.allocate_memory(temp_symbol_name, 1)
            if ram_addr is None:
                raise CodeGenerationError("Failed to allocate memory for readChar buffer")

            # Emit KEYIN ram_addr
            # KEYIN expects an address operand; use immediate address
            self.emit(InstructionType.KEYIN, Operand(ram_addr, True), comment=f"KEYIN -> {ram_addr}")

            # Read the value from RAM into a register and return it
            result_reg = self.symbol_table.allocate_temporary()
            self.emit(InstructionType.READ, Operand(ram_addr, True), result_reg, comment="Read char into register")
            return result_reg
        
        else:
            raise CodeGenerationError(f"Unknown memory function: {node.function_name}")
    
    def visit_array_access(self, node: ArrayAccess) -> int:
        """Generate code for array access."""
        array_node = node.array
        index_node = node.index
        # If array_node is an Identifier, get its symbol and RAM address
        if isinstance(array_node, Identifier):
            symbol = self.symbol_table.resolve(array_node.name)
            if symbol and symbol.storage_location == StorageLocation.RAM:
                index_reg = index_node.accept(self)
                addr_reg = self._emit_array_address(
                    symbol.address, index_reg,
                    comment=f"Base address of {array_node.name}")
                self._safe_free(index_reg)
                result_reg = self.symbol_table.allocate_temporary()
                self.emit(InstructionType.READ, addr_reg, result_reg, comment="Load array element")
                self._safe_free(addr_reg)
                return result_reg
        # Fallback: treat as pointer arithmetic
        base_reg = array_node.accept(self)
        index_reg = index_node.accept(self)
        addr_reg = self._emit_array_address(base_reg, index_reg,
                                             comment="Array index calculation (fallback)",
                                             base_is_reg=True)
        self._safe_free(base_reg)
        self._safe_free(index_reg)
        result_reg = self.symbol_table.allocate_temporary()
        self.emit(InstructionType.READ, addr_reg, result_reg, comment="Load array element (fallback)")
        self._safe_free(addr_reg)
        return result_reg
    
    
    def visit_array_literal(self, node: ArrayLiteral) -> int:
        # Allocate contiguous RAM for the array
        size = len(node.elements)
        ram_addr = self.symbol_table.memory_manager.allocate_memory("array_literal_temp_{}".format(self.label_counter), size)
        self.label_counter += 1
        
        for i, elem in enumerate(node.elements):
            value_reg = elem.accept(self)
            addr = ram_addr + i
            self.emit(InstructionType.LOAD, value_reg, Operand(addr, True), comment=f"Init array literal element {i}")
        # Return base RAM address as a temporary register
        result_reg = self.symbol_table.allocate_temporary()
        self.emit_immediate(InstructionType.MVR, ram_addr, result_reg, comment="Array literal base address")
        return result_reg

    def visit_integer_literal(self, node: IntegerLiteral) -> int:
        """Generate code for integer literal."""
        result_reg = self.symbol_table.allocate_temporary()
        self.emit_immediate(InstructionType.MVR, node.value, result_reg, 
                           comment=f"Load literal {node.value}")
        return result_reg

    def visit_asm_function_call(self, node: 'AsmFunctionCall') -> int:
        """Inject raw assembly from asm("template", arg0, arg1, ...) into the output.

        The template string may contain ``%0``, ``%1``, … placeholders which
        are substituted with the register-number strings of the corresponding
        evaluated MCL arguments before the lines are emitted.  Substitution is
        performed longest-first (``%10`` before ``%1``) so multi-digit indices
        do not partially match shorter ones.

        For immediate-mode usage the caller can prefix the placeholder in the
        template: ``i:%0`` becomes e.g. ``i:7`` after substitution, which is a
        valid immediate operand in the assembly.

        The asm() expression evaluates to the value in register 0.
        """
        ra = self.symbol_table.register_allocator

        # ------------------------------------------------------------------
        # 1. Evaluate each argument, keeping all results live so that a later
        #    argument evaluation doesn't evict an earlier one.
        #    Mirrors the pattern used in visit_gpu_function_call.
        # ------------------------------------------------------------------
        arg_regs = []
        saved_temps = []  # temps created by save_alu_result (to free later)
        for arg_expr in (node.args or []):
            reg = arg_expr.accept(self)
            if reg == 0:
                # R0 is the ALU output register; the next evaluation would
                # clobber it.  Save it into a pinned temp now.
                temp = ra.save_alu_result(pin_live=True)
                arg_regs.append(temp)
                saved_temps.append(temp)
            else:
                arg_regs.append(reg)

        # Pin all arg regs live so the allocator won't reuse them.
        for reg in arg_regs:
            ra.mark_register_live(reg)

        # ------------------------------------------------------------------
        # 2. Build the %N → register-string substitution table.
        #    Sort keys longest-first to avoid partial matches (e.g. "%10"
        #    before "%1").
        # ------------------------------------------------------------------
        substitutions = {f"%{i}": str(reg) for i, reg in enumerate(arg_regs)}
        sorted_keys = sorted(substitutions, key=len, reverse=True)

        def _apply_substitutions(text: str) -> str:
            for key in sorted_keys:
                text = text.replace(key, substitutions[key])
            return text

        # ------------------------------------------------------------------
        # 3. Emit each line of the template after substitution.
        # ------------------------------------------------------------------
        asm_text = node.asm_text
        for raw_line in asm_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = _apply_substitutions(line)
            if line.startswith('//'):
                self.emit(None, comment=f"RAW_ASM:{line}")
                continue
            if line.endswith(':'):
                label_name = line[:-1]
                self.emit(None, comment=f"RAW_ASM:{line}", label=label_name)
                continue
            self.emit(None, comment=f"RAW_ASM:{line}")

        # ------------------------------------------------------------------
        # 4. Release live marks and free all arg temporaries.
        # ------------------------------------------------------------------
        for reg in arg_regs:
            ra.mark_register_consumed(reg)
        ra.free_temporaries(*arg_regs)

        # asm() returns value in register 0
        return 0
    
    def visit_char_literal(self, node: CharLiteral) -> int:
        """Generate code for character literal."""
        result_reg = self.symbol_table.allocate_temporary()
        ascii_value = ord(node.value)
        self.emit_immediate(InstructionType.MVR, ascii_value, result_reg, 
                           comment=f"Load char '{node.value}' ({ascii_value})")
        return result_reg
    
    def visit_identifier(self, node: Identifier) -> int:
        """Generate code for identifier (variable reference)."""
        symbol = self.symbol_table.resolve(node.name)
        if not symbol:
            raise CodeGenerationError(f"Undefined variable: {node.name}")

        if symbol.kind == SymbolKind.FUNCTION:
            result_reg = self.symbol_table.allocate_temporary()
            self.emit_immediate(InstructionType.MVR, f"func_{node.name}", result_reg,
                               comment=f"Function pointer {node.name}")
            return result_reg

        # STACK variables: load via FP-relative address
        if symbol.storage_location == StorageLocation.STACK:
            return self._emit_fp_load(symbol.frame_offset,
                                      comment=f"Load {node.name} (FP{symbol.frame_offset:+d})")

        # RAM variables: load from immediate address
        if symbol.storage_location == StorageLocation.RAM:
            result_reg = self.symbol_table.allocate_temporary()
            self.emit(InstructionType.READ, Operand(symbol.address, True), result_reg,
                     comment=f"Load {node.name} from RAM")
            return result_reg

        # REGISTER variable
        return self.symbol_table.register_allocator.access_symbol(node.name)
    
    # Type visitors (no code generation needed)
    def visit_int_type(self, node: IntType) -> None:
        pass
    
    def visit_void_type(self, node) -> None:
        pass
    
    def visit_pointer_type(self, node: PointerType) -> None:
        pass
    
    def visit_array_type(self, node: ArrayType) -> None:
        pass
    
    def visit_function_type(self, node: FunctionType) -> None:
        pass
    
    def _ends_with_return(self, block: Block) -> bool:
        """Check if block ends with a return statement."""
        if not block.statements:
            return False
        
        last_stmt = block.statements[-1]
        return isinstance(last_stmt, ReturnStatement)
    
    def get_assembly_code(self) -> str:
        """Get the generated assembly code as a string."""
        lines = []
        for instruction in self.instructions:
            lines.append(str(instruction))
        return "\n".join(lines)
    
    def get_memory_stats(self) -> Dict[str, any]:
        """Get memory usage statistics from symbol table."""
        return self.symbol_table.get_memory_stats()

# ---------------------------------------------------------------------------
# Class-level operator/function maps (populated after the class body so that
# both InstructionType and BinaryOperator are fully defined).
# ---------------------------------------------------------------------------
AssemblyGenerator._BINARY_OP_MAP = {
    BinaryOperator.ADD:         InstructionType.ADD,
    BinaryOperator.SUBTRACT:    InstructionType.SUB,
    BinaryOperator.MULTIPLY:    InstructionType.MULT,
    BinaryOperator.DIVIDE:      InstructionType.DIV,
    BinaryOperator.AND:         InstructionType.AND,   # keyword 'and'
    BinaryOperator.OR:          InstructionType.OR,    # keyword 'or'
    BinaryOperator.XOR:         InstructionType.XOR,   # keyword 'xor'
    BinaryOperator.SHIFT_LEFT:  InstructionType.SHL,
    BinaryOperator.SHIFT_RIGHT: InstructionType.SHR,
    # Symbol forms — intentionally alias the same opcodes as the keyword forms.
    BinaryOperator.BITWISE_AND: InstructionType.AND,
    BinaryOperator.BITWISE_OR:  InstructionType.OR,
    BinaryOperator.BITWISE_XOR: InstructionType.XOR,
}

AssemblyGenerator._GPU_FUNC_MAP = {
    'drawLine':     InstructionType.DRLINE,
    'fillGrid':     InstructionType.DRGRD,
    'clearGrid':    InstructionType.CLRGRID,
    'loadSprite':   InstructionType.LDSPR,
    'drawSprite':   InstructionType.DRSPR,
    'loadText':     InstructionType.LDTXT,
    'drawText':     InstructionType.DRTXT,
    'scrollBuffer': InstructionType.SCRLBFR,
}

class CodeGenerationError(Exception):
    """Exception raised for code generation errors."""
    pass

def generate_assembly(ast: Program, ram_start: int = 0x1000, ram_size: int = 0x1000) -> str:
    """Generate assembly code from AST."""
    generator = AssemblyGenerator(ram_start, ram_size)
    generator.visit_program(ast)
    return generator.get_assembly_code()