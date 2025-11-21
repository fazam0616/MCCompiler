"""MCL Assembly Generator

Generates assembly code from AST nodes.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Union
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
            result += f"  // {self.comment}"
        
        return result


class AssemblyGenerator(ASTVisitor):
    """Generates assembly code from AST."""
    
    def __init__(self, ram_start: int = 0x1000, ram_size: int = 0x1000):
        self.instructions: List[Instruction] = []
        self.symbol_table = SymbolTable(ram_start, ram_size)
        self.label_counter = 0
        self.current_function = None
        self.break_labels: List[str] = []
        self.continue_labels: List[str] = []

        self.symbol_table.register_allocator.set_emit_callback(self.emit)
    
    def generate_label(self, prefix: str = "L") -> str:
        """Generate a unique label."""
        label = f"{prefix}{self.label_counter}"
        self.label_counter += 1
        return label
    
    def emit_label(self, label: str) -> None:
        """Emit a label (as a no-op instruction with label)."""
        self.emit(None, comment=f"Label: {label}", label=label)
    
    def emit(self, opcode: Optional[InstructionType], *operands, comment: str = None, label: str = None) -> None:
        """Emit an assembly instruction."""
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
    
    def visit_program(self, node: Program) -> None:
        """Generate code for the entire program."""
        # First pass: collect function declarations
        for decl in node.declarations:
            if isinstance(decl, FunctionDeclaration):
                func_type = FunctionType(
                    decl.return_type,
                    [param.param_type for param in decl.parameters]
                )
                self.symbol_table.define_function(decl.name, func_type)
        
        # Second pass: generate code
        for decl in node.declarations:
            decl.accept(self)
    
    def visit_function_declaration(self, node: FunctionDeclaration) -> None:
        """Generate code for function declaration."""
        self.current_function = node.name

        # Function label
        self.emit(InstructionType.MVR, 0, 0, label=f"func_{node.name}", 
                 comment=f"Function: {node.name}")

        self.symbol_table.enter_scope()

        # Reset parameter register allocation for each function
        if hasattr(self.symbol_table, 'register_allocator'):
            self.symbol_table.register_allocator.next_param_register = self.symbol_table.register_allocator.PARAM_START

        # Define return address as the first parameter (R2)
        ret_addr_symbol = self.symbol_table.define_parameter("__ret_addr", IntType())
        ret_addr_reg = ret_addr_symbol.address

        # Define user parameters
        for param in node.parameters:
            _ = self.symbol_table.define_parameter(param.name, param.param_type)

        node.body.accept(self)

        self.symbol_table.exit_scope()

        # Default return (return 0)
        if not self._ends_with_return(node.body):
            self.emit_immediate(InstructionType.MVR, 0, 0, comment="Default return 0")
            if node.name == "main":
                self.emit(InstructionType.HALT, comment="Halt execution")
            else:
                self.emit(InstructionType.JMP, ret_addr_reg, comment="Return to caller (default)")

        self.current_function = None
    
    def visit_variable_declaration(self, node: VariableDeclaration) -> None:
        """Generate code for variable declaration."""
        symbol = self.symbol_table.define_variable(node.name, node.var_type)
        
        if node.initializer:
            # Generate initializer code
            value_reg = node.initializer.accept(self)
            
            # Store in variable location based on storage type
            if symbol.storage_location == StorageLocation.RAM:
                self.emit(InstructionType.LOAD, value_reg, symbol.address, 
                         comment=f"Initialize {node.name} (RAM)")
            else:  # Register storage
                self.emit(InstructionType.MVR, value_reg, symbol.address, 
                         comment=f"Initialize {node.name} (R{symbol.address})")
    
    def visit_block(self, node: Block) -> None:
        """Generate code for block statement."""
        self.symbol_table.enter_scope()
        
        for stmt in node.statements:
            stmt.accept(self)
        
        self.symbol_table.exit_scope()
    
    def visit_expression_statement(self, node: ExpressionStatement) -> None:
        """Generate code for expression statement."""
        node.expression.accept(self)
    
    def visit_if_statement(self, node: IfStatement) -> None:
        """Generate code for if statement."""
        condition_reg = node.condition.accept(self)
        
        else_label = self.generate_label("els")
        end_label = self.generate_label("endf")
        
        # Jump to else if condition is zero
        self.emit(InstructionType.JZ, else_label, condition_reg, comment="If condition")
        
        # Then branch
        node.then_branch.accept(self)
        self.emit(InstructionType.JMP, end_label, comment="Skip else")
        
        # Else branch
        self.emit(InstructionType.MVR, 0, 0, label=else_label)
        if node.else_branch:
            node.else_branch.accept(self)
        
        # End label
        self.emit(InstructionType.MVR, 0, 0, label=end_label)
    
    def visit_while_statement(self, node: WhileStatement) -> None:
        """Generate code for while statement."""
        loop_label = self.generate_label("wh_lp")
        end_label = self.generate_label("wh_lp_nd")
        
        self.continue_labels.append(loop_label)
        self.break_labels.append(end_label)
        
        # Loop start
        self.emit(InstructionType.MVR, 0, 0, label=loop_label)
        
        # Check condition
        condition_reg = node.condition.accept(self)
        self.emit(InstructionType.JZ, end_label, condition_reg, comment="While condition")
        
        # Loop body
        node.body.accept(self)
        
        # Jump back to start
        self.emit(InstructionType.JMP, loop_label, comment="Loop back")
        
        # End label
        self.emit(InstructionType.MVR, 0, 0, label=end_label)
        
        self.continue_labels.pop()
        self.break_labels.pop()
    
    def visit_for_statement(self, node: ForStatement) -> None:
        """Generate code for for statement."""
        loop_label = self.generate_label("fr_lp")
        continue_label = self.generate_label("fr_cntnu")
        end_label = self.generate_label("fr_lp_nd")
        
        self.continue_labels.append(continue_label)
        self.break_labels.append(end_label)
        
        # Initializer
        if node.initializer:
            node.initializer.accept(self)
        
        # Loop start
        self.emit(InstructionType.MVR, 0, 0, label=loop_label)
        
        # Check condition
        if node.condition:
            condition_reg = node.condition.accept(self)
            self.emit(InstructionType.JZ, end_label, condition_reg, comment="For condition")
        
        # Loop body
        node.body.accept(self)
        
        # Continue point (for continue statements)
        self.emit(InstructionType.MVR, 0, 0, label=continue_label)
        
        # Increment
        if node.increment:
            node.increment.accept(self)
        
        # Jump back to condition
        self.emit(InstructionType.JMP, loop_label, comment="For loop back")
        
        # End label
        self.emit(InstructionType.MVR, 0, 0, label=end_label)
        
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
                temp_reg = self.symbol_table.register_allocator.allocate_register()
                
                # Compare expression with case value
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
                self.emit(InstructionType.MVR, 0, 0, label=default_label)
            else:
                self.emit(InstructionType.MVR, 0, 0, label=case_labels[case_idx])
                case_idx += 1
            
            for stmt in case.statements:
                stmt.accept(self)
        
        # End label
        self.emit(InstructionType.MVR, 0, 0, label=end_label)
        
        self.break_labels.pop()
    
    def visit_return_statement(self, node: ReturnStatement) -> None:
        """Generate code for return statement."""
        # Always use the first parameter register for return address (R2)
        ret_addr_reg = 2
        if node.value:
            return_reg = node.value.accept(self)
            # Move return value to return register (register 0)
            self.emit(InstructionType.MVR, return_reg, 0, comment="Set return value")
        else:
            # Return 0 by default
            self.emit_immediate(InstructionType.MVR, 0, 0, comment="Return 0")
        
        # Jump to function return point or halt if main function
        if self.current_function == "main":
            self.emit(InstructionType.HALT, comment="Halt execution")
        else:
            self.emit(InstructionType.JMP, ret_addr_reg, comment="Return to caller")
    
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
    
    def visit_binary_expression(self, node: BinaryExpression) -> int:
        """Generate code for binary expression and return result register."""
        self.symbol_table.enter_expression_scope()

        left_reg = node.left.accept(self)

        # If left_reg is R0 and will be clobbered by right operand evaluation, save it
        left_in_r0 = (left_reg == 0)
        if left_in_r0:
            temp_left_reg = self.symbol_table.allocate_temporary()
            self.emit(InstructionType.MVR, 0, temp_left_reg, comment="Save ALU result (left operand)")
            left_reg = temp_left_reg

        right_reg = node.right.accept(self)

        # Arithmetic, bitwise, logical, and comparison operations
        if node.operator == BinaryOperator.MODULO:
            # a % b = a - (a / b) * b
            div_reg = self.symbol_table.allocate_temporary()
            self.emit(InstructionType.DIV, left_reg, right_reg, comment="Modulo: a / b")
            self.emit(InstructionType.MVR, 0, div_reg, comment="Save quotient for modulo")
            self.emit(InstructionType.MULT, div_reg, right_reg, comment="Modulo: (a / b) * b")
            mult_reg = self.symbol_table.allocate_temporary()
            self.emit(InstructionType.MVR, 0, mult_reg, comment="Save product for modulo")
            self.emit(InstructionType.SUB, left_reg, mult_reg, comment="Modulo: a - (a / b) * b")
            self.symbol_table.exit_expression_scope()
            return 0
        elif node.operator == BinaryOperator.LOGICAL_AND:
            result_reg = self.symbol_table.allocate_temporary()
            false_label = self.generate_label("lgc_nd_fls")
            end_label = self.generate_label("lgc_nd_nd")
            self.emit(InstructionType.JZ, false_label, left_reg, comment="Logical AND: left zero")
            self.emit(InstructionType.JZ, false_label, right_reg, comment="Logical AND: right zero")
            self.emit_immediate(InstructionType.MVR, 1, result_reg, comment="Logical AND: true")
            self.emit(InstructionType.JMP, end_label)
            self.emit_label(false_label)
            self.emit_immediate(InstructionType.MVR, 0, result_reg, comment="Logical AND: false")
            self.emit(InstructionType.MVR, 0, 0, label=end_label)
            self.symbol_table.exit_expression_scope()
            return result_reg
        elif node.operator == BinaryOperator.LOGICAL_OR:
            result_reg = self.symbol_table.allocate_temporary()
            true_label = self.generate_label("lgc_or_tru")
            end_label = self.generate_label("lgc_or_nd")
            self.emit(InstructionType.JNZ, true_label, left_reg, comment="Logical OR: left nonzero")
            self.emit(InstructionType.JNZ, true_label, right_reg, comment="Logical OR: right nonzero")
            self.emit_immediate(InstructionType.MVR, 0, result_reg, comment="Logical OR: false")
            self.emit(InstructionType.JMP, end_label)
            self.emit_label(true_label)
            self.emit_immediate(InstructionType.MVR, 1, result_reg, comment="Logical OR: true")
            self.emit(InstructionType.MVR, 0, 0, label=end_label)
            self.symbol_table.exit_expression_scope()
            return result_reg
        elif node.operator in [
            BinaryOperator.EQUALS, BinaryOperator.NOT_EQUALS, BinaryOperator.LESS_THAN, BinaryOperator.GREATER_THAN,
            BinaryOperator.LESS_EQUAL, BinaryOperator.GREATER_EQUAL
        ]:
            result_reg = self.symbol_table.allocate_temporary()
            self.emit(InstructionType.SUB, left_reg, right_reg, comment="Comparison")
            true_label = self.generate_label("tru")
            end_label = self.generate_label("cmp_nd")

            if node.operator == BinaryOperator.EQUALS:
                self.emit(InstructionType.JZ, true_label, 0)
            elif node.operator == BinaryOperator.NOT_EQUALS:
                self.emit(InstructionType.JNZ, true_label, 0)
            elif node.operator == BinaryOperator.LESS_THAN:
                temp_reg = self.symbol_table.allocate_temporary()
                self.emit_immediate(InstructionType.MVR, 0x8000, temp_reg, comment="Load sign bit mask")
                self.emit(InstructionType.AND, 0, temp_reg, comment="Check sign bit")
                self.emit(InstructionType.JNZ, true_label, 0, comment="Jump if negative (less than)")
            elif node.operator == BinaryOperator.GREATER_THAN:
                else_label = self.generate_label("nt_grtr")
                self.emit(InstructionType.JZ, else_label, 0, comment="Jump if equal (not greater)")
                temp_reg = self.symbol_table.allocate_temporary()
                self.emit_immediate(InstructionType.MVR, 0x8000, temp_reg, comment="Load sign bit mask")
                self.emit(InstructionType.AND, 0, temp_reg, comment="Check sign bit")
                self.emit(InstructionType.JZ, true_label, 0, comment="Jump if positive (greater than)")
                self.emit_label(else_label)
            elif node.operator == BinaryOperator.LESS_EQUAL:
                self.emit(InstructionType.JZ, true_label, 0, comment="Jump if equal")
                temp_reg = self.symbol_table.allocate_temporary()
                self.emit_immediate(InstructionType.MVR, 0x8000, temp_reg, comment="Load sign bit mask")
                self.emit(InstructionType.AND, 0, temp_reg, comment="Check sign bit")
                self.emit(InstructionType.JNZ, true_label, 0, comment="Jump if negative (less than)")
            elif node.operator == BinaryOperator.GREATER_EQUAL:
                self.emit(InstructionType.JZ, true_label, 0, comment="Jump if equal")
                temp_reg = self.symbol_table.allocate_temporary()
                self.emit_immediate(InstructionType.MVR, 0x8000, temp_reg, comment="Load sign bit mask")
                self.emit(InstructionType.AND, 0, temp_reg, comment="Check sign bit")
                self.emit(InstructionType.JZ, true_label, 0, comment="Jump if positive (greater than)")
            else:
                self.symbol_table.exit_expression_scope()
                raise CodeGenerationError(f"Unsupported comparison operator: {node.operator}")

            self.emit_immediate(InstructionType.MVR, 0, result_reg)
            self.emit(InstructionType.JMP, end_label)
            self.emit_label(true_label)
            self.emit_immediate(InstructionType.MVR, 1, result_reg, comment="True case")
            self.emit(InstructionType.MVR, 0, 0, label=end_label)
            self.symbol_table.exit_expression_scope()
            return result_reg
        else:
            # Arithmetic/bitwise
            op_map = {
                BinaryOperator.ADD: InstructionType.ADD,
                BinaryOperator.SUBTRACT: InstructionType.SUB,
                BinaryOperator.MULTIPLY: InstructionType.MULT,
                BinaryOperator.DIVIDE: InstructionType.DIV,
                BinaryOperator.AND: InstructionType.AND,
                BinaryOperator.OR: InstructionType.OR,
                BinaryOperator.XOR: InstructionType.XOR,
                BinaryOperator.SHIFT_LEFT: InstructionType.SHL,
                BinaryOperator.SHIFT_RIGHT: InstructionType.SHR,
                # Add support for bitwise operators
                BinaryOperator.BITWISE_AND: InstructionType.AND,
                BinaryOperator.BITWISE_OR: InstructionType.OR,
                BinaryOperator.BITWISE_XOR: InstructionType.XOR
            }
            if node.operator in op_map:
                self.emit(op_map[node.operator], left_reg, right_reg, comment=f"{node.operator.value} operation")
                self.symbol_table.exit_expression_scope()
                return 0  # Result in register 0 (ALU output)
            else:
                self.symbol_table.exit_expression_scope()
                raise CodeGenerationError(f"Unsupported binary operator: {node.operator}")
    
    def visit_unary_expression(self, node: UnaryExpression) -> int:
        """Generate code for unary expression and return result register."""
        self.symbol_table.enter_expression_scope()
        operand_reg = node.operand.accept(self)

        if node.operator == UnaryOperator.NEGATE:
            temp_reg = self.symbol_table.allocate_temporary()
            self.emit_immediate(InstructionType.MVR, 0, temp_reg, comment="Load 0 for negation")
            self.emit(InstructionType.SUB, temp_reg, operand_reg, comment="Negate")
            self.symbol_table.exit_expression_scope()
            return 0
        elif node.operator == UnaryOperator.NOT:
            # Bitwise NOT
            self.emit(InstructionType.NOT, operand_reg, comment="Bitwise NOT")
            self.symbol_table.exit_expression_scope()
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
            self.emit(InstructionType.MVR, 0, 0, label=end_label)
            self.symbol_table.exit_expression_scope()
            return result_reg
        elif node.operator == UnaryOperator.ADDRESS_OF:
            symbol_name = getattr(node.operand, 'name', None)
            if symbol_name:
                symbol = self.symbol_table.resolve(symbol_name)
                if symbol:
                    result_reg = self.symbol_table.allocate_temporary()
                    self.emit_immediate(InstructionType.MVR, symbol.address, result_reg, comment=f"Address of {symbol_name}")
                    self.symbol_table.exit_expression_scope()
                    return result_reg
            self.symbol_table.exit_expression_scope()
            raise CodeGenerationError("Cannot take address of expression")
        elif node.operator == UnaryOperator.DEREFERENCE:
            result_reg = self.symbol_table.allocate_temporary()
            self.emit(InstructionType.READ, operand_reg, result_reg, comment="Dereference")
            self.symbol_table.exit_expression_scope()
            return result_reg
        else:
            self.symbol_table.exit_expression_scope()
            raise CodeGenerationError(f"Unsupported unary operator: {node.operator}")
    
    def visit_assignment_expression(self, node: AssignmentExpression) -> int:
        """Generate code for assignment expression."""
        value_reg = node.value.accept(self)
        
        # Handle different assignment targets
        if isinstance(node.target, Identifier):
            symbol = self.symbol_table.resolve(node.target.name)
            if not symbol:
                raise CodeGenerationError(f"Undefined variable: {node.target.name}")
            
            # Get current storage location for the symbol
            target_reg = self.symbol_table.access_symbol(node.target.name)
            
            if symbol.storage_location == StorageLocation.RAM:
                self.emit(InstructionType.LOAD, value_reg, symbol.address, 
                         comment=f"Assign to {node.target.name} (RAM)")
            else:
                self.emit(InstructionType.MVR, value_reg, target_reg, 
                         comment=f"Assign to {node.target.name} (R{target_reg})")
            
            return target_reg
        elif isinstance(node.target, ArrayAccess):
            # Array assignment - simplified
            base_reg = node.target.array.accept(self)
            index_reg = node.target.index.accept(self)
            
            # Calculate address (base + index)
            addr_reg = self.symbol_table.allocate_temporary()
            self.emit(InstructionType.ADD, base_reg, index_reg, comment="Calculate array address")
            self.emit(InstructionType.MVR, 0, addr_reg)  # Move ALU result to addr_reg
            
            # Store value
            self.emit(InstructionType.LOAD, value_reg, addr_reg, comment="Array assignment")
            return value_reg
        elif isinstance(node.target, UnaryExpression) and node.target.operator == UnaryOperator.DEREFERENCE:
            # Pointer dereference assignment: *ptr = value
            ptr_reg = node.target.operand.accept(self)
            
            # Store value at address contained in ptr_reg
            self.emit(InstructionType.LOAD, value_reg, ptr_reg, comment="Pointer dereference assignment")
            return ptr_reg
        else:
            raise CodeGenerationError(f"Invalid assignment target: {type(node.target)}")
    
    def visit_function_call(self, node: FunctionCall) -> int:
        """Generate code for function call."""
        # Allocate a temporary register for the return address
        ret_addr_reg = 2  # Always use R2 for return address
        # Set return address to the instruction after the call
        after_call_label = self.generate_label("aftr_cll")
        self.emit_immediate(InstructionType.MVR, after_call_label, ret_addr_reg, comment="Set return address")
        # Pass arguments in registers 3+
        for i, arg in enumerate(node.arguments):
            arg_reg = arg.accept(self)
            param_reg = 3 + i
            self.emit(InstructionType.MVR, arg_reg, param_reg, 
                     comment=f"Pass argument {i}")
        # Call function
        if isinstance(node.function, Identifier):
            self.emit(InstructionType.JAL, f"func_{node.function.name}", 
                     comment=f"Call {node.function.name}")
        else:
            # Function pointer call - more complex
            func_reg = node.function.accept(self)
            self.emit(InstructionType.JAL, func_reg, comment="Call function pointer")
        # After call label
        self.emit_label(after_call_label)
        # Return value is in register 0
        return 0
    
    def visit_gpu_function_call(self, node) -> int:
        """Generate code for GPU built-in function calls."""
        from .ast_nodes import GPUFunctionCall
        
        # Evaluate arguments
        arg_regs = []
        for arg in node.arguments:
            reg = arg.accept(self)
            arg_regs.append(reg)
        
        # Direct codegen for setGPUBuffer and getGPUBuffer (no branching)
        if node.function_name == 'setGPUBuffer':
            # setGPUBuffer(buffer_id, value)
            # buffer_id: 0 (edit), 1 (display)
            # value: 0 or 1
            if len(arg_regs) != 2:
                raise CodeGenerationError("setGPUBuffer requires 2 arguments")
            buffer_id_reg = arg_regs[0]
            value_reg = arg_regs[1]
            self.emit(InstructionType.MVR, 'GPU', 0, comment="Load GPU register")
            # If buffer_id is immediate (0 or 1), emit direct mask ops
            if hasattr(node.arguments[0], 'value'):
                buf_id = node.arguments[0].value
                if buf_id == 0:
                    # Edit buffer: clear bit 1, OR with (value << 1)
                    self.emit(InstructionType.AND, 0, 'i:0xFFFFFFFD', comment="Clear bit 1 (edit)")
                    self.emit(InstructionType.SHL, value_reg, 'i:1', comment="Shift value for edit buffer")
                    self.emit(InstructionType.OR, 0, 0, comment="Set edit buffer bit")
                elif buf_id == 1:
                    # Display buffer: clear bit 0, OR with value
                    self.emit(InstructionType.AND, 0, 'i:0xFFFFFFFE', comment="Clear bit 0 (display)")
                    self.emit(InstructionType.OR, 0, value_reg, comment="Set display buffer bit")
                else:
                    raise CodeGenerationError("Invalid buffer_id for setGPUBuffer (must be 0 or 1)")
            else:
                # Dynamic buffer_id: use conditional masking
                # Mask for edit: (buffer_id == 0)
                # Mask for display: (buffer_id == 1)
                # This is a fallback for non-constant buffer_id
                # Clear both bits, then OR with ((value << buffer_id) & (1 << buffer_id))
                self.emit(InstructionType.AND, 0, 'i:0xFFFFFFFC', comment="Clear both buffer bits")
                self.emit(InstructionType.SHL, value_reg, buffer_id_reg, comment="Shift value by buffer_id")
                self.emit(InstructionType.OR, 0, 0, comment="Set buffer bit dynamically")
            self.emit(InstructionType.MVR, 0, 'GPU', comment="Update GPU register")
            return 0
        elif node.function_name == 'getGPUBuffer':
            # getGPUBuffer(buffer_id)
            # buffer_id: 0 (edit), 1 (display)
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
                    raise CodeGenerationError("Invalid buffer_id for getGPUBuffer (must be 0 or 1)")
            else:
                # Dynamic buffer_id: (GPU >> buffer_id) & 1
                self.emit(InstructionType.SHR, 0, buffer_id_reg, comment="Shift right by buffer_id")
                self.emit(InstructionType.AND, 0, 'i:1', comment="Mask buffer bit dynamically")
            return 0
        # Default: other GPU built-ins
        gpu_func_map = {
            'drawLine': InstructionType.DRLINE,
            'fillGrid': InstructionType.DRGRD,
            'clearGrid': InstructionType.CLRGRID,
            'loadSprite': InstructionType.LDSPR,
            'drawSprite': InstructionType.DRSPR,
            'loadText': InstructionType.LDTXT,
            'drawText': InstructionType.DRTXT,
            'scrollBuffer': InstructionType.SCRLBFR
        }
        if node.function_name not in gpu_func_map:
            raise CodeGenerationError(f"Unknown GPU function: {node.function_name}")
        instruction_type = gpu_func_map[node.function_name]
        immediate_args = []
        for i, reg in enumerate(arg_regs):
            if hasattr(node.arguments[i], 'value'):
                immediate_args.append(f"i:{node.arguments[i].value}")
            else:
                immediate_args.append(reg)
        if immediate_args:
            self.emit(instruction_type, *immediate_args, comment=f"GPU: {node.function_name}")
        else:
            self.emit(instruction_type, comment=f"GPU: {node.function_name}")
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
                # Constant size allocation
                size = size_expr.value
                
                # Allocate memory using memory manager
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
                # Runtime size allocation - not supported in compile-time memory management
                raise CodeGenerationError("malloc with runtime size not supported - size must be compile-time constant")
        
        elif node.function_name == "free":
            # free(ptr) - free memory pointed to by pointer
            if len(node.arguments) != 1:
                raise CodeGenerationError("free requires exactly 1 argument (pointer)")
            
            ptr_reg = node.arguments[0].accept(self)
            
            # For compile-time memory management, we need to track which allocation this corresponds to
            # This is a simplified implementation - in practice, you'd want more sophisticated tracking
            
            # Generate a comment for the free operation
            self.emit(InstructionType.MVR, 0, 0, comment=f"free(R{ptr_reg}) - memory deallocated at compile time")
            
            # Note: The actual freeing happens at compile time through the memory manager
            # The runtime code doesn't need to do anything since memory layout is predetermined
            
            return 0  # free returns void
        
        else:
            raise CodeGenerationError(f"Unknown memory function: {node.function_name}")
    
    def visit_array_access(self, node: ArrayAccess) -> int:
        """Generate code for array access."""
        base_reg = node.array.accept(self)
        index_reg = node.index.accept(self)
        
        # Calculate address (base + index)
        self.emit(InstructionType.ADD, base_reg, index_reg, comment="Array index calculation")
        
        # Load value from calculated address (ALU result in R0)
        result_reg = self.symbol_table.allocate_temporary()
        self.emit(InstructionType.READ, 0, result_reg, comment="Load array element")
        
        return result_reg
    
    def visit_integer_literal(self, node: IntegerLiteral) -> int:
        """Generate code for integer literal."""
        result_reg = self.symbol_table.allocate_temporary()
        self.emit_immediate(InstructionType.MVR, node.value, result_reg, 
                           comment=f"Load literal {node.value}")
        return result_reg
    
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
            # Return function address for function pointers
            result_reg = self.symbol_table.allocate_temporary()
            self.emit_immediate(InstructionType.MVR, f"func_{node.name}", result_reg, 
                               comment=f"Function pointer {node.name}")
            return result_reg
        else:
            # Variable or parameter - use symbol table to access
            if symbol.storage_location == StorageLocation.RAM:
                # Load from RAM
                result_reg = self.symbol_table.allocate_temporary()
                self.emit(InstructionType.READ, symbol.address, result_reg, 
                         comment=f"Load {node.name} from RAM")
                return result_reg
            else:
                # In register - get current register location
                return self.symbol_table.access_symbol(node.name)
    
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


class CodeGenerationError(Exception):
    """Exception raised for code generation errors."""
    pass


def generate_assembly(ast: Program, ram_start: int = 0x1000, ram_size: int = 0x1000) -> str:
    """Generate assembly code from AST."""
    generator = AssemblyGenerator(ram_start, ram_size)
    generator.visit_program(ast)
    return generator.get_assembly_code()