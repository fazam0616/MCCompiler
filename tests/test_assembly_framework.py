"""
Assembly execution test framework for CPU instructions.

Tests CPU instruction execution by running assembly programs and checking register states.
"""

import unittest
import sys
import os
from typing import Dict, List, Any

# Add src to path to import VM components
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.vm.virtual_machine import VirtualMachine, create_vm
from src.vm.assembly_loader import load_assembly_string
from src.vm.cpu import CPUState


class AssemblyTestCase:
    """Represents a single assembly test case."""
    
    def __init__(self, name: str, assembly: str, expected_registers: Dict[int, int], 
                 expected_memory: Dict[int, int] = None, max_cycles: int = 1000):
        self.name = name
        self.assembly = assembly
        self.expected_registers = expected_registers
        self.expected_memory = expected_memory or {}
        self.max_cycles = max_cycles


def run_assembly_test(test_case: AssemblyTestCase) -> Dict[str, Any]:
    """Run an assembly test case and return results."""
    # Create VM
    config = {'enable_gpu': False}  # Headless for testing
    vm = create_vm(config)
    
    try:
        # Load and run assembly
        vm.reset()
        # instructions, labels = load_assembly_string(test_case.assembly)
        # vm.memory.load_program(instructions, labels)
        vm.load_program_string(test_case.assembly)
        vm.cpu.set_labels(vm.memory.labels)

        # Run with cycle limit
        vm.cpu.state = CPUState.RUNNING
        cycles = 0
        while vm.cpu.state == CPUState.RUNNING and cycles < test_case.max_cycles:
            if not vm.cpu.step():
                break
            cycles += 1
        
        # Collect results
        results = {
            'success': True,
            'cycles': cycles,
            'cpu_state': vm.cpu.state,
            'halt_reason': vm.cpu.halt_reason,
            'registers': vm.cpu.registers.copy(),
            'memory': {},
            'errors': []
        }
        
        # Check expected registers
        for reg_id, expected_value in test_case.expected_registers.items():
            actual_value = vm.cpu.get_register(reg_id)
            if actual_value != expected_value:
                results['errors'].append(
                    f"Register R{reg_id}: expected {expected_value}, got {actual_value}"
                )
        
        # Check expected memory
        for addr, expected_value in test_case.expected_memory.items():
            actual_value = vm.memory.read(addr)
            results['memory'][addr] = actual_value
            if actual_value != expected_value:
                results['errors'].append(
                    f"Memory[{addr}]: expected {expected_value}, got {actual_value}"
                )
        
        if results['errors']:
            results['success'] = False
            
    except Exception as e:
        results = {
            'success': False,
            'error': str(e),
            'errors': [str(e)]
        }
    
    finally:
        vm.shutdown()
    
    return results


class BaseAssemblyTestCase(unittest.TestCase):
    """Base class for assembly instruction tests."""
    
    def run_test_cases(self, test_cases: List[AssemblyTestCase]):
        """Run a list of test cases."""
        for test_case in test_cases:
            with self.subTest(test_case.name):
                results = run_assembly_test(test_case)
                
                if not results['success']:
                    error_msg = f"Test '{test_case.name}' failed:\n"
                    for error in results.get('errors', []):
                        error_msg += f"  - {error}\n"
                    if 'error' in results:
                        error_msg += f"  Exception: {results['error']}\n"
                    self.fail(error_msg)


if __name__ == '__main__':
    # Test the framework with a simple case
    test = AssemblyTestCase(
        "simple_mvr",
        "MVR i:42, 0\nHALT",
        {0: 42}
    )
    
    results = run_assembly_test(test)
    print(f"Test results: {results}")