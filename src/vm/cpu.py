"""MCL Virtual Machine CPU

Simulates the CPU with registers and instruction execution.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import struct


class CPUException(Exception):
    """Base exception for CPU-related errors."""
    pass


class InvalidInstructionException(CPUException):
    """Exception for invalid instructions."""
    pass


class MemoryAccessException(CPUException):
    """Exception for invalid memory access."""
    pass


class CPUState(Enum):
    """CPU execution states."""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    BREAKPOINT = "breakpoint"


@dataclass
class Instruction:
    """Represents a decoded instruction."""
    opcode: str
    operands: List[Any]
    address: int
    raw_data: Any = None


class CPU:
    """MCL Virtual Machine CPU."""
    
    # Special register indices
    RETURN_VALUE_REG = 0
    SECONDARY_RETURN_REG = 1
    STACK_POINTER_REG = 2
    FRAME_POINTER_REG = 3
    
    # Special named registers (outside 0-31 range)
    SPECIAL_REGISTERS = {
        'GPU': 'gpu_register'  # GPU control register
    }
    
    def __init__(self, memory, gpu=None, num_registers: int = 32):
        """Initialize CPU with memory and GPU references.
        
        Args:
            memory: Memory management unit
            gpu: GPU unit (optional)
            num_registers: Number of general-purpose registers
        """
        self.memory = memory
        self.gpu = gpu
        
        # Registers (16-bit integers)
        self.registers = [0] * num_registers
        
        # Program counter
        self.pc = 0
        
        # CPU state
        self.state = CPUState.STOPPED
        self.halt_reason = None
        
        # Execution statistics
        self.instruction_count = 0
        self.cycle_count = 0
        
        # Input buffer for KEYIN instruction
        self.input_buffer = [0] * 256  # Ring buffer for input
        self.input_write_pos = 0  # Where new input is written
        self.input_read_pos = 0   # Where KEYIN reads from
        
        # Labels dictionary for jump resolution
        self.labels: Dict[str, int] = {}
        
        # Instruction set
        self.instruction_handlers = {
            'LOAD': self._exec_load,
            'READ': self._exec_read,
            'MVR': self._exec_mvr,
            'MVM': self._exec_mvm,
            'ADD': self._exec_add,
            'SUB': self._exec_sub,
            'MULT': self._exec_mult,
            'DIV': self._exec_div,
            'SHL': self._exec_shl,
            'SHR': self._exec_shr,
            'SHLR': self._exec_shlr,
            'AND': self._exec_and,
            'OR': self._exec_or,
            'XOR': self._exec_xor,
            'NOT': self._exec_not,
            'JMP': self._exec_jmp,
            'JAL': self._exec_jal,
            'JBT': self._exec_jbt,
            'JZ': self._exec_jz,
            'JNZ': self._exec_jnz,
            'KEYIN': self._exec_keyin,
            'HALT': self._exec_halt,
            # GPU instructions
            'DRLINE': self._exec_gpu,
            'DRGRD': self._exec_gpu,
            'CLRGRID': self._exec_gpu,
            'LDSPR': self._exec_gpu,
            'DRSPR': self._exec_gpu,
            'LDTXT': self._exec_gpu,
            'DRTXT': self._exec_gpu,
            'SCRLBFR': self._exec_gpu,
        }
    
    def reset(self) -> None:
        """Reset CPU to initial state."""
        self.registers = [0] * len(self.registers)
        self.pc = 0
        self.state = CPUState.STOPPED
        self.halt_reason = None
        self.instruction_count = 0
        self.cycle_count = 0
    
    def get_register(self, reg_id) -> int:
        """Get register value (supports both numeric and named registers)."""
        # Handle named registers
        if isinstance(reg_id, str):
            if reg_id in self.SPECIAL_REGISTERS:
                if reg_id == 'GPU' and self.gpu:
                    return self.gpu.get_gpu_register()
                return 0  # Default for unimplemented special registers
            else:
                raise CPUException(f"Unknown special register: {reg_id}")
        
        # Handle numeric registers
        if 0 <= reg_id < len(self.registers):
            return self.registers[reg_id]
        raise CPUException(f"Invalid register: {reg_id}")
    
    def set_register(self, reg_id, value: int) -> None:
        """Set register value (supports both numeric and named registers)."""
        # Handle named registers
        if isinstance(reg_id, str):
            if reg_id in self.SPECIAL_REGISTERS:
                if reg_id == 'GPU' and self.gpu:
                    # Always mask GPU register to 32 bits
                    self.gpu.set_gpu_register(value & 0xFFFFFFFF)
                return
            else:
                raise CPUException(f"Unknown special register: {reg_id}")
        
        # Handle numeric registers
        if 0 <= reg_id < len(self.registers):
            # Ensure 16-bit unsigned range (0 to 65535)
            self.registers[reg_id] = value & 0xFFFF
        else:
            raise CPUException(f"Invalid register: {reg_id}")
    
    def _to_16bit_unsigned(self, value: int) -> int:
        """Convert value to 16-bit unsigned integer."""
        return value & 0xFFFF
    
    def add_input_char(self, char_code: int) -> None:
        """Add character to input buffer."""
        self.input_buffer[self.input_write_pos] = char_code
        self.input_write_pos = (self.input_write_pos + 1) % len(self.input_buffer)
    
    def set_labels(self, labels: Dict[str, int]) -> None:
        """Set labels dictionary for jump resolution."""
        self.labels = labels.copy()
    
    def backspace_input(self) -> None:
        """Handle backspace in input buffer."""
        if self.input_write_pos != self.input_read_pos:
            self.input_write_pos = (self.input_write_pos - 1) % len(self.input_buffer)
    
    def read_input_char(self) -> int:
        """Read next character from input buffer for KEYIN instruction."""
        if self.input_read_pos == self.input_write_pos:
            return 0  # No input available
        
        char_code = self.input_buffer[self.input_read_pos]
        self.input_read_pos = (self.input_read_pos + 1) % len(self.input_buffer)
        return char_code
    
    def _blocking_read_input_char(self) -> int:
        """Blocking read from input buffer - waits until input is available."""
        import time
        
        while self.state == CPUState.RUNNING:
            # Check if input is available
            if self.input_read_pos != self.input_write_pos:
                char_code = self.input_buffer[self.input_read_pos]
                self.input_read_pos = (self.input_read_pos + 1) % 256
                return char_code
            
            # No input available - update display to process events and wait
            if self.gpu and hasattr(self.gpu, 'update_display'):
                if not self.gpu.update_display():
                    # Display closed - stop execution
                    self.state = CPUState.STOPPED
                    return 0
            
        
        # CPU stopped while waiting
        return 0
    
    def _read_stdin_char(self) -> int:
        """Read a character from stdin in headless mode."""
        try:
            import sys
            
            # Simple input without tty manipulation for Windows compatibility
            print("Enter character: ", end='', flush=True)
            char = input()
            if char:
                # Take first character and convert to uppercase
                char = char[0].upper()
                # Convert to 6-bit character code
                if char.isalpha():
                    return ord(char) - ord('A')  # A-Z = 0-25
                elif char.isdigit():
                    return ord(char) - ord('0') + 26  # 0-9 = 26-35
                elif char in "!?+-*.,":
                    special_chars = "!?+-*.,"
                    return special_chars.index(char) + 36  # Special = 36-42
            return 0
        except:
            # Fallback: return 0 if input reading fails
            return 0
    
    def _resolve_operand(self, operand: str):
        """Resolve operand to a value.
        
        Args:
            operand: String operand (register, immediate, or label)
        
        Returns:
            Resolved integer value or register name for special registers
        """
        if isinstance(operand, int):
            return operand
        
        operand_str = str(operand)
        
        # Immediate value (prefixed with 'i:')
        if operand_str.startswith('i:'):
            value_str = operand_str[2:]
            if value_str.startswith('0x'):
                try:
                    return int(value_str, 16)
                except ValueError:
                    # Not a valid hex, treat as label
                    return self.memory.resolve_label(value_str)
            try:
                return int(value_str)
            except ValueError:
                # Not a valid int, treat as label
                return self.memory.resolve_label(value_str)
        
        # Hexadecimal
        if operand_str.startswith('0x'):
            return int(operand_str, 16)
        
        # Register or memory address
        try:
            return int(operand_str)
        except ValueError:
            # Check for special named registers before resolving as label
            if operand_str in self.SPECIAL_REGISTERS:
                return operand_str  # Return the name for special handling
            # Label - resolve through memory/program
            return self.memory.resolve_label(operand_str)
    
    def step(self) -> bool:
        """Execute one instruction.
        
        Returns:
            True if execution should continue, False if halted
        """
        if self.state != CPUState.RUNNING:
            return False
        
        try:
            # Fetch instruction
            instruction = self.memory.fetch_instruction(self.pc)
            if instruction is None:
                self.state = CPUState.STOPPED
                self.halt_reason = "End of program"
                return False
            
            # Decode and execute
            self._execute_instruction(instruction)
            
            # Update counters
            self.instruction_count += 1
            self.cycle_count += 1
            
            return True
        except Exception as e:
            self.state = CPUState.ERROR
            self.halt_reason = str(e)
            # Immediately raise exception so error is not silently swallowed
            raise
    
    def run(self, max_cycles: Optional[int] = None) -> None:
        """Run CPU until halted or max cycles reached."""
        self.state = CPUState.RUNNING
        
        cycles = 0
        while self.state == CPUState.RUNNING:
            if max_cycles and cycles >= max_cycles:
                self.state = CPUState.STOPPED
                self.halt_reason = "Max cycles reached"
                break
            
            if not self.step():
                break
            
            cycles += 1
    
    def _execute_instruction(self, instruction: Instruction) -> None:
        """Execute a decoded instruction."""
        handler = self.instruction_handlers.get(instruction.opcode.upper())
        if not handler:
            raise InvalidInstructionException(f"Unknown instruction: {instruction.opcode}")
        
        # Execute instruction
        handler(instruction)
        
        # Advance PC (unless it was modified by the instruction)
        if instruction.opcode.upper() not in ['JMP', 'JAL', 'JBT', 'JZ', 'JNZ']:
            self.pc += 1
    
    # Instruction implementations
    
    def _exec_load(self, instr: Instruction) -> None:
        """LOAD A, B - Load value A into RAM address B
        A can be immediate (i:value), hex (0x...), or register for value
        B can be immediate (i:addr), hex (0x...), or register for address
        """
        if len(instr.operands) != 2:
            raise InvalidInstructionException("LOAD requires 2 operands")
        
        # Get value to store (first operand)
        if instr.operands[0].startswith('i:'):
            # Immediate value - use the value directly
            value = self._resolve_operand(instr.operands[0])
        elif str(instr.operands[0]).startswith('0x'):
            # Hex immediate value
            value = int(instr.operands[0], 16)
        else:
            # Register - use the register's value
            try:
                reg_num = int(instr.operands[0])
                value = self.get_register(reg_num)
            except ValueError:
                raise CPUException(f"Invalid source operand: {instr.operands[0]}")
        
        # Get RAM address (second operand)
        if instr.operands[1].startswith('i:'):
            # Immediate address - use the address directly
            ram_addr = self._resolve_operand(instr.operands[1])
        elif str(instr.operands[1]).startswith('0x'):
            # Hex immediate address
            ram_addr = int(instr.operands[1], 16)
        else:
            # Register - use the register's value as address
            try:
                reg_num = int(instr.operands[1])
                ram_addr = self.get_register(reg_num)
            except ValueError:
                raise CPUException(f"Invalid destination address operand: {instr.operands[1]}")
        
        self.memory.write(ram_addr, value)
    
    def _exec_read(self, instr: Instruction) -> None:
        """READ A, B - Load data at RAM address A into register B
        A can be immediate (i:addr), hex (0x...), or register for address
        B must be a register number (cannot be immediate)
        """
        if len(instr.operands) != 2:
            raise InvalidInstructionException("READ requires 2 operands")
        
        # Validate destination is not immediate
        if str(instr.operands[1]).startswith('i:'):
            raise CPUException("READ destination cannot be immediate value")
        
        # Get RAM address (first operand)
        if instr.operands[0].startswith('i:'):
            # Immediate address - use the address directly
            ram_addr = self._resolve_operand(instr.operands[0])
        elif str(instr.operands[0]).startswith('0x'):
            # Hex immediate address
            ram_addr = int(instr.operands[0], 16)
        else:
            # Register - use the register's value as address
            try:
                reg_num = int(instr.operands[0])
                ram_addr = self.get_register(reg_num)
            except ValueError:
                raise CPUException(f"Invalid RAM address operand: {instr.operands[0]}")
        
        # Get destination register (second operand)
        try:
            dest_reg = int(instr.operands[1])
            if not (0 <= dest_reg < len(self.registers)):
                raise CPUException(f"Invalid destination register: {dest_reg}")
        except ValueError:
            raise CPUException(f"Invalid destination register: {instr.operands[1]}")
        
        value = self.memory.read(ram_addr)
        self.set_register(dest_reg, value)
    
    def _exec_mvr(self, instr: Instruction) -> None:
        """MVR A, B - Move value to register
        A can be immediate (i:value), hex (0x...), or register
        B must be a register (cannot be immediate)
        """
        if len(instr.operands) != 2:
            raise InvalidInstructionException("MVR requires 2 operands")

        # Validate destination is not immediate
        if str(instr.operands[1]).startswith('i:'):
            raise CPUException("MVR destination cannot be immediate value")

        # Use the robust _get_operand_value for the source
        value = self._get_operand_value(instr.operands[0])

        # Get destination register (second operand)
        try:
            dst_reg = int(instr.operands[1])
            if not (0 <= dst_reg < len(self.registers)):
                raise CPUException(f"Invalid destination register: {dst_reg}")
        except ValueError:
            # Handle special named registers like 'GPU'
            dst_reg_str = str(instr.operands[1])
            if dst_reg_str in self.SPECIAL_REGISTERS:
                dst_reg = dst_reg_str
            else:
                raise CPUException(f"Invalid destination register: {dst_reg_str}")

        self.set_register(dst_reg, value)
    
    def _exec_mvm(self, instr: Instruction) -> None:
        """MVM A, B - Copy RAM address A to RAM address B
        A can be immediate (i:addr), hex (0x...), or register for address
        B can be immediate (i:addr), hex (0x...), or register for address
        """
        if len(instr.operands) != 2:
            raise InvalidInstructionException("MVM requires 2 operands")
        
        # Get source address (first operand)
        if instr.operands[0].startswith('i:'):
            src_addr = self._resolve_operand(instr.operands[0])
        elif str(instr.operands[0]).startswith('0x'):
            src_addr = int(instr.operands[0], 16)
        else:
            try:
                reg_num = int(instr.operands[0])
                src_addr = self.get_register(reg_num)
            except ValueError:
                raise CPUException(f"Invalid source address operand: {instr.operands[0]}")
        
        # Get destination address (second operand)
        if instr.operands[1].startswith('i:'):
            dst_addr = self._resolve_operand(instr.operands[1])
        elif str(instr.operands[1]).startswith('0x'):
            dst_addr = int(instr.operands[1], 16)
        else:
            try:
                reg_num = int(instr.operands[1])
                dst_addr = self.get_register(reg_num)
            except ValueError:
                raise CPUException(f"Invalid destination address operand: {instr.operands[1]}")
        
        value = self.memory.read(src_addr)
        self.memory.write(dst_addr, value)
    
    def _exec_add(self, instr: Instruction) -> None:
        """ADD A, B - Add A and B, store result in return registers"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("ADD requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        result = a + b
        self.set_register(self.RETURN_VALUE_REG, result)
    
    def _exec_sub(self, instr: Instruction) -> None:
        """SUB A, B - Subtract B from A, store result in return registers"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("SUB requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        result = a - b
        self.set_register(self.RETURN_VALUE_REG, result)
    
    def _exec_mult(self, instr: Instruction) -> None:
        """MULT A, B - Multiply A and B, store result in return registers"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("MULT requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        result = a * b
        # Handle overflow into secondary register (16-bit)
        self.set_register(self.RETURN_VALUE_REG, result & 0xFFFF)
        self.set_register(self.SECONDARY_RETURN_REG, (result >> 16) & 0xFFFF)
    
    def _exec_div(self, instr: Instruction) -> None:
        """DIV A, B - Divide A by B, store result in return registers"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("DIV requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        if b == 0:
            raise CPUException("Division by zero")
        
        quotient = a // b
        remainder = a % b
        
        self.set_register(self.RETURN_VALUE_REG, quotient)
        self.set_register(self.SECONDARY_RETURN_REG, remainder)
    
    def _exec_shl(self, instr: Instruction) -> None:
        """SHL A, B - Shift A left by B bits"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("SHL requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        if str(instr.operands[0]) == 'GPU':
            result = (a << b) & 0xFFFFFFFF
        else:
            result = (a << b) & 0xFFFF
        self.set_register(self.RETURN_VALUE_REG, result)
    
    def _exec_shr(self, instr: Instruction) -> None:
        """SHR A, B - Shift A right by B bits"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("SHR requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        if str(instr.operands[0]) == 'GPU':
            result = (a >> b) & 0xFFFFFFFF
        else:
            result = (a >> b) & 0xFFFF
        self.set_register(self.RETURN_VALUE_REG, result)
    
    def _exec_shlr(self, instr: Instruction) -> None:
        """SHLR A, B - Shift A left rotate by B bits"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("SHLR requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1]) % 16
        
        # 16-bit rotate left
        a = a & 0xFFFF
        result = ((a << b) | (a >> (16 - b))) & 0xFFFF
        self.set_register(self.RETURN_VALUE_REG, result)
    
    def _exec_and(self, instr: Instruction) -> None:
        """AND A, B - Bitwise AND of A and B"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("AND requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        if (str(instr.operands[0]) == 'GPU') or (str(instr.operands[1]) == 'GPU'):
            result = (a & b) & 0xFFFFFFFF
        else:
            result = a & b
        self.set_register(self.RETURN_VALUE_REG, result)
    
    def _exec_or(self, instr: Instruction) -> None:
        """OR A, B - Bitwise OR of A and B"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("OR requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        if (str(instr.operands[0]) == 'GPU') or (str(instr.operands[1]) == 'GPU'):
            result = (a | b) & 0xFFFFFFFF
        else:
            result = a | b
        self.set_register(self.RETURN_VALUE_REG, result)
    
    def _exec_xor(self, instr: Instruction) -> None:
        """XOR A, B - Bitwise XOR of A and B"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("XOR requires 2 operands")
        
        a = self._get_operand_value(instr.operands[0])
        b = self._get_operand_value(instr.operands[1])
        
        if (str(instr.operands[0]) == 'GPU') or (str(instr.operands[1]) == 'GPU'):
            result = (a ^ b) & 0xFFFFFFFF
        else:
            result = a ^ b
        self.set_register(self.RETURN_VALUE_REG, result)
    
    def _exec_not(self, instr: Instruction) -> None:
        """NOT A - Bitwise NOT of A"""
        if len(instr.operands) != 1:
            raise InvalidInstructionException("NOT requires 1 operand")
        
        # NOT should only work on registers, not immediate values
        operand = instr.operands[0]
        if operand.startswith('i:'):
            raise InvalidInstructionException("NOT operand cannot be immediate value")
            
        # Handle both 'r:N' and 'N' formats
        if operand.startswith('r:'):
            reg_num = int(operand[2:])
        else:
            reg_num = int(operand)
            
        a = self.get_register(reg_num)
        
        result = (~a) & 0xFFFF  # Ensure 16-bit result
        self.set_register(reg_num, result)
    
    def _exec_jmp(self, instr: Instruction) -> None:
        """JMP A - Jump to address A
        If A is immediate (i:addr), jump to that address directly
        If A is register, jump to the address stored in that register
        If A is label, jump to the label's resolved address
        """
        if len(instr.operands) != 1:
            raise InvalidInstructionException("JMP requires 1 operand")
        
        operand = instr.operands[0]
        
        if operand.startswith('i:'):
            # Immediate address
            target = self._resolve_operand(operand)
        elif operand.isdigit() or (operand.startswith('r:') and operand[2:].isdigit()):
            # Register - use register's value as address
            if operand.startswith('r:'):
                reg_num = int(operand[2:])
            else:
                reg_num = int(operand)
            target = self.get_register(reg_num)
        else:
            # Label - resolve through memory
            target = self._resolve_operand(operand)
            
        self.pc = target
    
    def _exec_jal(self, instr: Instruction) -> None:
        """JAL A - Jump to address A and store current PC in reserved register"""
        if len(instr.operands) != 1:
            raise InvalidInstructionException("JAL requires 1 operand")
        
        # Store return address (next instruction)
        self.set_register(self.SECONDARY_RETURN_REG, self.pc + 1)
        
        target = self._resolve_operand(instr.operands[0])
        self.pc = target
    
    def _exec_jbt(self, instr: Instruction) -> None:
        """JBT A, x, y - Jump to A if register x > register y"""
        if len(instr.operands) != 3:
            raise InvalidInstructionException("JBT requires 3 operands")
        
        target = self._resolve_operand(instr.operands[0])
        x = self._get_operand_value(instr.operands[1])
        y = self._get_operand_value(instr.operands[2])
        
        if x > y:
            self.pc = target
        else:
            self.pc += 1
    
    def _exec_jz(self, instr: Instruction) -> None:
        """JZ A, x - Jump to A if register x == 0"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("JZ requires 2 operands")
        
        target = self._resolve_operand(instr.operands[0])
        x = self._get_operand_value(instr.operands[1])
        
        if x == 0:
            self.pc = target
        else:
            self.pc += 1
    
    def _exec_jnz(self, instr: Instruction) -> None:
        """JNZ A, x - Jump to A if register x != 0"""
        if len(instr.operands) != 2:
            raise InvalidInstructionException("JNZ requires 2 operands")
        
        target = self._resolve_operand(instr.operands[0])
        x = self._get_operand_value(instr.operands[1])
        
        if x != 0:
            self.pc = target
        else:
            self.pc += 1
    
    def _exec_keyin(self, instr: Instruction) -> None:
        """KEYIN A - Load system input into address A with blocking behavior"""
        if len(instr.operands) != 1:
            raise InvalidInstructionException("KEYIN requires 1 operand")
        
        address = self._resolve_operand(instr.operands[0])
        # Prefer input buffer if data has been queued (tests can inject input)
        if self.input_read_pos != self.input_write_pos:
            char_code = self.read_input_char()
        else:
            # Read character from input buffer or stdin in headless mode
            if self.gpu and self.gpu.pygame_initialized:
                # GUI mode: blocking read from input buffer
                char_code = self._blocking_read_input_char()
            else:
                # Headless mode: read from stdin (always blocking)
                char_code = self._read_stdin_char()
        
        # Store in memory at specified address
        try:
            self.memory.write(address, char_code)
        except Exception as e:
            raise CPUException(f"KEYIN memory write failed: {e}")
    
    def _exec_halt(self, instr: Instruction) -> None:
        """HALT - Stop program execution"""
        self.state = CPUState.STOPPED
        self.halt_reason = "HALT instruction executed"
    
    def _exec_gpu(self, instr: Instruction) -> None:
        """GPU instruction - delegate to GPU unit with immediate value support"""
        if self.gpu:
            # Resolve all operands (both immediate and register values)
            resolved_operands = []
            for operand in instr.operands:
                resolved_operands.append(self._get_operand_value(operand))
            
            self.gpu.execute_command(instr.opcode, resolved_operands)
        else:
            # Ignore GPU commands if no GPU is attached
            pass
    
    def _get_operand_value(self, operand: str) -> int:
        """Get the value of an operand (register value or immediate)."""
        if str(operand).startswith('i:'):
            _, str_data = operand.split(':', 1)

            #Check is str_data is a label referring to another section of assembly code
            if str_data in self.memory.labels:
                return self.memory.labels[str_data] 
            else:
                # Explicit immediate value
                return self._resolve_operand(operand)
        elif str(operand).startswith('0x'):
            # Hex immediate (no i: prefix needed)
            return int(operand, 16)
        else:
            # Raw decimal - treat as register number
            try:
                resolved = self._resolve_operand(operand)
                if isinstance(resolved, str):
                    # Named register (like 'GPU')
                    return self.get_register(resolved)
                else:
                    # Numeric register
                    return self.get_register(resolved)
            except ValueError:
                raise CPUException(f"Invalid operand: {operand}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get CPU state for debugging."""
        return {
            'registers': self.registers.copy(),
            'pc': self.pc,
            'state': self.state.value,
            'halt_reason': self.halt_reason,
            'instruction_count': self.instruction_count,
            'cycle_count': self.cycle_count
        }
    
    def set_breakpoint(self, address: int) -> None:
        """Set a breakpoint at the given address."""
        # This would be implemented in conjunction with the debugger
        pass
    
    def clear_breakpoint(self, address: int) -> None:
        """Clear a breakpoint at the given address."""
        # This would be implemented in conjunction with the debugger
        pass