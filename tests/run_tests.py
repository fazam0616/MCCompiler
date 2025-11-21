#!/usr/bin/env python3
"""Test runner for MCL compiler toolchain.
"""

import sys
import os
import unittest
import subprocess
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def run_unit_tests():
    """Run all unit tests."""
    print("Running unit tests...")
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


# def run_integration_tests():
#     """Run integration tests with example files."""
#     print("\nRunning integration tests...")
    
#     examples_dir = Path(__file__).parent.parent / 'examples'
#     compiler_path = Path(__file__).parent.parent / 'src' / 'compiler' / 'main.py'
    
#     success = True
    
#     for mcl_file in examples_dir.glob('*.mcl'):
#         print(f"Testing compilation of {mcl_file.name}...")
        
#         try:
#             # Try to compile the example
#             result = subprocess.run([
#                 sys.executable, str(compiler_path),
#                 str(mcl_file)
#             ], capture_output=True, text=True, timeout=30)
            
#             if result.returncode != 0:
#                 print(f"FAILED: {mcl_file.name}")
#                 print(f"Error: {result.stderr}")
#                 success = False
#             else:
#                 print(f"PASSED: {mcl_file.name}")
                
#         except subprocess.TimeoutExpired:
#             print(f"TIMEOUT: {mcl_file.name}")
#             success = False
#         except Exception as e:
#             print(f"ERROR: {mcl_file.name} - {e}")
#             success = False
    
#     return success


# def run_vm_tests():
#     """Test virtual machine with example assembly."""
#     print("\nRunning VM tests...")
    
#     examples_dir = Path(__file__).parent.parent / 'examples'
#     vm_path = Path(__file__).parent.parent / 'src' / 'vm' / 'virtual_machine.py'
    
#     success = True
    
#     for asm_file in examples_dir.glob('*.asm'):
#         print(f"Testing VM execution of {asm_file.name}...")
        
#         try:
#             # Try to run the assembly in VM
#             result = subprocess.run([
#                 sys.executable, str(vm_path),
#                 '--file', str(asm_file),
#                 '--headless'  # Run without graphics
#             ], capture_output=True, text=True, timeout=10)
            
#             if result.returncode != 0:
#                 print(f"FAILED: {asm_file.name}")
#                 print(f"Error: {result.stderr}")
#                 success = False
#             else:
#                 print(f"PASSED: {asm_file.name}")
                
#         except subprocess.TimeoutExpired:
#             print(f"TIMEOUT: {asm_file.name}")
#             success = False
#         except Exception as e:
#             print(f"ERROR: {asm_file.name} - {e}")
#             success = False
    
#     return success


def run_instruction_tests():
    """Run CPU instruction tests.""" 
    print("\nRunning CPU instruction tests...")
    
    try:
        from run_instruction_tests import run_instruction_tests as run_cpu_tests
        return run_cpu_tests(verbosity=1)
    except ImportError as e:
        print(f"Could not import instruction tests: {e}")
        return False
    except Exception as e:
        print(f"Error running instruction tests: {e}")
        return False


def main():
    """Run all tests."""
    print("MCL Compiler Toolchain Test Suite")
    print("=" * 40)
    
    all_passed = True
    
    # Run unit tests
    if not run_unit_tests():
        all_passed = False
    
    # Run CPU instruction tests  
    if not run_instruction_tests():
        all_passed = False
    
    # Run integration tests
    # if not run_integration_tests():
    #     all_passed = False
    
    # Run VM tests
    # if not run_vm_tests():
    #     all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("All tests PASSED! ✅")
        sys.exit(0)
    else:
        print("Some tests FAILED! ❌")
        sys.exit(1)


if __name__ == '__main__':
    main()