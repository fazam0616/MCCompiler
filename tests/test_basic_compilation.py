"""Basic compilation tests for MCL compiler.
"""

import unittest
import tempfile
import os
from pathlib import Path

from src.compiler.lexer import tokenize, LexerError
from src.compiler.parser import parse, ParseError
from src.compiler.assembly_generator import generate_assembly, CodeGenerationError


class TestBasicCompilation(unittest.TestCase):
    """Test basic compilation pipeline."""
    
    def test_simple_lexing(self):
        """Test lexical analysis of simple program."""
        code = """
function main() -> int {
    var x: int = 42;
    return x;
}
        """
        
        tokens = tokenize(code)
        self.assertGreater(len(tokens), 0)
        
        # Check for some expected tokens
        token_values = [token.value for token in tokens]
        self.assertIn('function', token_values)
        self.assertIn('main', token_values)
        self.assertIn('var', token_values)
        self.assertIn('42', token_values)
    
    def test_simple_parsing(self):
        """Test parsing of simple program."""
        code = """
function main() {
    var x: int = 42;
    return x;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        
        self.assertIsNotNone(ast)
        self.assertEqual(len(ast.declarations), 1)
    
    def test_simple_code_generation(self):
        """Test assembly generation."""
        code = """
function main() {
    var x: int = 42;
    return x;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        self.assertIsInstance(assembly, str)
        self.assertGreater(len(assembly), 0)
        self.assertIn('func_main', assembly)
    
    def test_lexer_error(self):
        """Test lexer error handling."""
        code = "function main() { var x = $invalid; }"  # $ is not a valid character
        
        with self.assertRaises(LexerError):
            tokenize(code)
    
    def test_parser_error(self):
        """Test parser error handling."""
        code = "function main() { var x = ; }"  # Missing value
        
        tokens = tokenize(code)
        with self.assertRaises(ParseError):
            parse(tokens)
    
    def test_arithmetic_operations(self):
        """Test arithmetic operations compilation."""
        code = """
function main() {
    var a: int = 10;
    var b: int = 5;
    var sum: int = a + b;
    var diff: int = a - b;
    var prod: int = a * b;
    var quot: int = a / b;
    return sum + diff + prod + quot;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        self.assertIn('ADD', assembly)
        self.assertIn('SUB', assembly)
        self.assertIn('MULT', assembly)
        self.assertIn('DIV', assembly)
    
    def test_control_flow(self):
        """Test control flow compilation."""
        code = """
function main() {
    var i: int = 0;
    var sum: int = 0;
    
    while (i < 10) {
        sum = sum + i;
        i = i + 1;
    }
    
    return sum;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        # Should contain jump instructions for while loop
        self.assertIn('JZ', assembly)
        self.assertIn('JMP', assembly)
    
    def test_function_calls(self):
        """Test function call compilation."""
        code = """
function add(a: int, b: int) {
    return a + b;
}

function main() {
    var result: int = add(5, 3);
    return result;
}
        """
        
        tokens = tokenize(code)
        ast = parse(tokens)
        assembly = generate_assembly(ast)
        
        # Should contain function labels and calls
        self.assertIn('func_add', assembly)
        self.assertIn('func_main', assembly)
        self.assertIn('JAL', assembly)  # Jump and link for function call


if __name__ == '__main__':
    unittest.main()