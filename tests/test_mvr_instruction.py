"""
Tests for MVR (Move to Register) instruction.

MVR is the most fundamental instruction, so it's tested first.
Format: MVR source, destination
- MVR i:value, register (immediate to register)
- MVR register, i:value (not standard, but handle gracefully)  
- MVR register, register (register to register)
"""

import unittest
from test_assembly_framework import BaseAssemblyTestCase, AssemblyTestCase


class TestMVRInstruction(BaseAssemblyTestCase):
    """Test MVR instruction in all its forms."""
    
    def test_mvr_immediate_to_register(self):
        """Test MVR with immediate value to register."""
        test_cases = [
            AssemblyTestCase(
                "mvr_immediate_basic",
                "MVR i:42, 0\nHALT",
                {0: 42}
            ),
            AssemblyTestCase(
                "mvr_immediate_large",
                "MVR i:65535, 1\nHALT", 
                {1: 65535}
            ),
            AssemblyTestCase(
                "mvr_immediate_zero",
                "MVR i:0, 2\nHALT",
                {2: 0}
            ),
            AssemblyTestCase(
                "mvr_immediate_hex",
                "MVR i:0xFF, 3\nHALT",
                {3: 255}
            ),
            AssemblyTestCase(
                "mvr_immediate_multiple",
                "MVR i:10, 0\nMVR i:20, 1\nMVR i:30, 2\nHALT",
                {0: 10, 1: 20, 2: 30}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_mvr_register_to_register(self):
        """Test MVR between registers."""
        test_cases = [
            AssemblyTestCase(
                "mvr_reg_to_reg_basic",
                "MVR i:100, 0\nMVR 0, 1\nHALT",
                {0: 100, 1: 100}
            ),
            AssemblyTestCase(
                "mvr_reg_chain",
                "MVR i:42, 0\nMVR 0, 1\nMVR 1, 2\nMVR 2, 3\nHALT",
                {0: 42, 1: 42, 2: 42, 3: 42}
            ),
            AssemblyTestCase(
                "mvr_reg_overwrite",
                "MVR i:10, 0\nMVR i:20, 1\nMVR 1, 0\nHALT",
                {0: 20, 1: 20}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_mvr_16bit_overflow(self):
        """Test MVR with 16-bit overflow handling."""
        test_cases = [
            AssemblyTestCase(
                "mvr_overflow_wrap", 
                "MVR i:65536, 0\nHALT",  # Should wrap to 0
                {0: 0}
            ),
            AssemblyTestCase(
                "mvr_overflow_large",
                "MVR i:65537, 0\nHALT",  # Should wrap to 1  
                {0: 1}
            ),
            AssemblyTestCase(
                "mvr_negative_as_unsigned",
                "MVR i:-1, 0\nHALT",  # Should be treated as 65535
                {0: 65535}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_mvr_all_registers(self):
        """Test MVR to all 32 registers."""
        assembly = []
        expected = {}
        
        # Test all 32 registers
        for i in range(32):
            value = i * 10
            assembly.append(f"MVR i:{value}, {i}")
            expected[i] = value
        
        assembly.append("HALT")
        
        test_case = AssemblyTestCase(
            "mvr_all_registers",
            "\n".join(assembly),
            expected
        )
        
        self.run_test_cases([test_case])
    
    def test_mvr_register_boundary(self):
        """Test MVR with boundary register numbers."""
        test_cases = [
            AssemblyTestCase(
                "mvr_register_0",
                "MVR i:123, 0\nHALT",
                {0: 123}
            ),
            AssemblyTestCase(
                "mvr_register_31", 
                "MVR i:456, 31\nHALT",
                {31: 456}
            ),
            AssemblyTestCase(
                "mvr_first_last_registers",
                "MVR i:100, 0\nMVR i:200, 31\nMVR 0, 15\nMVR 31, 16\nHALT",
                {0: 100, 31: 200, 15: 100, 16: 200}
            )
        ]
        
        self.run_test_cases(test_cases)


if __name__ == '__main__':
    unittest.main()