"""
Comprehensive MCL Language Test Suite

Tests MCL language features including:
- Variable declaration and initialization
- Arithmetic operations
- Comparison operations
- Control flow (if/else, loops)
- Logical operations
- Bitwise operations
- Functions and recursion

Uses the MCL compiler to generate assembly and the VM to execute it.
"""

import unittest
import sys
import os
from typing import Dict, Tuple

# Add src to path to import compiler and VM components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.compiler.lexer import tokenize, LexerError
from src.compiler.parser import parse, ParseError
from src.compiler.assembly_generator import generate_assembly, CodeGenerationError
from src.vm.virtual_machine import VirtualMachine, create_vm
from src.vm.assembly_loader import load_assembly_string
from src.vm.cpu import CPUState


class MCLTestCase:
    """Represents a single MCL test case."""
    
    def __init__(self, name: str, mcl_code: str, expected_return_value: int, 
                 max_cycles: int = 10000):
        self.name = name
        self.mcl_code = mcl_code
        self.expected_return_value = expected_return_value
        self.max_cycles = max_cycles


def compile_and_run_mcl(mcl_code: str, max_cycles: int = 10000) -> Tuple[int, str]:
    """Compile MCL code and run it, returning the return value and any errors.
    
    Args:
        mcl_code: MCL source code
        max_cycles: Maximum CPU cycles to run
    
    Returns:
        Tuple of (return_value, error_message). If successful, error_message is empty.
    """
    try:
        # Compile MCL to assembly
        tokens = tokenize(mcl_code)
        ast = parse(tokens)
        assembly_code = generate_assembly(ast)
        
        # Create and run VM
        config = {'enable_gpu': False}  # Headless for testing
        vm = create_vm(config)
        
        try:
            # Load and run assembly
            # instructions, labels = load_assembly_string()
            vm.reset()
            vm.load_program_string(assembly_code)
            
            # Run with cycle limit
            vm.cpu.state = CPUState.RUNNING
            cycles = 0
            while vm.cpu.state == CPUState.RUNNING and cycles < max_cycles:
                if not vm.cpu.step():
                    break
                cycles += 1
            
            # Get return value from register 0
            return_value = vm.cpu.get_register(0)
            
            if cycles >= max_cycles:
                return return_value, f"Exceeded max cycles ({max_cycles})"
            
            return return_value, ""
            
        finally:
            vm.shutdown()
            
    except LexerError as e:
        return 0, f"Lexer Error: {e}"
    except ParseError as e:
        return 0, f"Parse Error: {e}"
    except CodeGenerationError as e:
        return 0, f"Code Generation Error: {e}"
    except Exception as e:
        return 0, f"Runtime Error: {e}"


def run_mcl_test(test_case: MCLTestCase) -> Dict:
    """Run an MCL test case and return results."""
    return_value, error = compile_and_run_mcl(test_case.mcl_code, test_case.max_cycles)
    
    success = (error == "") and (return_value == test_case.expected_return_value)
    
    return {
        'success': success,
        'return_value': return_value,
        'expected_value': test_case.expected_return_value,
        'error': error
    }


class BaseMCLTestCase(unittest.TestCase):
    """Base class for MCL language tests."""
    
    def run_mcl_tests(self, test_cases: list):
        """Run a list of MCL test cases."""
        for test_case in test_cases:
            with self.subTest(test_case.name):
                results = run_mcl_test(test_case)
                
                if not results['success']:
                    error_msg = f"Test '{test_case.name}' failed:\n"
                    error_msg += f"  Expected return value: {results['expected_value']}\n"
                    error_msg += f"  Actual return value: {results['return_value']}\n"
                    if results['error']:
                        error_msg += f"  Error: {results['error']}\n"
                    self.fail(error_msg)


class TestVariableDeclaration(BaseMCLTestCase):
    """Test variable declaration and initialization."""
    
    def test_basic_integer_declaration(self):
        """Test MCL-VAR-001: Basic integer declaration."""
        test_cases = [
            MCLTestCase(
                "basic_integer_declaration",
                """
function main() {
    var age: int = 25;
    return age;
}
                """,
                25
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_c_style_declaration(self):
        """Test MCL-VAR-002: C-style variable declaration."""
        test_cases = [
            MCLTestCase(
                "c_style_declaration",
                """
function main() {
    int count = 10;
    return count;
}
                """,
                10
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_character_literal(self):
        """Test MCL-VAR-003: Character variable with escape sequence."""
        test_cases = [
            MCLTestCase(
                "character_literal",
                """
function main() {
    var letter: char = 'A';
    return letter;
}
                """,
                65  # ASCII value of 'A'
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_uninitialized_variable(self):
        """Test MCL-VAR-004: Uninitialized variable."""
        test_cases = [
            MCLTestCase(
                "uninitialized_variable",
                """
function main() {
    var x: int;
    return 0;
}
                """,
                0
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_multiple_variables(self):
        """Test MCL-VAR-005: Multiple variable declarations."""
        test_cases = [
            MCLTestCase(
                "multiple_variables",
                """
function main() {
    var a: int = 5;
    var b: int = 10;
    var c: int = 15;
    return a + b + c;
}
                """,
                30
            ),
        ]
        self.run_mcl_tests(test_cases)


class TestArithmeticOperations(BaseMCLTestCase):
    """Test arithmetic operations."""
    
    def test_addition(self):
        """Test MCL-ARITH-001: Addition."""
        test_cases = [
            MCLTestCase(
                "simple_addition",
                """
function main() {
    var x: int = 10;
    var y: int = 20;
    return x + y;
}
                """,
                30
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_subtraction(self):
        """Test MCL-ARITH-002: Subtraction."""
        test_cases = [
            MCLTestCase(
                "simple_subtraction",
                """
function main() {
    var x: int = 30;
    var y: int = 12;
    return x - y;
}
                """,
                18
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_multiplication(self):
        """Test MCL-ARITH-003: Multiplication."""
        test_cases = [
            MCLTestCase(
                "simple_multiplication",
                """
function main() {
    var x: int = 6;
    var y: int = 7;
    return x * y;
}
                """,
                42
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_division(self):
        """Test MCL-ARITH-004: Division."""
        test_cases = [
            MCLTestCase(
                "simple_division",
                """
function main() {
    var x: int = 100;
    var y: int = 4;
    return x / y;
}
                """,
                25
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_modulo(self):
        """Test MCL-ARITH-005: Modulo operation."""
        test_cases = [
            MCLTestCase(
                "simple_modulo",
                """
function main() {
    var x: int = 17;
    var y: int = 5;
    return x % y;
}
                """,
                2
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_mixed_arithmetic(self):
        """Test MCL-ARITH-006: Mixed arithmetic expression."""
        test_cases = [
            MCLTestCase(
                "mixed_arithmetic",
                """
function main() {
    var result: int = 10 + 5 * 2 - 8 / 2;
    return result;
}
                """,
                16  # 10 + 10 - 4 = 16
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_operator_precedence(self):
        """Test MCL-ARITH-007: Operator precedence."""
        test_cases = [
            MCLTestCase(
                "operator_precedence",
                """
function main() {
    var x: int = 2 + 3 * 4;
    return x;
}
                """,
                14  # 2 + 12 = 14, not 20
            ),
        ]
        self.run_mcl_tests(test_cases)


class TestComparisonOperations(BaseMCLTestCase):
    """Test comparison operations."""
    
    def test_equality_true(self):
        """Test MCL-CMP-001: Equality comparison (true)."""
        test_cases = [
            MCLTestCase(
                "equality_true",
                """
function main() {
    var x: int = 5;
    var y: int = 5;
    if (x == y) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_equality_false(self):
        """Test MCL-CMP-002: Equality comparison (false)."""
        test_cases = [
            MCLTestCase(
                "equality_false",
                """
function main() {
    var x: int = 5;
    var y: int = 10;
    if (x == y) {
        return 1;
    }
    return 0;
}
                """,
                0
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_not_equal(self):
        """Test MCL-CMP-003: Not equal comparison."""
        test_cases = [
            MCLTestCase(
                "not_equal",
                """
function main() {
    var x: int = 5;
    var y: int = 10;
    if (x != y) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_greater_than(self):
        """Test MCL-CMP-004: Greater than comparison."""
        test_cases = [
            MCLTestCase(
                "greater_than",
                """
function main() {
    var x: int = 10;
    var y: int = 5;
    if (x > y) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_less_than(self):
        """Test MCL-CMP-005: Less than comparison."""
        test_cases = [
            MCLTestCase(
                "less_than",
                """
function main() {
    var x: int = 3;
    var y: int = 10;
    if (x < y) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_greater_equal(self):
        """Test MCL-CMP-006: Greater than or equal."""
        test_cases = [
            MCLTestCase(
                "greater_equal",
                """
function main() {
    var x: int = 5;
    var y: int = 5;
    if (x >= y) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_less_equal(self):
        """Test MCL-CMP-007: Less than or equal."""
        test_cases = [
            MCLTestCase(
                "less_equal",
                """
function main() {
    var x: int = 5;
    var y: int = 5;
    if (x <= y) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)


class TestControlFlow(BaseMCLTestCase):
    """Test control flow statements."""
    
    def test_simple_if(self):
        """Test MCL-IF-001: Simple if statement."""
        test_cases = [
            MCLTestCase(
                "simple_if",
                """
function main() {
    var x: int = 10;
    if (x > 5) {
        return 100;
    }
    return 0;
}
                """,
                100
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_if_else(self):
        """Test MCL-IF-002: If-else statement."""
        test_cases = [
            MCLTestCase(
                "if_else",
                """
function main() {
    var x: int = 3;
    if (x > 5) {
        return 100;
    } else {
        return 200;
    }
}
                """,
                200
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_if_else_if_else(self):
        """Test MCL-IF-003: If-else if-else chain."""
        test_cases = [
            MCLTestCase(
                "if_else_if_else",
                """
function main() {
    var x: int = 15;
    if (x < 10) {
        return 1;
    } else if (x < 20) {
        return 2;
    } else {
        return 3;
    }
}
                """,
                2
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_nested_if(self):
        """Test MCL-IF-004: Nested if statements."""
        test_cases = [
            MCLTestCase(
                "nested_if",
                """
function main() {
    var x: int = 10;
    var y: int = 20;
    if (x < 15) {
        if (y > 15) {
            return 1;
        }
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)


class TestLogicalOperations(BaseMCLTestCase):
    """Test logical operations."""
    
    def test_logical_and_true(self):
        """Test MCL-LOG-001: Logical AND (true && true)."""
        test_cases = [
            MCLTestCase(
                "logical_and_true",
                """
function main() {
    if (1 && 1) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_logical_and_false(self):
        """Test MCL-LOG-002: Logical AND (true && false)."""
        test_cases = [
            MCLTestCase(
                "logical_and_false",
                """
function main() {
    if (1 && 0) {
        return 1;
    }
    return 0;
}
                """,
                0
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_logical_or_true(self):
        """Test MCL-LOG-003: Logical OR (false || true)."""
        test_cases = [
            MCLTestCase(
                "logical_or_true",
                """
function main() {
    if (0 || 1) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_logical_or_false(self):
        """Test MCL-LOG-004: Logical OR (false || false)."""
        test_cases = [
            MCLTestCase(
                "logical_or_false",
                """
function main() {
    if (0 || 0) {
        return 1;
    }
    return 0;
}
                """,
                0
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_logical_not_true(self):
        """Test MCL-LOG-005: Logical NOT (!)."""
        test_cases = [
            MCLTestCase(
                "logical_not_true",
                """
function main() {
    var x: int = 0;
    if (!x) {
        return 1;
    }
    return 0;
}
                """,
                1
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_logical_not_false(self):
        """Test MCL-LOG-006: Logical NOT on true value."""
        test_cases = [
            MCLTestCase(
                "logical_not_false",
                """
function main() {
    var x: int = 5;
    if (!x) {
        return 1;
    }
    return 0;
}
                """,
                0
            ),
        ]
        self.run_mcl_tests(test_cases)


class TestBitwiseOperations(BaseMCLTestCase):
    """Test bitwise operations."""
    
    def test_bitwise_and(self):
        """Test MCL-BIT-001: Bitwise AND."""
        test_cases = [
            MCLTestCase(
                "bitwise_and",
                """
function main() {
    var x: int = 12;  // 1100
    var y: int = 10;  // 1010
    return x & y;     // 1000 = 8
}
                """,
                8
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_bitwise_or(self):
        """Test MCL-BIT-002: Bitwise OR."""
        test_cases = [
            MCLTestCase(
                "bitwise_or",
                """
function main() {
    var x: int = 12;  // 1100
    var y: int = 10;  // 1010
    return x | y;     // 1110 = 14
}
                """,
                14
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_bitwise_xor(self):
        """Test MCL-BIT-003: Bitwise XOR."""
        test_cases = [
            MCLTestCase(
                "bitwise_xor",
                """
function main() {
    var x: int = 12;  // 1100
    var y: int = 10;  // 1010
    return x ^ y;     // 0110 = 6
}
                """,
                6
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_left_shift(self):
        """Test MCL-BIT-005: Left shift."""
        test_cases = [
            MCLTestCase(
                "left_shift",
                """
function main() {
    var x: int = 5;  // 0101
    return x << 2;   // 10100 = 20
}
                """,
                20
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_right_shift(self):
        """Test MCL-BIT-006: Right shift."""
        test_cases = [
            MCLTestCase(
                "right_shift",
                """
function main() {
    var x: int = 20;  // 10100
    return x >> 2;    // 0101 = 5
}
                """,
                5
            ),
        ]
        self.run_mcl_tests(test_cases)


class TestLoops(BaseMCLTestCase):
    """Test loop constructs."""
    
    def test_while_loop(self):
        """Test MCL-LOOP-001: Simple while loop."""
        test_cases = [
            MCLTestCase(
                "while_loop",
                """
function main() {
    var i: int = 0;
    var sum: int = 0;
    while (i < 5) {
        sum = sum + i;
        i = i + 1;
    }
    return sum;  // 0+1+2+3+4 = 10
}
                """,
                10,
                max_cycles=1000
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_for_loop(self):
        """Test MCL-LOOP-FOR-001: Simple for loop."""
        test_cases = [
            MCLTestCase(
                "for_loop",
                """
function main() {
    var sum: int = 0;
    for (var i: int = 0; i < 5; i = i + 1) {
        sum = sum + i;
    }
    return sum;  // 0+1+2+3+4 = 10
}
                """,
                10,
                max_cycles=1000
            ),
        ]
        self.run_mcl_tests(test_cases)


class TestFunctions(BaseMCLTestCase):
    """Test function declarations and calls."""
    
    def test_function_with_parameters(self):
        """Test MCL-FUNC-001: Function with parameters."""
        test_cases = [
            MCLTestCase(
                "function_with_parameters",
                """
function add(a: int, b: int) {
    return a + b;
}

function main() {
    return add(10, 15);
}
                """,
                25
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_multiple_function_calls(self):
        """Test MCL-FUNC-004: Multiple function calls."""
        test_cases = [
            MCLTestCase(
                "multiple_function_calls",
                """
function triple(x: int) {
    return x * 3;
}

function add_five(x: int) {
    return x + 5;
}

function main() {
    var result: int = triple(10);      // 30
    result = add_five(result);         // 35
    return result;
}
                """,
                35
            ),
        ]
        self.run_mcl_tests(test_cases)
    
    def test_recursive_function(self):
        """Test MCL-FUNC-003: Recursive function."""
        test_cases = [
            MCLTestCase(
                "recursive_function",
                """
function factorial(n: int) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

function main() {
    return factorial(5);  // 5! = 120
}
                """,
                120,
                max_cycles=5000
            ),
        ]
        self.run_mcl_tests(test_cases)


if __name__ == '__main__':
    unittest.main(verbosity=2)
