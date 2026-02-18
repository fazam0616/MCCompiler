"""MCL Symbol Table and Memory Management

Manages symbols (variables, functions), register allocation with spilling,
and RAM memory management during compilation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Set
from enum import Enum
import bisect
from .ast_nodes import Type, IntType, PointerType, ArrayType, FunctionType


class SymbolKind(Enum):
    VARIABLE = "variable"
    FUNCTION = "function"
    PARAMETER = "parameter"
    ARRAY = "array"
    TEMPORARY = "temporary"


class StorageLocation(Enum):
    REGISTER = "register"
    RAM = "ram"
    SPILLED = "spilled"  # Register value stored in RAM temporarily
    STACK = "stack"    # Value in stack frame, accessed via FP-relative offset


@dataclass
class Symbol:
    """Represents a symbol in the symbol table."""
    name: str  # Original user-facing name
    symbol_type: Type
    kind: SymbolKind
    storage_location: StorageLocation = StorageLocation.REGISTER
    address: Optional[int] = None  # Register number or RAM address
    size: int = 1  # Size in memory units (for arrays)
    is_global: bool = False
    is_live: bool = True  # Whether symbol is currently needed
    line: int = 0
    column: int = 0
    scoped_name: Optional[str] = None  # Internal scoped name for register allocation
    scope_level: int = 0  # Scope depth level
    scope_id: int = 0  # Unique scope identifier
    frame_offset: Optional[int] = None  # FP-relative offset for STACK storage
    
    def is_in_register(self) -> bool:
        return self.storage_location == StorageLocation.REGISTER
    
    def is_in_ram(self) -> bool:
        return self.storage_location in [StorageLocation.RAM, StorageLocation.SPILLED]
    
    def is_on_stack(self) -> bool:
        return self.storage_location == StorageLocation.STACK


@dataclass
class MemorySegment:
    """Memory management segment for RAM allocation."""
    start_address: int
    end_address: int
    stored_symbol: str = ""  # Empty string means free
    prev_neighbor: Optional['MemorySegment'] = None
    next_neighbor: Optional['MemorySegment'] = None
    
    @property
    def size(self) -> int:
        return self.end_address - self.start_address + 1
    
    @property
    def is_free(self) -> bool:
        return self.stored_symbol == ""
    
    def __lt__(self, other: 'MemorySegment') -> bool:
        return self.start_address < other.start_address


class Scope:
    """Represents a lexical scope with register allocation tracking."""
    
    def __init__(self, parent: Optional['Scope'] = None, register_allocator: Optional['RegisterAllocator'] = None, scope_id: int = 0):
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.register_allocator = register_allocator
        self.live_symbols: Set[str] = set()  # Symbols needed in this scope
        self.scope_registers: Dict[str, int] = {}  # Registers allocated for this scope
        self.scope_id = scope_id  # Unique identifier for this scope
        self.level = 0 if parent is None else parent.level + 1  # Depth level
    
    def define(self, symbol: Symbol, register_allocator: 'RegisterAllocator') -> None:
        """Define a symbol in this scope."""
        if symbol.name in self.symbols:
            raise SymbolError(f"Symbol '{symbol.name}' already defined in this scope")
        
        self.symbols[symbol.name] = symbol
        self.live_symbols.add(symbol.name)
    
    def lookup(self, name: str) -> Optional[Symbol]:
        """Look up a symbol in this scope (not parent scopes)."""
        return self.symbols.get(name)
    
    def resolve(self, name: str) -> Optional[Symbol]:
        """Resolve a symbol in this scope or parent scopes."""
        symbol = self.lookup(name)
        if symbol is not None:
            return symbol
        
        if self.parent is not None:
            return self.parent.resolve(name)
        
        return None
    
    def enter_scope(self, register_allocator: 'RegisterAllocator') -> None:
        """Prepare registers for entering this scope."""
        if not self.live_symbols:
            return
        
        # Ensure all live symbols are in registers
        required_symbols = list(self.live_symbols)
        self.scope_registers = register_allocator.get_registers_for_scope(required_symbols)
    
    def exit_scope(self, register_allocator: 'RegisterAllocator') -> None:
        """Clean up registers when exiting this scope."""
        # Free registers for local symbols that go out of scope
        for symbol_name in self.symbols:
            if symbol_name in register_allocator.symbol_to_register:
                symbol = self.symbols[symbol_name]
                if not symbol.is_global:  # Only free local symbols
                    register_allocator.free_register(
                        register_allocator.symbol_to_register[symbol_name]
                    )
    
    def add_live_symbol(self, symbol_name: str) -> None:
        """Mark a symbol as live (needed) in this scope."""
        self.live_symbols.add(symbol_name)
    
    def remove_live_symbol(self, symbol_name: str) -> None:
        """Mark a symbol as no longer needed in this scope."""
        self.live_symbols.discard(symbol_name)


class SymbolError(Exception):
    """Exception raised for symbol table errors."""
    pass


class MemoryManager:
    """Segregated free list memory manager with exponential size buckets."""
    
    def __init__(self, ram_start: int = 0x1000, ram_size: int = 0x1000):
        self.ram_start = ram_start
        self.ram_end = ram_start + ram_size - 1
        
        # Hash table mapping symbol names to segments
        self.symbol_to_segment: Dict[str, MemorySegment] = {}
        
        # Exponential size buckets: 1-4, 5-16, 17-64, 65+
        self.size_buckets = {
            0: (1, 4),      # Bucket 0: sizes 1-4
            1: (5, 16),     # Bucket 1: sizes 5-16  
            2: (17, 64),    # Bucket 2: sizes 17-64
            3: (65, float('inf'))  # Bucket 3: sizes 65+
        }
        
        # Each bucket contains segments sorted by start address
        self.bucket_to_segments: Dict[int, List[MemorySegment]] = {
            0: [], 1: [], 2: [], 3: []
        }
        
        # Initialize with one large free segment
        initial_segment = MemorySegment(self.ram_start, self.ram_end)
        self._add_to_bucket(initial_segment)
    
    def allocate_memory(self, symbol_name: str, size: int) -> Optional[int]:
        """Allocate memory for a symbol and return start address."""
        segment = self._find_suitable_segment(size)
        if not segment:
            return None
        
        # Remove from free lists
        self._remove_from_bucket(segment)
        
        if segment.size > size:
            self._split_segment(segment, size)
        
        # Mark as allocated
        segment.stored_symbol = symbol_name
        self.symbol_to_segment[symbol_name] = segment
        
        return segment.start_address
    
    def free_memory(self, symbol_name: str) -> bool:
        """Free memory for a symbol and coalesce with neighbors."""
        if symbol_name not in self.symbol_to_segment:
            return False
        
        segment = self.symbol_to_segment[symbol_name]
        
        # Mark as free
        segment.stored_symbol = ""
        del self.symbol_to_segment[symbol_name]
        
        # Coalesce with neighbors
        coalesced_segment = self._coalesce_segment(segment)
        
        self._add_to_bucket(coalesced_segment)
        
        return True
    
    def _find_suitable_segment(self, size: int) -> Optional[MemorySegment]:
        """Find a segment of suitable size using exponential bucket search."""
        target_bucket = self._get_size_bucket(size)
        
        best_segment = self._find_best_fit_in_bucket(target_bucket, size)
        if best_segment:
            return best_segment
        
        # If not found, search larger buckets in order
        for bucket_id in range(target_bucket + 1, len(self.size_buckets)):
            segments = self.bucket_to_segments[bucket_id]
            if segments:
                best_segment = self._find_best_fit_in_bucket(bucket_id, size)
                if best_segment:
                    return best_segment
        
        return None
    
    def _split_segment(self, segment: MemorySegment, allocation_size: int) -> None:
        """Split a segment into allocated and free parts."""
        if segment.size <= allocation_size:
            return
        
        # Create new segment for remainder
        remainder_start = segment.start_address + allocation_size
        remainder = MemorySegment(
            start_address=remainder_start,
            end_address=segment.end_address,
            prev_neighbor=segment,
            next_neighbor=segment.next_neighbor
        )
        
        # Update original segment
        segment.end_address = segment.start_address + allocation_size - 1
        segment.next_neighbor = remainder
        
        # Update neighbor links
        if remainder.next_neighbor:
            remainder.next_neighbor.prev_neighbor = remainder
        
        # Add remainder to free lists
        self._add_to_bucket(remainder)
    
    def _coalesce_segment(self, segment: MemorySegment) -> MemorySegment:
        """Coalesce segment with free neighbors."""
        current = segment
        
        # Coalesce with previous neighbors
        while current.prev_neighbor and current.prev_neighbor.is_free:
            prev_seg = current.prev_neighbor
            self._remove_from_bucket(prev_seg)
            
            # Merge segments
            prev_seg.end_address = current.end_address
            prev_seg.next_neighbor = current.next_neighbor
            
            if current.next_neighbor:
                current.next_neighbor.prev_neighbor = prev_seg
            
            current = prev_seg
        
        # Coalesce with next neighbors
        while current.next_neighbor and current.next_neighbor.is_free:
            next_seg = current.next_neighbor
            self._remove_from_bucket(next_seg)
            
            # Merge segments
            current.end_address = next_seg.end_address
            current.next_neighbor = next_seg.next_neighbor
            
            if next_seg.next_neighbor:
                next_seg.next_neighbor.prev_neighbor = current
        
        return current
    
    def _add_to_bucket(self, segment: MemorySegment) -> None:
        """Add segment to appropriate size bucket."""
        bucket_id = self._get_size_bucket(segment.size)
        
        # Insert in sorted order by start address
        bisect.insort(self.bucket_to_segments[bucket_id], segment)
    
    def _remove_from_bucket(self, segment: MemorySegment) -> None:
        """Remove segment from its size bucket."""
        bucket_id = self._get_size_bucket(segment.size)
        
        try:
            self.bucket_to_segments[bucket_id].remove(segment)
        except ValueError:
            pass  # Segment not in list
    
    def _get_size_bucket(self, size: int) -> int:
        """Get the bucket ID for a given size."""
        for bucket_id, (min_size, max_size) in self.size_buckets.items():
            if min_size <= size <= max_size:
                return bucket_id
        # Fallback to largest bucket
        return max(self.size_buckets.keys())
    
    def _find_best_fit_in_bucket(self, bucket_id: int, required_size: int) -> Optional[MemorySegment]:
        """Find the best-fit segment within a specific bucket."""
        segments = self.bucket_to_segments[bucket_id]
        best_segment = None
        best_size = float('inf')
        
        for segment in segments:
            if segment.size >= required_size and segment.size < best_size:
                best_segment = segment
                best_size = segment.size
                
                # If we found an exact match, use it immediately
                if segment.size == required_size:
                    break
        
        return best_segment
    
    def get_memory_usage(self) -> Dict[str, any]:
        """Get memory usage statistics."""
        total_allocated = sum(seg.size for seg in self.symbol_to_segment.values())
        total_free = sum(sum(seg.size for seg in segments) for segments in self.bucket_to_segments.values())
        total_memory = self.ram_end - self.ram_start + 1
        
        # Calculate fragmentation stats per bucket
        bucket_stats = {}
        for bucket_id, segments in self.bucket_to_segments.items():
            min_size, max_size = self.size_buckets[bucket_id]
            bucket_stats[f'bucket_{bucket_id}_{min_size}-{max_size}'] = {
                'segments': len(segments),
                'total_size': sum(seg.size for seg in segments)
            }
        
        return {
            'total': total_memory,
            'allocated': total_allocated,
            'free': total_free,
            'bucket_stats': bucket_stats,
            'total_free_segments': sum(len(segs) for segs in self.bucket_to_segments.values())
        }


class SymbolTable:
    """Enhanced symbol table manager with advanced memory management."""
    
    def __init__(self, ram_start: int = 0x1000, ram_size: int = 0x1000):
        self.memory_manager = MemoryManager(ram_start, ram_size)
        self.register_allocator = RegisterAllocator(self.memory_manager, self)
        
        self.global_scope = Scope(register_allocator=self.register_allocator, scope_id=0)
        self.current_scope = self.global_scope
        
        # Track global memory allocation
        self.next_global_address = ram_start

        # Expression scope stack for temporary register management
        self.expression_scope_stack: List[Set[int]] = []
        
        # Scope ID counter for generating unique scope identifiers
        self.next_scope_id = 1
        
        # Function depth tracking for recursion
        self.current_function_name = None
        self.function_call_depth: Dict[str, int] = {}  # function_name -> current depth
    
    def enter_scope(self) -> None:
        """Enter a new scope."""
        new_scope = Scope(self.current_scope, self.register_allocator, self.next_scope_id)
        self.next_scope_id += 1
        new_scope.enter_scope(self.register_allocator)
        self.current_scope = new_scope
    
    def exit_scope(self) -> None:
        """Exit the current scope."""
        if self.current_scope.parent is not None:
            self.current_scope.exit_scope(self.register_allocator)
            self.current_scope = self.current_scope.parent
        else:
            raise SymbolError("Cannot exit global scope")
    
    def _create_scoped_name(self, name: str) -> str:
        """Create a scoped name for a symbol to ensure unique register allocation.
        
        Format: varname$scope{scope_id}$level{level}
        This prevents variable shadowing issues and helps with recursion tracking.
        """
        scope_id = self.current_scope.scope_id
        level = self.current_scope.level
        return f"{name}$scope{scope_id}$level{level}"
    
    def define_variable(self, name: str, var_type: Type, line: int = 0, column: int = 0) -> Symbol:
        """Define a variable with intelligent storage allocation."""
        is_global = (self.current_scope == self.global_scope)
        
        # Create scoped name for register allocation
        # Format: varname$scope{scope_id}$level{level}
        scoped_name = self._create_scoped_name(name)
        
        # Determine storage requirements
        if isinstance(var_type, ArrayType):
            # Arrays always go to RAM
            size = var_type.size if hasattr(var_type, 'size') else 10  # Default size
            ram_addr = self.memory_manager.allocate_memory(scoped_name, size)
            if ram_addr is None:
                raise SymbolError(f"Cannot allocate RAM for array {name}")
            
            symbol = Symbol(
                name=name,
                symbol_type=var_type,
                kind=SymbolKind.ARRAY,
                storage_location=StorageLocation.RAM,
                address=ram_addr,
                size=size,
                is_global=is_global,
                line=line,
                column=column,
                scoped_name=scoped_name,
                scope_level=self.current_scope.level,
                scope_id=self.current_scope.scope_id
            )
        else:
            # Regular variables - try register first
            if is_global:
                # Global variables go to RAM
                ram_addr = self.memory_manager.allocate_memory(scoped_name, 1)
                if ram_addr is None:
                    raise SymbolError(f"Cannot allocate RAM for global variable {name}")
                
                symbol = Symbol(
                    name=name,
                    symbol_type=var_type,
                    kind=SymbolKind.VARIABLE,
                    storage_location=StorageLocation.RAM,
                    address=ram_addr,
                    size=1,
                    is_global=True,
                    line=line,
                    column=column,
                    scoped_name=scoped_name,
                    scope_level=self.current_scope.level,
                    scope_id=self.current_scope.scope_id
                )
            else:
                # Local variables - try register allocation using scoped name
                reg = self.register_allocator.allocate_register_for_symbol(scoped_name, False)
                if reg is not None:
                    symbol = Symbol(
                        name=name,
                        symbol_type=var_type,
                        kind=SymbolKind.VARIABLE,
                        storage_location=StorageLocation.REGISTER,
                        address=reg,
                        size=1,
                        is_global=False,
                        line=line,
                        column=column,
                        scoped_name=scoped_name,
                        scope_level=self.current_scope.level,
                        scope_id=self.current_scope.scope_id
                    )
                else:
                    # Fall back to RAM if no registers available
                    ram_addr = self.memory_manager.allocate_memory(scoped_name, 1)
                    if ram_addr is None:
                        raise SymbolError(f"Cannot allocate storage for variable {name}")
                    
                    symbol = Symbol(
                        name=name,
                        symbol_type=var_type,
                        kind=SymbolKind.VARIABLE,
                        storage_location=StorageLocation.RAM,
                        address=ram_addr,
                        size=1,
                        is_global=False,
                        line=line,
                        column=column,
                        scoped_name=scoped_name,
                        scope_level=self.current_scope.level,
                        scope_id=self.current_scope.scope_id
                    )
        
        self.current_scope.define(symbol, self.register_allocator)
        return symbol
    
    def define_function(self, name: str, func_type: FunctionType, line: int = 0, column: int = 0) -> Symbol:
        """Define a function in the global scope."""
        symbol = Symbol(
            name=name,
            symbol_type=func_type,
            kind=SymbolKind.FUNCTION,
            storage_location=StorageLocation.RAM,  # Function code in RAM
            address=None,  # Will be resolved during assembly
            is_global=True,
            line=line,
            column=column,
            scoped_name=name,  # Functions use their original name
            scope_level=0,
            scope_id=0
        )
        
        self.global_scope.define(symbol, self.register_allocator)
        return symbol
    
    def define_parameter(self, name: str, param_type: Type, line: int = 0, column: int = 0) -> Symbol:
        """Define a function parameter."""
        # Create scoped name for parameter
        scoped_name = self._create_scoped_name(name)
        
        reg = self.register_allocator.allocate_register_for_symbol(scoped_name, True)
        if reg is None:
            raise SymbolError(f"Cannot allocate register for parameter {name}")
        
        symbol = Symbol(
            name=name,
            symbol_type=param_type,
            kind=SymbolKind.PARAMETER,
            storage_location=StorageLocation.REGISTER,
            address=reg,
            is_global=False,
            line=line,
            column=column,
            scoped_name=scoped_name,
            scope_level=self.current_scope.level,
            scope_id=self.current_scope.scope_id
        )
        
        self.current_scope.define(symbol, self.register_allocator)
        return symbol
    
    def resolve(self, name: str) -> Optional[Symbol]:
        """Resolve a symbol by name."""
        return self.current_scope.resolve(name)
    
    def prepare_for_statement(self, required_symbols: List[str]) -> Dict[str, int]:
        """Prepare registers for a statement that needs specific symbols."""
        return self.register_allocator.get_registers_for_scope(required_symbols)
    
    def allocate_temporary(self) -> int:
        """Allocate a temporary register for calculations."""
        reg = self.register_allocator.allocate_temporary_register()
        if reg is None:
            raise SymbolError("Cannot allocate temporary register")
        
        # Track in current expression scope if one exists
        if self.expression_scope_stack:
            self.expression_scope_stack[-1].add(reg)
            
        return reg
    
    def enter_expression_scope(self) -> None:
        """Enter a new expression scope for temporary register management."""
        self.expression_scope_stack.append(set())
        # Also enter a register allocation scope
        self.register_allocator.enter_register_scope()
        print(' '*len(self.expression_scope_stack)+"Entering new expression scope: ", len(self.expression_scope_stack))
    
    def exit_expression_scope(self) -> None:
        """Exit the current expression scope and free its temporary registers."""
        if not self.expression_scope_stack:
            return
            
        print(' '*len(self.expression_scope_stack)+"Exiting expression scope: ", len(self.expression_scope_stack))

        temp_registers = self.expression_scope_stack.pop()
        for reg in temp_registers:
            self.register_allocator.free_temporary_register(reg)
        
        # Also exit the register allocation scope
        self.register_allocator.exit_register_scope()
    
    def define_variable_on_stack(self, name: str, var_type: Type, frame_offset: int,
                                   line: int = 0, column: int = 0) -> Symbol:
        """Define a local variable stored in the current stack frame."""
        scoped_name = self._create_scoped_name(name)
        symbol = Symbol(
            name=name,
            symbol_type=var_type,
            kind=SymbolKind.VARIABLE,
            storage_location=StorageLocation.STACK,
            address=None,
            frame_offset=frame_offset,
            is_global=False,
            line=line,
            column=column,
            scoped_name=scoped_name,
            scope_level=self.current_scope.level,
            scope_id=self.current_scope.scope_id
        )
        self.current_scope.define(symbol, self.register_allocator)
        return symbol

    def define_parameter_on_stack(self, name: str, param_type: Type, frame_offset: int,
                                    line: int = 0, column: int = 0) -> Symbol:
        """Define a function parameter stored in the current stack frame."""
        scoped_name = self._create_scoped_name(name)
        symbol = Symbol(
            name=name,
            symbol_type=param_type,
            kind=SymbolKind.PARAMETER,
            storage_location=StorageLocation.STACK,
            address=None,
            frame_offset=frame_offset,
            is_global=False,
            line=line,
            column=column,
            scoped_name=scoped_name,
            scope_level=self.current_scope.level,
            scope_id=self.current_scope.scope_id
        )
        self.current_scope.define(symbol, self.register_allocator)
        return symbol

    def get_memory_stats(self) -> Dict[str, any]:
        """Get comprehensive memory usage statistics."""
        return {
            'ram': self.memory_manager.get_memory_usage(),
            'registers': self.register_allocator.get_register_usage_stats()
        }


class RegisterAllocator:
    """Advanced register allocator with spilling support."""
    
    def __init__(self, memory_manager: MemoryManager, symbol_table: SymbolTable = None):
        self.memory_manager = memory_manager
        
        # Register allocation strategy
        self.ALU_REGISTERS = {0, 1}  # R0, R1 for ALU operations  
        self.PARAM_START = 6  # R6+ for temporaries (R2=ret addr, R3=SP, R4=FP, R5=epilogue-save)
        self.LOCAL_START = 31  # R31, R30, R29, ... for local calculations
        self.MAX_REGISTERS = 32
        self.RESERVED_REGISTERS = {0, 1, 2, 3, 4, 5}  # Never allocate these
        
        # Track register usage
        self.register_to_symbol = {}  # reg -> symbol name
        self.symbol_to_register = {}  # symbol -> reg
        self.register_usage_count = {}  # access frequency
        self.spilled_symbols = {}  # symbol -> RAM address
        
        # Temporary register tracking
        self.temporary_registers = set()  # Registers allocated for temporaries
        self.temp_register_counter = 0  # Counter for generating unique temp names
        
        # Available registers for local allocation (counting down from R31)
        self.next_local_register = 31
        
        # Parameter register allocation (counting up from R2)
        self.next_param_register = 2
        
        # Each scope has a set of available registers
        self.register_availability_stack = []
        
        # Initialize with all allocatable registers (excluding reserved registers)
        initial_available = set(range(self.PARAM_START, self.MAX_REGISTERS)) - self.RESERVED_REGISTERS
        self.register_availability_stack.append(initial_available)
        
        # Maps register -> scope depth where it was allocated
        self.register_scope_depth = {}
        
        # Maps register -> set of symbols that depend on its value
        self.register_live_uses = {}
        
        # Track which registers hold values that haven't been consumed yet
        self.live_registers = set()
        self.symbol_table = symbol_table
    
    def allocate_register_for_symbol(self, symbol_name: str, is_parameter: bool = False) -> Optional[int]:
        """Allocate a register for a symbol, with spilling if needed."""
        if symbol_name in self.symbol_to_register:
            return self.symbol_to_register[symbol_name]
        
        # Try to allocate register
        if is_parameter:
            reg = self._allocate_parameter_register()
        else:
            reg = self._allocate_local_register()
        
        if reg is not None:
            self._assign_register_to_symbol(reg, symbol_name)
            
            # Mark as used in current scope
            self.mark_register_used(reg)
            
            # Track scope depth
            self.register_scope_depth[reg] = len(self.register_availability_stack) - 1
            
            return reg
        
        # No registers available - need to spill
        return self._spill_and_allocate(symbol_name, is_parameter)
    
    def allocate_temporary_register(self) -> Optional[int]:
        """Allocate a temporary register for calculations."""
        # Try to allocate from available registers in current scope
        available = self.get_available_registers()
        
        # Filter out live registers and already allocated registers
        candidate_registers = available - self.live_registers - set(self.register_to_symbol.keys())
        
        if candidate_registers:
            # Prefer higher-numbered registers for temporaries (R31, R30, ...)
            reg = max(candidate_registers)
        else:
            # Fall back to spill-allocation
            reg = None
        
        if reg is not None:
            # Create a unique temporary symbol name
            temp_name = f"__temp_{self.temp_register_counter}"
            self.temp_register_counter += 1

            # Track as temporary register
            self.temporary_registers.add(reg)
            self._assign_register_to_symbol(reg, temp_name)

            # Mark as used in current scope
            self.mark_register_used(reg)

            # Track scope depth
            self.register_scope_depth[reg] = len(self.register_availability_stack) - 1

            return reg

        # Spill least recently used register
        return self._spill_lru_and_allocate()
    
    def free_temporary_register(self, register: int) -> None:
        """Free a temporary register."""
        if register in self.temporary_registers:
            # Unmark live first so the slot is fully available for reuse.
            self.mark_register_consumed(register)
            self.temporary_registers.remove(register)
            self._free_register_internal(register, True)

            # Allow the register to be reused by moving the counter back if appropriate
            # Only reset if this register is higher than the current counter
            if register > self.next_local_register:
                self.next_local_register = register
    
    def free_register(self, register: int) -> None:
        """Free a register (public interface)."""
        self._free_register_internal(register, False)

        
    def set_emit_callback(self, callback):
        """Set a callback for emitting assembly instructions (opcode, *args, comment=None)."""
        self._emit_callback = callback
    
    def _free_register_internal(self, register: int, delete_symbol: bool = False) -> None:
        """Internal method to free a register and update tracking."""
        if register in self.register_to_symbol and delete_symbol:
            symbol = self.register_to_symbol[register]
            del self.register_to_symbol[register]
            del self.symbol_to_register[symbol]
            del self.register_usage_count[register]
            print(' ' * (len(self.symbol_table.expression_scope_stack) ) + f"Freed symbol {symbol} in R{register} ")
        
        self.mark_register_available(register)
        
        self.mark_register_consumed(register)
        
        # Remove scope depth tracking
        if register in self.register_scope_depth:
            del self.register_scope_depth[register]
    
    def access_symbol(self, symbol_name: str) -> int:
        """Access a symbol, loading from RAM if spilled or stored in RAM."""
        # Use symbol table to resolve symbol
        symbol: Optional[Symbol] = None
        if self.symbol_table:
            symbol = self.symbol_table.current_scope.resolve(symbol_name)
        
        # Use scoped name for register lookups if available
        lookup_name = symbol.scoped_name if symbol and symbol.scoped_name else symbol_name

        # If in register, update usage and return
        if lookup_name in self.symbol_to_register:
            reg = self.symbol_to_register[lookup_name]
            self.register_usage_count[reg] = self.register_usage_count.get(reg, 0) + 1
            return reg

        # If spilled, need to load back into register
        if lookup_name in self.spilled_symbols or (symbol and symbol.is_in_ram()):
            reg = self.allocate_register_for_symbol(lookup_name, False)
            if reg is None:
                raise RuntimeError(f"Cannot allocate register for spilled symbol {symbol_name}")
            if (symbol and symbol.is_in_ram()):
                ram_addr = symbol.address
            else:
                ram_addr = self.spilled_symbols[lookup_name]
                print(f"Reloading spilled symbol {symbol_name} from RAM address {ram_addr} into register R{reg}")
            if hasattr(self, '_emit_callback') and self._emit_callback:
                self._emit_callback('READ', f'i:{ram_addr}', reg, comment=f"Reload {symbol_name} from RAM")
            self._assign_register_to_symbol(reg, lookup_name)
            self.mark_register_used(reg)
            self.register_scope_depth[reg] = len(self.register_availability_stack) - 1
            self.mark_register_live(reg, lookup_name)
            if lookup_name in self.spilled_symbols:
                del self.spilled_symbols[lookup_name]
            return reg

        raise RuntimeError(f"Symbol {symbol_name} not found in registers, spilled memory, or RAM")
    
    def spill_symbol(self, symbol_name: str) -> bool:
        """Spill a symbol from register to RAM."""
        if symbol_name not in self.symbol_to_register:
            return False

        reg = self.symbol_to_register[symbol_name]


        # # Check if register is live
        # if self.is_register_live(reg):
        #     pass 

        # Allocate RAM for spilled symbol
        ram_addr = self.memory_manager.allocate_memory(f"spill_{symbol_name}", 1)
        if ram_addr is None:
            return False
        print(f"Spilling symbol {symbol_name} from register R{reg} to RAM address {ram_addr}")

        # Emit LOAD instruction: LOAD reg, i:ram_addr
        if hasattr(self, '_emit_callback') and self._emit_callback:
            self._emit_callback('LOAD', reg, f'i:{ram_addr}', comment=f"Spill {symbol_name} to RAM")

        self.spilled_symbols[symbol_name] = ram_addr
        # If this was a temporary register, remove it from temporary_registers so
        # the slot is fully reclaimed and future spill passes can see it as free.
        self.temporary_registers.discard(reg)
        self.free_register(reg)
        return True
    
    def get_registers_for_scope(self, required_symbols: List[str]) -> Dict[str, int]:
        """Ensure all required symbols are in registers for a scope."""
        result = {}
        
        for symbol in required_symbols:
            reg = self.access_symbol(symbol)
            result[symbol] = reg
        
        return result
    
    def _allocate_parameter_register(self) -> Optional[int]:
        """Allocate a parameter register (R6+)."""
        while self.next_param_register < self.LOCAL_START:
            if (self.next_param_register not in self.register_to_symbol and
                    self.next_param_register not in self.RESERVED_REGISTERS):
                reg = self.next_param_register
                self.next_param_register += 1
                return reg
            self.next_param_register += 1
        return None
    
    def _allocate_local_register(self) -> Optional[int]:
        """Allocate a local register (R31, R30, R29, ..., R6)."""
        available = self.get_available_registers()
        
        while self.next_local_register >= self.PARAM_START:
            if (self.next_local_register not in self.register_to_symbol and 
                self.next_local_register not in self.RESERVED_REGISTERS and
                self.next_local_register in available and
                not self.is_register_live(self.next_local_register)):
                reg = self.next_local_register
                self.next_local_register -= 1
                return reg
            self.next_local_register -= 1
        return None
    
    def _assign_register_to_symbol(self, register: int, symbol_name: str) -> None:
        """Assign a register to a symbol."""
        self.register_to_symbol[register] = symbol_name
        self.symbol_to_register[symbol_name] = register
        self.register_usage_count[register] = 0
        print(' ' * (len(self.symbol_table.expression_scope_stack)) + f"Assigned symbol {symbol_name} to register R{register}")
    
    def _spill_and_allocate(self, symbol_name: str, is_parameter: bool) -> Optional[int]:
        """Spill least recently used symbol and allocate register."""
        # Find LRU register to spill (prefer non-live registers)
        lru_reg = None
        min_usage = float('inf')
        
        register_pool = (range(self.PARAM_START, self.LOCAL_START) if is_parameter 
                        else range(self.LOCAL_START, self.PARAM_START, -1))
        
        # First pass: try to find a non-live register
        for reg in register_pool:
            if (reg in self.register_to_symbol and 
                reg not in self.ALU_REGISTERS and
                not self.is_register_live(reg)):
                usage = self.register_usage_count.get(reg, 0)
                if usage < min_usage:
                    min_usage = usage
                    lru_reg = reg
        
        # Second pass: if no non-live registers, allow spilling live registers
        if lru_reg is None:
            for reg in register_pool:
                if reg in self.register_to_symbol and reg not in self.ALU_REGISTERS:
                    usage = self.register_usage_count.get(reg, 0)
                    if usage < min_usage:
                        min_usage = usage
                        lru_reg = reg
        
        if lru_reg is None:
            return None
        
        lru_symbol = self.register_to_symbol[lru_reg]
        if not self.spill_symbol(lru_symbol):
            return None
        
        self._assign_register_to_symbol(lru_reg, symbol_name)
        
        self.mark_register_used(lru_reg)
        
        # Track scope depth
        self.register_scope_depth[lru_reg] = len(self.register_availability_stack) - 1
        
        return lru_reg
    
    def _spill_lru_and_allocate(self) -> Optional[int]:
        """Spill LRU register for temporary allocation.

        All in-use temporary registers are marked live by
        allocate_temporary_register(), so only non-live named-variable
        registers are eligible for eviction here.
        """
        lru_reg = None
        min_usage = float('inf')

        # Single pass: find LRU non-live, non-ALU register with a symbol.
        for reg in range(self.LOCAL_START, self.PARAM_START, -1):
            if (reg not in self.ALU_REGISTERS
                    and not self.is_register_live(reg)
                    and reg in self.register_to_symbol):
                usage = self.register_usage_count.get(reg, 0)
                if usage < min_usage:
                    min_usage = usage
                    lru_reg = reg
        
        if lru_reg is None:
            print(' ' * (len(self.symbol_table.expression_scope_stack)) + "No non-live registers available to spill")
            print(f"  TEMP_REGS ({len(self.temporary_registers)}): {sorted(self.temporary_registers)}")
            print(f"  LIVE_REGS ({len(self.live_registers)}): {sorted(self.live_registers)}")
            print(f"  REG2SYM: {dict(sorted(self.register_to_symbol.items()))}")
            # No non-live registers available to spill
            # This is a critical situation - we might need to spill a live register
            # or increase the number of available registers
            return None
        
        # Guard against KeyError: only spill if lru_reg is mapped to a symbol
        if lru_reg in self.register_to_symbol:
            # Spill the LRU symbol
            lru_symbol = self.register_to_symbol[lru_reg]
            if not self.spill_symbol(lru_symbol):
                return None

        temp_name = f"__temp_{self.temp_register_counter}"
        self.temp_register_counter += 1

        self._assign_register_to_symbol(lru_reg, temp_name)
        self.temporary_registers.add(lru_reg)

        self.mark_register_used(lru_reg)

        # Track scope depth
        self.register_scope_depth[lru_reg] = len(self.register_availability_stack) - 1

        return lru_reg
    
    def get_return_register(self) -> int:
        """Get the return value register."""
        return 0
    
    def get_secondary_register(self) -> int:
        """Get the secondary return value register."""
        return 1
    
    def enter_register_scope(self) -> None:
        """Enter a new register allocation scope."""
        # Clone the current scope's available registers
        if self.register_availability_stack:
            parent_available = self.register_availability_stack[-1].copy()
        else:
            # Initialize if stack is empty
            parent_available = set(range(self.PARAM_START, self.MAX_REGISTERS)) - self.ALU_REGISTERS
        
        self.register_availability_stack.append(parent_available)
    
    def exit_register_scope(self) -> None:
        """Exit the current register allocation scope."""
        if len(self.register_availability_stack) <= 1:
            # Don't pop the base scope
            return
        
        current_scope_depth = len(self.register_availability_stack) - 1
        
        # Free all registers allocated at this scope depth
        registers_to_free = [
            reg for reg, depth in self.register_scope_depth.items()
            if depth == current_scope_depth
        ]
        
        for reg in registers_to_free:
            # Only free registers that are not still live (i.e. not currently
            # in active use by codegen).  Live registers were allocated inside
            # this scope but are being returned as results to the parent scope —
            # forcibly consuming them here would create dangling register refs.
            if not self.is_register_live(reg):
                self.temporary_registers.discard(reg)
                self._free_register_internal(reg, True)
        
        # # Clean up spilled symbols that were spilled at this scope depth
        # # (This prevents memory leaks of spilled data that's no longer needed)
        # symbols_to_unspill = []
        # for symbol_name, ram_addr in list(self.spilled_symbols.items()):
        #     # Check if this symbol should be cleaned up
        #     # For now, we keep spilled symbols across scopes for safety
        #     # TODO: Track which scope each symbol was spilled in for more aggressive cleanup
        #     print('TODO: Skipping spilled symbol cleanup for', symbol_name, 'at address', ram_addr)
        #     pass
        
        # Pop the scope
        self.register_availability_stack.pop()
    
    def get_available_registers(self) -> Set[int]:
        """Get the set of currently available registers."""
        if self.register_availability_stack:
            return self.register_availability_stack[-1].copy()
        return set()
    
    def mark_register_used(self, register: int) -> None:
        """Mark a register as used (remove from available set)."""
        if self.register_availability_stack:
            self.register_availability_stack[-1].discard(register)
    
    def mark_register_available(self, register: int) -> None:
        """Mark a register as available (add to available set)."""
        if self.register_availability_stack:
            self.register_availability_stack[-1].add(register)
    
    def mark_register_live(self, register: int, dependent_symbol: str = None) -> None:
        """Mark a register as containing a live value that must be preserved.
        
        Args:
            register: The register containing the live value
            dependent_symbol: Optional symbol that depends on this register's value
        """
        self.live_registers.add(register)
        
        if dependent_symbol:
            if register not in self.register_live_uses:
                self.register_live_uses[register] = set()
            self.register_live_uses[register].add(dependent_symbol)
    
    def mark_register_consumed(self, register: int, by_symbol: str = None) -> None:
        """Mark a register's value as consumed (no longer needs preservation).
        
        Args:
            register: The register whose value was consumed
            by_symbol: Optional symbol that consumed the value
        """
        if by_symbol and register in self.register_live_uses:
            self.register_live_uses[register].discard(by_symbol)
            
            # If no more uses, mark as not live
            if not self.register_live_uses[register]:
                self.live_registers.discard(register)
                del self.register_live_uses[register]
        else:
            # Unconditionally mark as not live
            self.live_registers.discard(register)
            if register in self.register_live_uses:
                del self.register_live_uses[register]
    
    def is_register_live(self, register: int) -> bool:
        """Check if a register contains a live value."""
        return register in self.live_registers

    # ------------------------------------------------------------------
    # Convenience helpers (consolidate repeated patterns from codegen)
    # ------------------------------------------------------------------

    def free_temporaries(self, *registers) -> None:
        """Free multiple temporary registers in one call.

        Accepts individual register numbers or iterables of register numbers.
        Skips None values so callers can pass optional regs unconditionally.

        Example::

            ra.free_temporaries(left_reg, right_reg, extra_reg)
        """
        for item in registers:
            if item is None:
                continue
            try:
                # An integer register number
                for reg in item:          # works if item is iterable
                    if reg is not None:
                        self.free_temporary_register(reg)
            except TypeError:
                self.free_temporary_register(item)  # scalar int

    def save_alu_result(self, pin_live: bool = False) -> int:
        """Allocate a fresh temporary, emit ``MVR 0 temp``, and return it.

        When *pin_live* is True the returned register is immediately marked
        live so the allocator cannot spill or reuse it before the caller is
        finished.  The caller is responsible for calling
        ``mark_register_consumed(reg)`` and, when done, freeing the temp.

        This consolidates the pattern::

            temp = allocate_temporary()
            emit(MVR, 0, temp, ...)
            mark_register_live(temp)          # if pin_live

        that appears every time an ALU result in R0 must survive a later
        allocation.
        """
        temp = self.allocate_temporary_register()
        if temp is None:
            raise RuntimeError("save_alu_result: no register available")
        # Track in expression scope so auto-free at scope exit is possible.
        if self.symbol_table and self.symbol_table.expression_scope_stack:
            self.symbol_table.expression_scope_stack[-1].add(temp)
        if hasattr(self, '_emit_callback') and self._emit_callback:
            self._emit_callback('MVR', 0, temp,
                                comment="Save ALU result (R0) to temp")
        if pin_live:
            self.mark_register_live(temp)
        return temp


    def allocate_protected(self, *live_regs) -> int:
        """Mark *live_regs* live, allocate a new temporary, then unmark them.

        Returns the newly allocated temporary register.  The live-reg pins are
        released immediately after allocation succeeds, so the caller still
        owns the returned register and is responsible for freeing it.

        This consolidates the triplet::

            ra.mark_register_live(r1)
            ra.mark_register_live(r2)
            result = allocate_temporary()
            ra.mark_register_consumed(r1)
            ra.mark_register_consumed(r2)

        that appears in MODULO, LOGICAL_AND, LOGICAL_OR, and comparisons.
        """
        for r in live_regs:
            self.mark_register_live(r)
        result = self.allocate_temporary_register()
        for r in live_regs:
            self.mark_register_consumed(r)
        if result is None:
            raise RuntimeError("allocate_protected: no register available after spill")
        # Track in expression scope stack (mirrors SymbolTable.allocate_temporary behaviour)
        if self.symbol_table and self.symbol_table.expression_scope_stack:
            self.symbol_table.expression_scope_stack[-1].add(result)
        return result

    def get_register_usage_stats(self) -> Dict[str, any]:
        """Get register allocation statistics."""
        return {
            'registers_used': len(self.register_to_symbol),
            'symbols_spilled': len(self.spilled_symbols),
            'next_local_reg': self.next_local_register,
            'next_param_reg': self.next_param_register,
            'register_map': dict(self.register_to_symbol),
            'scope_depth': len(self.register_availability_stack),
            'available_in_scope': len(self.register_availability_stack[-1]) if self.register_availability_stack else 0,
            'live_registers': list(self.live_registers)
        }