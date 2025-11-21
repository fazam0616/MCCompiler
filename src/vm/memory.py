"""MCL Virtual Machine Memory Management

Handles RAM, ROM (program memory), and address resolution.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from .cpu import Instruction


class MemoryException(Exception):
    """Base exception for memory-related errors."""
    pass


class InvalidAddressException(MemoryException):
    """Exception for invalid memory addresses."""
    pass


class ReadOnlyException(MemoryException):
    """Exception for writing to read-only memory."""
    pass


@dataclass
class MemoryRegion:
    """Represents a region of memory."""
    start_address: int
    size: int
    read_only: bool = False
    name: str = ""
    
    @property
    def end_address(self) -> int:
        return self.start_address + self.size - 1
    
    def contains(self, address: int) -> bool:
        return self.start_address <= address <= self.end_address


class Memory:
    """MCL Virtual Machine Memory Management Unit."""
    
    def __init__(self, ram_size: int = 0x8000, rom_size: int = 0x4000):
        """Initialize memory with specified RAM and ROM sizes.
        
        Args:
            ram_size: Size of RAM in 16-bit words (default 32KB)
            rom_size: Size of ROM in 16-bit words (default 16KB)
        """
        # Memory regions (16-bit addressing)
        self.regions = {
            'ram': MemoryRegion(0x0000, ram_size, False, "RAM"),
            'rom': MemoryRegion(0x8000, rom_size, True, "ROM")
        }
        
        # Physical memory storage
        self.ram = [0] * ram_size
        self.rom = [0] * rom_size
        
        # Program storage (instructions)
        self.program: List[Instruction] = []
        
        # Label to address mapping
        self.labels: Dict[str, int] = {}
        
        # Memory access statistics
        self.read_count = 0
        self.write_count = 0
    
    def load_program(self, instructions: List[Instruction], labels: Dict[str, int] = None) -> None:
        """Load a program into ROM.
        
        Args:
            instructions: List of instructions to load
            labels: Optional label to address mapping
        """
        if len(instructions) > len(self.rom):
            raise MemoryException(f"Program too large: {len(instructions)} > {len(self.rom)}")
        
        self.program = instructions.copy()
        
        if labels:
            self.labels.update(labels)
        
        # Clear ROM and load instructions
        self.rom = [0] * len(self.rom)
        for i, instr in enumerate(instructions):
            self.rom[i] = instr  # Store instruction objects
    
    def read(self, address: int) -> int:
        """Read a word from memory.
        
        Args:
            address: Memory address to read from (16-bit)
        
        Returns:
            16-bit integer value at the address
        """
        address = address & 0xFFFF  # Ensure 16-bit address
        self.read_count += 1
        
        # Determine which region contains this address
        region = self._get_region(address)
        
        if region.name == "RAM":
            offset = address - region.start_address
            if 0 <= offset < len(self.ram):
                return self.ram[offset] & 0xFFFF  # Ensure 16-bit return
        elif region.name == "ROM":
            offset = address - region.start_address
            if 0 <= offset < len(self.rom):
                # ROM contains instructions, not raw data
                # This shouldn't normally be called for ROM addresses
                return 0  # Or raise exception
        
        raise InvalidAddressException(f"Invalid read address: 0x{address:04X}")
    
    def write(self, address: int, value: int) -> None:
        """Write a word to memory.
        
        Args:
            address: Memory address to write to (16-bit)
            value: 16-bit integer value to write
        """
        address = address & 0xFFFF  # Ensure 16-bit address
        value = value & 0xFFFF      # Ensure 16-bit value
        self.write_count += 1
        
        # Determine which region contains this address
        region = self._get_region(address)
        
        if region.read_only:
            raise ReadOnlyException(f"Cannot write to read-only memory: 0x{address:04X}")
        
        if region.name == "RAM":
            offset = address - region.start_address
            if 0 <= offset < len(self.ram):
                # Store 16-bit value
                self.ram[offset] = value
                return
        
        raise InvalidAddressException(f"Invalid write address: 0x{address:04X}")
    
    def fetch_instruction(self, pc: int) -> Optional[Instruction]:
        """Fetch an instruction from program memory.
        
        Args:
            pc: Program counter (instruction address)
        
        Returns:
            Instruction at the given address, or None if out of bounds
        """
        if 0 <= pc < len(self.program):
            return self.program[pc]
        return None
    
    def resolve_label(self, label: str) -> int:
        """Resolve a label to its address.
        
        Args:
            label: Label name to resolve
        
        Returns:
            Address corresponding to the label
        
        Raises:
            MemoryException: If label is not found
        """
        if label in self.labels:
            return self.labels[label]
        
        # Try to find function labels
        func_label = f"func_{label}"
        if func_label in self.labels:
            return self.labels[func_label]
        
        raise MemoryException(f"Undefined label: {label}")
    
    def _get_region(self, address: int) -> MemoryRegion:
        """Get the memory region containing the given address.
        
        Args:
            address: Memory address
        
        Returns:
            MemoryRegion containing the address
        
        Raises:
            InvalidAddressException: If address is not in any region
        """
        for region in self.regions.values():
            if region.contains(address):
                return region
        
        raise InvalidAddressException(f"Address not in any memory region: 0x{address:04X}")
    
    def get_memory_map(self) -> Dict[str, Any]:
        """Get memory map information for debugging."""
        return {
            'regions': {
                name: {
                    'start': f"0x{region.start_address:04X}",
                    'end': f"0x{region.end_address:04X}",
                    'size': region.size,
                    'read_only': region.read_only
                }
                for name, region in self.regions.items()
            },
            'program_size': len(self.program),
            'labels': self.labels,
            'statistics': {
                'reads': self.read_count,
                'writes': self.write_count
            }
        }
    
    def dump_ram(self, start: int = 0, count: int = 16) -> Dict[int, int]:
        """Dump RAM contents for debugging.
        
        Args:
            start: Starting address offset in RAM
            count: Number of words to dump
        
        Returns:
            Dictionary mapping addresses to values
        """
        result = {}
        ram_region = self.regions['ram']
        
        for i in range(count):
            addr = start + i
            if 0 <= addr < len(self.ram):
                result[ram_region.start_address + addr] = self.ram[addr]
        
        return result
    
    def dump_program(self, start: int = 0, count: int = 10) -> List[str]:
        """Dump program instructions for debugging.
        
        Args:
            start: Starting instruction index
            count: Number of instructions to dump
        
        Returns:
            List of instruction strings
        """
        result = []
        
        for i in range(start, min(start + count, len(self.program))):
            instr = self.program[i]
            result.append(f"{i:04d}: {instr}")
        
        return result
    
    def clear_ram(self) -> None:
        """Clear all RAM contents."""
        self.ram = [0] * len(self.ram)
    
    def get_ram_usage(self) -> float:
        """Get RAM usage percentage."""
        non_zero = sum(1 for x in self.ram if x != 0)
        return (non_zero / len(self.ram)) * 100.0