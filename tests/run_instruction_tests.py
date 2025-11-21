"""
Comprehensive test runner for all CPU instruction tests.

Runs instruction tests in dependency order:
1. MVR (most basic, needed for all other tests)
2. Arithmetic instructions (ADD, SUB, MULT, DIV)  
3. Bitwise instructions (AND, OR, XOR, NOT, shifts)
4. Memory instructions (LOAD, READ, MVM)
5. Jump instructions (JMP, JAL, JBT, JZ, JNZ) - most complex
6. HALT instruction
"""

import unittest
import sys
import os

# Add the tests directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import all test modules
from test_mvr_instruction import TestMVRInstruction
from test_arithmetic_instructions import TestArithmeticInstructions  
from test_bitwise_instructions import TestBitwiseInstructions
from test_memory_instructions import TestMemoryInstructions
from test_jump_instructions import TestJumpInstructions
from test_halt_instruction import TestHaltInstruction


def create_test_suite():
    """Create test suite in dependency order."""
    suite = unittest.TestSuite()
    
    # Order tests by complexity and dependencies
    test_classes = [
        # 1. Most basic - MVR needed by everything
        TestMVRInstruction,
        
        # 2. Arithmetic - depends on MVR for operand setup
        TestArithmeticInstructions,
        
        # 3. Bitwise operations - depends on MVR 
        TestBitwiseInstructions,
        
        # 4. Memory operations - depends on MVR for addresses/values
        TestMemoryInstructions,
        
        # 5. Control flow - most complex, depends on arithmetic for conditions
        TestJumpInstructions,
        
        # 6. Program termination
        TestHaltInstruction,
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    return suite


def run_instruction_tests(verbosity=2):
    """Run all instruction tests with detailed output."""
    print("=" * 70)
    print("MCL CPU INSTRUCTION TEST SUITE")
    print("=" * 70)
    print()
    
    suite = create_test_suite()
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        stream=sys.stdout,
        descriptions=True,
        failfast=False
    )
    
    print(f"Running {suite.countTestCases()} instruction tests...")
    print()
    
    result = runner.run(suite)
    
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\nOVERALL: {'PASS' if success else 'FAIL'}")
    print("=" * 70)
    
    return success


def run_single_instruction_test(instruction_name, verbosity=2):
    """Run tests for a single instruction."""
    test_modules = {
        'mvr': TestMVRInstruction,
        'arithmetic': TestArithmeticInstructions,
        'bitwise': TestBitwiseInstructions,
        'memory': TestMemoryInstructions,
        'jump': TestJumpInstructions,
        'halt': TestHaltInstruction,
    }
    
    if instruction_name.lower() not in test_modules:
        print(f"Unknown instruction test: {instruction_name}")
        print(f"Available tests: {', '.join(test_modules.keys())}")
        return False
    
    test_class = test_modules[instruction_name.lower()]
    suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
    runner = unittest.TextTestRunner(verbosity=verbosity)
    
    print(f"Running {instruction_name.upper()} instruction tests...")
    result = runner.run(suite)
    
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run MCL CPU instruction tests')
    parser.add_argument('--instruction', '-i', type=str, 
                       help='Run tests for specific instruction (mvr, arithmetic, bitwise, memory, jump, halt)')
    parser.add_argument('--verbose', '-v', action='count', default=1,
                       help='Increase test verbosity')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Minimal output')
    
    args = parser.parse_args()
    
    verbosity = 0 if args.quiet else min(args.verbose + 1, 2)
    
    try:
        if args.instruction:
            success = run_single_instruction_test(args.instruction, verbosity)
        else:
            success = run_instruction_tests(verbosity)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)