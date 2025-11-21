"""MCL Assembly Loader

Loads and parses assembly files into executable instructions.
"""

from typing import List, Dict, Tuple, Optional
import re
from .cpu import Instruction


class AssemblyLoaderError(Exception):
    """Exception raised for assembly loading errors."""
    pass


class AssemblyLoader:
    """Loads assembly code into executable instructions."""
    
    def __init__(self):
        self.labels: Dict[str, int] = {}
        self.instructions: List[Instruction] = []
    
    def load_from_file(self, filename: str) -> Tuple[List[Instruction], Dict[str, int]]:
        """Load assembly from file.
        
        Args:
            filename: Path to assembly file
        
        Returns:
            Tuple of (instructions, labels)
        """
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.load_from_string(content)
    
    def load_from_string(self, assembly_code: str) -> Tuple[List[Instruction], Dict[str, int]]:
        """Load assembly from string.
        
        Args:
            assembly_code: Assembly code as string
        
        Returns:
            Tuple of (instructions, labels)
        """
        self.labels.clear()
        self.instructions.clear()
        
        lines = assembly_code.strip().split('\n')
        current_address = 0
        
        # First pass: collect labels
        for line_num, line in enumerate(lines, 1):
            try:
                processed_line = self._preprocess_line(line)
                if not processed_line:
                    continue
                
                # Check for label
                if ':' in processed_line and not processed_line.strip().startswith('//'):
                    label_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*):(.*)$', processed_line)
                    if label_match:
                        label_name = label_match.group(1)
                        self.labels[label_name] = current_address
                        
                        # Check if there's an instruction after the label
                        remaining = label_match.group(2).strip()
                        if remaining and not remaining.startswith('//'):
                            current_address += 1
                    else:
                        current_address += 1
                else:
                    current_address += 1
            
            except Exception as e:
                raise AssemblyLoaderError(f"Error on line {line_num}: {e}")
        
        # Second pass: parse instructions
        current_address = 0
        for line_num, line in enumerate(lines, 1):
            try:
                processed_line = self._preprocess_line(line)
                if not processed_line:
                    continue
                
                # Handle labels
                if ':' in processed_line:
                    label_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*):(.*)$', processed_line)
                    if label_match:
                        remaining = label_match.group(2).strip()
                        if remaining and not remaining.startswith('//'):
                            instruction = self._parse_instruction(remaining, current_address)
                            self.instructions.append(instruction)
                            current_address += 1
                    else:
                        instruction = self._parse_instruction(processed_line, current_address)
                        self.instructions.append(instruction)
                        current_address += 1
                else:
                    instruction = self._parse_instruction(processed_line, current_address)
                    self.instructions.append(instruction)
                    current_address += 1
            
            except Exception as e:
                raise AssemblyLoaderError(f"Error on line {line_num}: {e}")
        
        return self.instructions.copy(), self.labels.copy()
    
    def _preprocess_line(self, line: str) -> str:
        """Preprocess a line by removing comments and whitespace.
        
        Args:
            line: Raw line from assembly file
        
        Returns:
            Processed line, or empty string if line should be skipped
        """
        # Remove comments
        comment_pos = line.find('//')
        if comment_pos >= 0:
            line = line[:comment_pos]
        
        # Strip whitespace
        line = line.strip()
        
        # Skip empty lines
        if not line:
            return ""
        
        return line
    
    def _parse_instruction(self, line: str, address: int) -> Instruction:
        """Parse a single instruction line.
        
        Args:
            line: Instruction line (without label)
            address: Address of this instruction
        
        Returns:
            Parsed Instruction object
        """
        # Split instruction and operands
        parts = line.split()
        if not parts:
            raise AssemblyLoaderError("Empty instruction")
        
        opcode = parts[0].upper()
        
        # Parse operands
        operands = []
        if len(parts) > 1:
            # Join remaining parts and split by comma
            operand_str = ' '.join(parts[1:])
            # Remove inline comments before parsing operands
            comment_pos = operand_str.find(';')
            if comment_pos >= 0:
                operand_str = operand_str[:comment_pos]
            
            operand_parts = [op.strip() for op in operand_str.split(',')]
            
            for op in operand_parts:
                if op:
                    operands.append(self._parse_operand(op))
        
        return Instruction(opcode, operands, address)
    
    def _parse_operand(self, operand: str) -> str:
        """Parse a single operand.
        
        Args:
            operand: Raw operand string
        
        Returns:
            Parsed operand
        
        Rules:
        - i:123 = immediate decimal value
        - 0x123 = immediate hex value (no i: needed)
        - 123 = register number (raw decimals are always registers)
        - label = label reference
        """
        operand = operand.strip()
        
        # Handle explicit immediate values (i:123 or i:0xFF)
        if operand.startswith('i:'):
            return operand
        
        # Handle hexadecimal values (treated as immediates without i: prefix)
        if operand.startswith('0x') or operand.startswith('0X'):
            return operand
        
        # Handle decimal numbers (treated as register numbers)
        try:
            int(operand)
            return operand  # Raw decimal = register number
        except ValueError:
            pass
        
        # Handle labels/identifiers
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', operand):
            return operand
        
        raise AssemblyLoaderError(f"Invalid operand: {operand}")


def load_assembly_file(filename: str) -> Tuple[List[Instruction], Dict[str, int]]:
    """Convenience function to load assembly from file.
    
    Args:
        filename: Path to assembly file
    
    Returns:
        Tuple of (instructions, labels)
    """
    loader = AssemblyLoader()
    return loader.load_from_file(filename)


def load_assembly_string(assembly_code: str) -> Tuple[List[Instruction], Dict[str, int]]:
    """Convenience function to load assembly from string.
    
    Args:
        assembly_code: Assembly code as string
    
    Returns:
        Tuple of (instructions, labels)
    """
    loader = AssemblyLoader()
    return loader.load_from_string(assembly_code)