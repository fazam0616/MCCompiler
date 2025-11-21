"""Tests for MCL memory management functions (malloc, free).
"""

import unittest
from src.compiler.lexer import tokenize
from src.compiler.parser import parse
from src.compiler.assembly_generator import generate_assembly


class TestMemoryManagement(unittest.TestCase):
    """Test memory management functions."""
    
    def test_malloc_basic(self):
        """Test basic malloc functionality."""
        code = """
function main() {
    var ptr: int* = malloc(10);
    return 0;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        self.assertIn('malloc(10)', assembly)
        self.assertIn('MVR', assembly)  # Should contain move instruction for pointer
    
    def test_malloc_and_free(self):
        """Test malloc followed by free."""
        code = """
function main() {
    var ptr: int* = malloc(5);
    free(ptr);
    return 0;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        self.assertIn('malloc(5)', assembly)
        self.assertIn('free(R', assembly)  # Should contain free with register
    
    def test_multiple_malloc(self):
        """Test multiple malloc calls."""
        code = """
function main() {
    var ptr1: int* = malloc(10);
    var ptr2: int* = malloc(20);
    var ptr3: int* = malloc(5);
    
    free(ptr1);
    free(ptr2);
    free(ptr3);
    
    return 0;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        self.assertIn('malloc(10)', assembly)
        self.assertIn('malloc(20)', assembly)
        self.assertIn('malloc(5)', assembly)
        
        # Should have three free operations
        free_count = assembly.count('free(R')
        self.assertEqual(free_count, 3)
    
    def test_malloc_with_pointer_usage(self):
        """Test malloc with pointer dereferencing."""
        code = """
function main() {
    var ptr: int* = malloc(1);
    *ptr = 42;
    var value: int = *ptr;
    free(ptr);
    return value;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        self.assertIn('malloc(1)', assembly)
        self.assertIn('LOAD', assembly)  # For *ptr = 42
        self.assertIn('READ', assembly)  # For var value = *ptr
        self.assertIn('free(R', assembly)
    
    def test_malloc_error_no_args(self):
        """Test malloc with no arguments should raise error."""
        code = """
function main() {
    var ptr: int* = malloc();
    return 0;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        
        with self.assertRaises(Exception):  # Should raise CodeGenerationError
            generate_assembly(ast)
    
    def test_free_error_no_args(self):
        """Test free with no arguments should raise error."""
        code = """
function main() {
    free();
    return 0;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        
        with self.assertRaises(Exception):  # Should raise CodeGenerationError
            generate_assembly(ast)
    
    def test_lexing_malloc_free(self):
        """Test that malloc and free are recognized as tokens."""
        code = "malloc(10) free(ptr)"
        
        tokens = tokenize(code)
        token_values = [token.value for token in tokens]
        
        self.assertIn('malloc', token_values)
        self.assertIn('free', token_values)
    
    def test_memory_allocation_addresses(self):
        """Test that different malloc calls get different addresses."""
        code = """
function main() {
    var ptr1: int* = malloc(1);
    var ptr2: int* = malloc(1);
    return 0;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        # Should contain two different memory addresses
        lines = assembly.split('\n')
        malloc_lines = [line for line in lines if 'malloc(1)' in line]
        self.assertEqual(len(malloc_lines), 2)
        
        # Extract addresses from the malloc lines
        addresses = []
        for line in malloc_lines:
            if '->' in line:
                addr_part = line.split('->')[1].strip()
                addresses.append(addr_part)
        
        # Addresses should be different
        self.assertEqual(len(set(addresses)), 2, "malloc should return different addresses")


if __name__ == '__main__':
    unittest.main()