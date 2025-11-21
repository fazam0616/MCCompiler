"""
Tests for arithmetic instructions: ADD, SUB, MULT, DIV.

These are tested after MVR since they depend on it to set up operands.
All arithmetic operations store results in register 0 (RETURN_VALUE_REG).
MULT and DIV use register 1 (SECONDARY_RETURN_REG) for overflow/remainder.
"""

import unittest
from test_assembly_framework import BaseAssemblyTestCase, AssemblyTestCase


class TestArithmeticInstructions(BaseAssemblyTestCase):
    """Test arithmetic instructions."""
    
    def test_add_instruction(self):
        """Test ADD instruction."""
        test_cases = [
            AssemblyTestCase(
                "add_immediate_values",
                "ADD i:10, i:20\nHALT",
                {0: 30}  # Result in RETURN_VALUE_REG
            ),
            AssemblyTestCase(
                "add_register_values", 
                "MVR i:15, 1\nMVR i:25, 2\nADD 1, 2\nHALT",
                {0: 40, 1: 15, 2: 25}
            ),
            AssemblyTestCase(
                "add_mixed_operands",
                "MVR i:100, 3\nADD i:50, 3\nHALT", 
                {0: 150, 3: 100}
            ),
            AssemblyTestCase(
                "add_zero_values",
                "ADD i:0, i:0\nHALT",
                {0: 0}
            ),
            AssemblyTestCase(
                "add_large_values",
                "ADD i:30000, i:30000\nHALT", 
                {0: 60000}
            ),
            AssemblyTestCase(
                "add_16bit_overflow",
                "ADD i:65535, i:1\nHALT",  # Should wrap to 0
                {0: 0}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_sub_instruction(self):
        """Test SUB instruction.""" 
        test_cases = [
            AssemblyTestCase(
                "sub_immediate_values",
                "SUB i:30, i:10\nHALT",
                {0: 20}
            ),
            AssemblyTestCase(
                "sub_register_values",
                "MVR i:100, 1\nMVR i:25, 2\nSUB 1, 2\nHALT",
                {0: 75, 1: 100, 2: 25}
            ),
            AssemblyTestCase(
                "sub_equal_values",
                "SUB i:42, i:42\nHALT",
                {0: 0}
            ),
            AssemblyTestCase(
                "sub_larger_from_smaller",
                "SUB i:10, i:20\nHALT",  # Should wrap around in 16-bit
                {0: 65526}  # -10 as 16-bit unsigned
            ),
            AssemblyTestCase(
                "sub_from_zero",
                "SUB i:0, i:5\nHALT", 
                {0: 65531}  # -5 as 16-bit unsigned
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_mult_instruction(self):
        """Test MULT instruction."""
        test_cases = [
            AssemblyTestCase(
                "mult_simple_values",
                "MULT i:6, i:7\nHALT",
                {0: 42, 1: 0}  # Result in R0, overflow in R1
            ),
            AssemblyTestCase(
                "mult_register_values",
                "MVR i:12, 2\nMVR i:5, 3\nMULT 2, 3\nHALT",
                {0: 60, 1: 0, 2: 12, 3: 5}
            ),
            AssemblyTestCase(
                "mult_by_zero",
                "MULT i:1000, i:0\nHALT",
                {0: 0, 1: 0}
            ),
            AssemblyTestCase(
                "mult_by_one",
                "MULT i:12345, i:1\nHALT", 
                {0: 12345, 1: 0}
            ),
            AssemblyTestCase(
                "mult_overflow_to_secondary",
                "MULT i:256, i:256\nHALT",  # 65536 = 0x10000
                {0: 0, 1: 1}  # Low 16-bits = 0, High 16-bits = 1
            ),
            AssemblyTestCase(
                "mult_large_overflow",
                "MULT i:65535, i:65535\nHALT",  # Max * Max
                {0: 1, 1: 65534}  # (2^16-1)^2 = 2^32 - 2^17 + 1
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_div_instruction(self):
        """Test DIV instruction."""
        test_cases = [
            AssemblyTestCase(
                "div_simple_values",
                "DIV i:42, i:6\nHALT",
                {0: 7, 1: 0}  # Quotient in R0, remainder in R1
            ),
            AssemblyTestCase(
                "div_with_remainder",
                "DIV i:17, i:5\nHALT",
                {0: 3, 1: 2}  # 17/5 = 3 remainder 2
            ),
            AssemblyTestCase(
                "div_register_values",
                "MVR i:100, 4\nMVR i:7, 5\nDIV 4, 5\nHALT",
                {0: 14, 1: 2, 4: 100, 5: 7}  # 100/7 = 14 remainder 2
            ),
            AssemblyTestCase(
                "div_exact_division",
                "DIV i:64, i:8\nHALT",
                {0: 8, 1: 0}
            ),
            AssemblyTestCase(
                "div_by_one",
                "DIV i:12345, i:1\nHALT",
                {0: 12345, 1: 0}
            ),
            AssemblyTestCase(
                "div_smaller_by_larger",
                "DIV i:3, i:10\nHALT",
                {0: 0, 1: 3}  # 3/10 = 0 remainder 3
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_arithmetic_chaining(self):
        """Test chaining multiple arithmetic operations."""
        test_cases = [
            AssemblyTestCase(
                "add_then_sub",
                "ADD i:10, i:5\nMVR 0, 10\nSUB 10, i:3\nHALT",
                {0: 12, 10: 15}  # (10+5) - 3 = 12
            ),
            AssemblyTestCase(
                "mult_then_div",
                "MULT i:6, i:7\nMVR 0, 10\nDIV 10, i:2\nHALT", 
                {0: 21, 1: 0, 10: 42}  # (6*7) / 2 = 21
            ),
            AssemblyTestCase(
                "complex_calculation",
                # Calculate (5 + 3) * 4 - 2 = 30
                "ADD i:5, i:3\nMVR 0, 10\nMULT 10, i:4\nMVR 0, 11\nSUB 11, i:2\nHALT",
                {0: 30, 10: 8, 11: 32}
            )
        ]
        
        self.run_test_cases(test_cases)


if __name__ == '__main__':
    unittest.main()