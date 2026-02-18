"""
Tests for HALT instruction.

The HALT instruction stops program execution and sets CPU state to STOPPED.
"""

import unittest
from test_assembly_framework import BaseAssemblyTestCase, AssemblyTestCase, run_assembly_test
from src.vm.cpu import CPUState


class TestHaltInstruction(BaseAssemblyTestCase):
    """Test HALT instruction."""
    
    def test_halt_basic(self):
        """Test basic HALT functionality."""
        test_cases = [
            AssemblyTestCase(
                "halt_immediately",
                "HALT",
                {}  # No register changes expected
            ),
            AssemblyTestCase(
                "halt_after_operations",
                "MVR i:42, 0\nMVR i:99, 1\nHALT",
                {0: 42, 1: 99}
            ),
            AssemblyTestCase(
                "halt_skips_remaining",
                "MVR i:10, 0\nHALT\nMVR i:20, 1",  # Should not execute last MVR
                {0: 10, 1: 0}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_halt_state_checking(self):
        """Test that HALT properly sets CPU state."""
        test_case = AssemblyTestCase(
            "halt_state_check",
            "MVR i:123, 5\nHALT\nMVR i:456, 6",
            {5: 123, 6: 0}
        )
        
        results = run_assembly_test(test_case)
        
        # Verify CPU stopped with HALT
        self.assertEqual(results['cpu_state'], CPUState.STOPPED)
        self.assertEqual(results['halt_reason'], "HALT instruction executed")
        self.assertTrue(results['success'])
    
    def test_halt_in_control_flow(self):
        """Test HALT within control flow structures."""
        test_cases = [
            AssemblyTestCase(
                "halt_in_conditional",
                "MVR i:0, 0\nJZ halt_now, 0\nMVR i:99, 1\nhalt_now:\nHALT\nMVR i:88, 2",
                {0: 0, 1: 0, 2: 0}  # Should jump to HALT, skip both MVRs after
            ),
            AssemblyTestCase(
                "halt_in_loop_break",
                "MVR i:2, 10\nloop:\nSUB 10, i:1\nMVR 0, 10\nJZ break_loop, 10\nJMP loop\nbreak_loop:\nHALT\nMVR i:999, 5",
                {0: 0, 10: 0, 5: 0}  # Count down from 2: 2->1->0, then halt
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_halt_with_subroutines(self):
        """Test HALT in subroutine contexts."""
        test_cases = [
            AssemblyTestCase(
                "halt_in_subroutine",
                "JAL subroutine\nMVR i:999, 3\nHALT\nsubroutine:\nMVR i:42, 5\nHALT",  # HALT in subroutine
                {2: 1, 5: 42, 3: 0}  # Should not return to main, return address in R2
            ),
            AssemblyTestCase(
                "halt_after_subroutine_return",
                "MVR i:10, 0\nJAL func\nMVR i:20, 4\nHALT\nfunc:\nMVR i:5, 3\nJMP 2",  # Return then halt using R2
                {0: 10, 2: 2, 3: 5, 4: 20}  # Should execute normally then halt
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_multiple_halt_paths(self):
        """Test programs with multiple possible HALT locations."""
        test_cases = [
            AssemblyTestCase(
                "multiple_halt_conditions",
                "MVR i:1, 1\nSUB 1, i:1\nJZ path_a, 0\nJZ path_b, 0\npath_a:\nMVR i:100, 5\nHALT\npath_b:\nMVR i:200, 5\nHALT",
                {0: 0, 1: 1, 5: 100}  # SUB result (0) goes to R0, should take path_a
            ),
            AssemblyTestCase(
                "conditional_halt_or_continue",
                "MVR i:0, 0\nJZ early_halt, 0\nMVR i:50, 2\nHALT\nearly_halt:\nMVR i:25, 2\nHALT",
                {0: 0, 2: 25}  # Should take early_halt path
            )
        ]
        
        self.run_test_cases(test_cases)


if __name__ == '__main__':
    unittest.main()