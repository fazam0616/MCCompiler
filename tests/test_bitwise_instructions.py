"""
Tests for bitwise instructions: AND, OR, XOR, NOT.

These operations work on 16-bit values and store results in register 0.
"""

import unittest
from test_assembly_framework import BaseAssemblyTestCase, AssemblyTestCase


class TestBitwiseInstructions(BaseAssemblyTestCase):
    """Test bitwise logical instructions."""
    
    def test_and_instruction(self):
        """Test AND instruction.""" 
        test_cases = [
            AssemblyTestCase(
                "and_basic_values",
                "AND i:15, i:7\nHALT",  # 1111 & 0111 = 0111 (7)
                {0: 7}
            ),
            AssemblyTestCase(
                "and_register_values",
                "MVR i:0xFF00, 1\nMVR i:0x00FF, 2\nAND 1, 2\nHALT",
                {0: 0, 1: 0xFF00, 2: 0x00FF}  # No bits in common
            ),
            AssemblyTestCase(
                "and_all_ones",
                "AND i:0xFFFF, i:0xAAAA\nHALT",  # All 1s & alternating
                {0: 0xAAAA}
            ),
            AssemblyTestCase(
                "and_with_zero",
                "AND i:12345, i:0\nHALT",
                {0: 0}
            ),
            AssemblyTestCase(
                "and_identical_values",
                "AND i:0x1234, i:0x1234\nHALT",
                {0: 0x1234}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_or_instruction(self):
        """Test OR instruction."""
        test_cases = [
            AssemblyTestCase(
                "or_basic_values", 
                "OR i:8, i:4\nHALT",  # 1000 | 0100 = 1100 (12)
                {0: 12}
            ),
            AssemblyTestCase(
                "or_register_values",
                "MVR i:0xFF00, 1\nMVR i:0x00FF, 2\nOR 1, 2\nHALT",
                {0: 0xFFFF, 1: 0xFF00, 2: 0x00FF}  # Combine all bits
            ),
            AssemblyTestCase(
                "or_with_zero",
                "OR i:12345, i:0\nHALT",
                {0: 12345}  # OR with 0 preserves value
            ),
            AssemblyTestCase(
                "or_with_all_ones",
                "OR i:0x5555, i:0xFFFF\nHALT",
                {0: 0xFFFF}  # OR with all 1s gives all 1s
            ),
            AssemblyTestCase(
                "or_complementary_patterns",
                "OR i:0xAAAA, i:0x5555\nHALT",  # Alternating patterns
                {0: 0xFFFF}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_xor_instruction(self):
        """Test XOR instruction."""
        test_cases = [
            AssemblyTestCase(
                "xor_basic_values",
                "XOR i:15, i:9\nHALT",  # 1111 ^ 1001 = 0110 (6)
                {0: 6}
            ),
            AssemblyTestCase(
                "xor_register_values",
                "MVR i:0xF0F0, 1\nMVR i:0x0F0F, 2\nXOR 1, 2\nHALT",
                {0: 0xFFFF, 1: 0xF0F0, 2: 0x0F0F}  # Complementary patterns
            ),
            AssemblyTestCase(
                "xor_with_zero",
                "XOR i:12345, i:0\nHALT",
                {0: 12345}  # XOR with 0 preserves value
            ),
            AssemblyTestCase(
                "xor_with_self",
                "MVR i:54321, 1\nXOR 1, 1\nHALT", 
                {0: 0, 1: 54321}  # XOR with self gives 0
            ),
            AssemblyTestCase(
                "xor_toggle_bits",
                "MVR i:0xAAAA, 1\nXOR 1, i:0xFFFF\nHALT",  # Toggle all bits
                {0: 0x5555, 1: 0xAAAA}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_not_instruction(self):
        """Test NOT instruction (unary bitwise complement)."""
        test_cases = [
            AssemblyTestCase(
                "not_basic_value",
                "MVR i:0, 1\nNOT 1\nHALT",
                {1: 0xFFFF}  # ~0 = all 1s in 16-bit
            ),
            AssemblyTestCase(
                "not_all_ones",
                "MVR i:0xFFFF, 1\nNOT 1\nHALT",
                {1: 0}  # ~(all 1s) = 0
            ),
            AssemblyTestCase(
                "not_register_value",
                "MVR i:0xAAAA, 1\nNOT 1\nHALT",
                {1: 0x5555}  # Flip alternating pattern
            ),
            AssemblyTestCase(
                "not_pattern",
                "MVR i:0xF0F0, 1\nNOT 1\nHALT",
                {1: 0x0F0F}  # Invert checker pattern
            ),
            AssemblyTestCase(
                "not_single_bit",
                "MVR i:0x0001, 1\nNOT 1\nHALT",
                {1: 0xFFFE}  # Flip single bit
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_shift_instructions(self):
        """Test SHL, SHR, SHLR shift instructions."""
        test_cases = [
            AssemblyTestCase(
                "shl_basic_shift",
                "SHL i:1, i:3\nHALT",  # 1 << 3 = 8
                {0: 8}
            ),
            AssemblyTestCase(
                "shl_register_shift",
                "MVR i:5, 1\nMVR i:2, 2\nSHL 1, 2\nHALT", 
                {0: 20, 1: 5, 2: 2}  # 5 << 2 = 20
            ),
            AssemblyTestCase(
                "shr_basic_shift",
                "SHR i:16, i:2\nHALT",  # 16 >> 2 = 4
                {0: 4}
            ),
            AssemblyTestCase(
                "shr_register_shift",
                "MVR i:100, 3\nMVR i:3, 4\nSHR 3, 4\nHALT",
                {0: 12, 3: 100, 4: 3}  # 100 >> 3 = 12
            ),
            AssemblyTestCase(
                "shlr_rotate_left",
                "SHLR i:0x8000, i:1\nHALT",  # Rotate MSB to LSB 
                {0: 1}  # 0x8000 rotated left by 1 = 0x0001
            ),
            AssemblyTestCase(
                "shlr_multi_rotate",
                "SHLR i:0x1234, i:4\nHALT",  # Rotate by nibble
                {0: 0x2341}  # Rotate 0x1234 left by 4 bits
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_bitwise_combinations(self):
        """Test combining multiple bitwise operations.""" 
        test_cases = [
            AssemblyTestCase(
                "and_then_or",
                "AND i:0xFF00, i:0xF0F0\nMVR 0, 1\nOR 1, i:0x000F\nHALT",
                {0: 0xF00F, 1: 0xF000}  # (0xFF00 & 0xF0F0) | 0x000F
            ),
            AssemblyTestCase(
                "xor_then_not", 
                "XOR i:0x5555, i:0x3333\nMVR 0, 2\nNOT 2\nHALT",
                {0: 0x6666, 2: 0x9999}  # ~(0x5555 ^ 0x3333)
            ),
            AssemblyTestCase(
                "shift_and_mask",
                "SHL i:0x000F, i:8\nMVR 0, 3\nAND 3, i:0xFF00\nHALT",
                {0: 0x0F00, 3: 0x0F00}  # (0x000F << 8) & 0xFF00
            )
        ]
        
        self.run_test_cases(test_cases)


if __name__ == '__main__':
    unittest.main()