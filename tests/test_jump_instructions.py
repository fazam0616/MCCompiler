"""
Tests for jump and control flow instructions: JMP, JAL, JBT, JZ, JNZ.

These are the most complex instructions as they depend on labels and program flow.
JMP should be tested with:
- Labels (most common)
- Immediate addresses (line numbers) 
- Register values (computed jumps)
- Boundary conditions
"""

import unittest
from test_assembly_framework import BaseAssemblyTestCase, AssemblyTestCase


class TestJumpInstructions(BaseAssemblyTestCase):
    """Test jump and control flow instructions."""
    
    def test_jmp_with_labels(self):
        """Test JMP instruction using labels."""
        test_cases = [
            AssemblyTestCase(
                "jmp_forward_label",
                "MVR i:1, 0\nskip_ahead:\nMVR i:2, 1\nJMP end\nMVR i:99, 2\nend:\nHALT", 
                {0: 1, 1: 2, 2: 0}  # R2 should not be set to 99
            ),
            AssemblyTestCase(
                "jmp_backward_label",
                "MVR i:3, 10\nloop_start:\nSUB 10, i:1\nMVR 0, 10\nJNZ loop_start, 10\nHALT",
                {0: 0, 10: 0}  # Count down from 3: 3->2->1->0, exit when R10 becomes 0
            ),
            AssemblyTestCase(
                "jmp_skip_instructions",
                "JMP target\nMVR i:100, 0\nMVR i:200, 1\ntarget:\nMVR i:42, 2\nHALT",
                {0: 0, 1: 0, 2: 42}  # Skip the MVR instructions  
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_jmp_with_immediate_addresses(self):
        """Test JMP with immediate line numbers."""
        test_cases = [
            AssemblyTestCase(
                "jmp_immediate_forward",
                "MVR i:1, 0\nJMP i:3\nMVR i:99, 1\nMVR i:2, 2\nHALT",
                {0: 1, 1: 0, 2: 2}  # Skip line 2, execute line 3
            ),
            AssemblyTestCase(
                "jmp_immediate_to_halt",
                "MVR i:42, 0\nJMP i:3\nMVR i:99, 1\nHALT",
                {0: 42, 1: 0}  # Jump directly to HALT
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_jmp_with_register_values(self):
        """Test JMP with computed addresses from registers."""
        test_cases = [
            AssemblyTestCase(
                "jmp_register_address",
                "MVR i:3, 0\nJMP 0\nMVR i:99, 1\nMVR i:5, 2\nHALT",
                {0: 3, 1: 0, 2: 5}  # Jump to line in R0
            ),
            AssemblyTestCase(
                "jmp_computed_address",
                "ADD i:2, i:1\nJMP 0\nMVR i:88, 3\nMVR i:77, 4\nHALT",  # Jump to line 3 (2+1)
                {0: 3, 3: 0, 4: 77}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_jal_instruction(self):
        """Test JAL (Jump and Link) instruction."""
        test_cases = [
            AssemblyTestCase(
                "jal_basic_call",
                "JAL subroutine\nMVR i:99, 3\nHALT\nsubroutine:\nMVR i:42, 5\nHALT",
                {2: 1, 5: 42, 3: 0}  # Return address in R2, subroutine executes
            ),
            AssemblyTestCase(
                "jal_with_return",
                "MVR i:10, 0\nJAL func\nMVR i:20, 4\nHALT\nfunc:\nMVR i:5, 3\nJMP 2",  # Return using saved address in R2
                {0: 10, 2: 2, 3: 5, 4: 20}  # Should return and execute MVR i:20, 4
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_jz_instruction(self):
        """Test JZ (Jump if Zero) instruction."""
        test_cases = [
            AssemblyTestCase(
                "jz_zero_value_jumps",
                "MVR i:0, 0\nJZ target, 0\nMVR i:99, 1\ntarget:\nMVR i:42, 2\nHALT",
                {0: 0, 1: 0, 2: 42}  # Should jump because R0 == 0
            ),
            AssemblyTestCase(
                "jz_nonzero_value_no_jump",
                "MVR i:5, 0\nJZ target, 0\nMVR i:33, 1\ntarget:\nMVR i:44, 2\nHALT",
                {0: 5, 1: 33, 2: 44}  # Should not jump, execute both MVRs
            ),
            AssemblyTestCase(
                "jz_with_arithmetic_result",
                "SUB i:10, i:10\nJZ zero_target, 0\nMVR i:88, 3\nzero_target:\nMVR i:77, 4\nHALT",
                {0: 0, 3: 0, 4: 77}  # SUB gives 0, should jump
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_jnz_instruction(self):
        """Test JNZ (Jump if Not Zero) instruction."""
        test_cases = [
            AssemblyTestCase(
                "jnz_nonzero_value_jumps",
                "MVR i:7, 0\nJNZ target, 0\nMVR i:11, 1\ntarget:\nMVR i:22, 2\nHALT",
                {0: 7, 1: 0, 2: 22}  # Should jump because R0 != 0
            ),
            AssemblyTestCase(
                "jnz_zero_value_no_jump",
                "MVR i:0, 0\nJNZ target, 0\nMVR i:33, 1\ntarget:\nMVR i:44, 2\nHALT",
                {0: 0, 1: 33, 2: 44}  # Should not jump, execute both MVRs
            ),
            AssemblyTestCase(
                "jnz_with_arithmetic_result",
                "SUB i:15, i:10\nJNZ nonzero_target, 0\nMVR i:66, 3\nnonzero_target:\nMVR i:55, 4\nHALT",
                {0: 5, 3: 0, 4: 55}  # SUB gives 5, should jump
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_jbt_instruction(self):
        """Test JBT (Jump if Better/Greater Than) instruction."""
        test_cases = [
            AssemblyTestCase(
                "jbt_greater_than_jumps",
                "MVR i:10, 1\nMVR i:5, 2\nJBT target, 1, 2\nMVR i:99, 3\ntarget:\nMVR i:42, 4\nHALT",
                {1: 10, 2: 5, 3: 0, 4: 42}  # 10 > 5, should jump
            ),
            AssemblyTestCase(
                "jbt_equal_values_no_jump",
                "MVR i:8, 1\nMVR i:8, 2\nJBT target, 1, 2\nMVR i:33, 3\ntarget:\nMVR i:44, 4\nHALT",
                {1: 8, 2: 8, 3: 33, 4: 44}  # 8 == 8, should not jump
            ),
            AssemblyTestCase(
                "jbt_less_than_no_jump",
                "MVR i:3, 1\nMVR i:7, 2\nJBT target, 1, 2\nMVR i:55, 3\ntarget:\nMVR i:66, 4\nHALT",
                {1: 3, 2: 7, 3: 55, 4: 66}  # 3 < 7, should not jump
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_complex_control_flow(self):
        """Test complex control flow patterns."""
        test_cases = [
            AssemblyTestCase(
                "simple_loop_with_counter",
                # Count from 0 to 3 using JBT comparison
                "MVR i:3, 1\nMVR i:0, 0\nloop:\nADD 0, i:1\nMVR 0, 0\nJBT loop, 1, 0\nHALT",
                {0: 3, 1: 3},
                max_cycles=50
            ),
            AssemblyTestCase(
                "conditional_branch_tree",
                "MVR i:2, 0\nSUB 0, i:1\nJZ case_one, 0\nSUB 0, i:1\nJZ case_two, 0\nJMP default_case\ncase_one:\nMVR i:10, 5\nJMP done\ncase_two:\nMVR i:20, 5\nJMP done\ndefault_case:\nMVR i:30, 5\ndone:\nHALT",
                {0: 0, 5: 20}  # Should hit case_two (2-1-1=0)
            ),
            AssemblyTestCase(
                "nested_jumps",
                "JMP outer\nMVR i:1, 0\nouter:\nJMP inner\nMVR i:2, 0\ninner:\nMVR i:3, 0\nHALT",
                {0: 3}  # Should only execute the final MVR
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_jump_boundary_conditions(self):
        """Test jump instructions at program boundaries."""
        test_cases = [
            AssemblyTestCase(
                "jump_to_first_instruction",
                "MVR i:1, 0\nJMP i:0\nMVR i:2, 0\nHALT",  # Should create infinite loop but limited by max_cycles
                {0: 1},
                max_cycles=10
            ),
            AssemblyTestCase(
                "jump_to_halt",
                "MVR i:42, 0\nJMP i:3\nMVR i:99, 1\nHALT",
                {0: 42, 1: 0}  # Jump directly to HALT
            )
        ]
        
        self.run_test_cases(test_cases)


if __name__ == '__main__':
    unittest.main()