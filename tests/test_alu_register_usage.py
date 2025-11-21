"""Test ALU register usage and edge cases.

Tests scenarios where ALU result register (R0) is used as source
in subsequent operations, which is common in complex expressions.
"""

import unittest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from vm.virtual_machine import VirtualMachine, create_vm
from vm.cpu import CPUState


class TestALURegisterUsage(unittest.TestCase):
    """Test ALU register usage patterns and edge cases."""
    
    def setUp(self):
        """Set up VM for each test."""
        self.vm = create_vm({'enable_gpu': False})
    
    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self.vm, 'shutdown'):
            self.vm.shutdown()
    
    def run_assembly(self, assembly):
        """Helper method to load and run assembly code until halt."""
        self.vm.load_program_string(assembly)
        # Step through execution until halt
        while self.vm.cpu.state.name != 'HALTED' and self.vm.step():
            pass
    
    def to_unsigned_16(self, signed_value):
        """Convert signed integer to 16-bit unsigned representation."""
        if signed_value < 0:
            return 65536 + signed_value
        return signed_value
    
    def test_alu_result_as_source(self):
        """Test using ALU result (R0) as source in next operation."""
        assembly = """
        MVR i:5, 1     // Load 5 into R1
        MVR i:3, 2     // Load 3 into R2
        ADD 1, 2       // 5 + 3 = 8 (result in R0)
        MVR i:2, 3     // Load 2 into R3
        MULT 0, 3      // 8 * 2 = 16 (using R0 as source)
        HALT
        """
        self.run_assembly(assembly)
        
        # Result should be 16 in R0
        self.assertEqual(self.vm.cpu.registers[0], 16)
    
    def test_chained_alu_operations(self):
        """Test multiple chained ALU operations."""
        assembly = """
        MVR i:10, 1    // Load 10 into R1
        MVR i:5, 2     // Load 5 into R2
        SUB 1, 2       // 10 - 5 = 5 (result in R0)
        MVR i:3, 3     // Load 3 into R3
        MULT 0, 3      // 5 * 3 = 15 (using R0)
        MVR i:2, 4     // Load 2 into R4
        DIV 0, 4       // 15 / 2 = 7 (integer division, using R0)
        HALT
        """
        self.run_assembly(assembly)
        
        # Result should be 7 in R0
        self.assertEqual(self.vm.cpu.registers[0], 7)
    
    def test_negation_multiplication_pattern(self):
        """Test the specific pattern from bouncing square: x * -1."""
        assembly = """
        MVR i:5, 5     // Load value 5 into R5 (simulating dx)
        MVR i:1, 6     // Load 1 into R6
        MVR i:0, 7     // Load 0 into R7
        SUB 7, 6       // 0 - 1 = -1 (result in R0)
        MULT 5, 0      // 5 * -1 = -5 (using R0 as source)
        HALT
        """
        self.run_assembly(assembly)
        
        # Result should be -5 in R0 (represented as 65531 in 16-bit unsigned)
        self.assertEqual(self.vm.cpu.registers[0], self.to_unsigned_16(-5))
    
    def test_alu_result_copied_then_reused(self):
        """Test copying ALU result to register, then using both."""
        assembly = """
        MVR i:8, 1     // Load 8 into R1
        MVR i:3, 2     // Load 3 into R2
        SUB 1, 2       // 8 - 3 = 5 (result in R0)
        MVR 0, 10      // Copy result to R10
        MVR i:2, 3     // Load 2 into R3
        MULT 10, 3     // 5 * 2 = 10 (using copied value)
        ADD 0, 10      // 10 + 5 = 15 (using both ALU result and copied value)
        HALT
        """
        self.run_assembly(assembly)
        
        
        # Final result should be 15 in R0, and R10 should still have 5
        self.assertEqual(self.vm.cpu.registers[0], 15)
        self.assertEqual(self.vm.cpu.registers[10], 5)
    
    def test_comparison_then_multiply(self):
        """Test comparison result used in multiplication (boolean arithmetic)."""
        assembly = """
        MVR i:10, 1    // Load 10 into R1
        MVR i:5, 2     // Load 5 into R2
        SUB 1, 2       // 10 - 5 = 5 (result in R0, non-zero = true)
        MVR i:7, 3     // Load 7 into R3
        MULT 0, 3      // 5 * 7 = 35 (using comparison result)
        HALT
        """
        self.run_assembly(assembly)
        
        
        # Result should be 35 in R0
        self.assertEqual(self.vm.cpu.registers[0], 35)
    
    def test_zero_multiplication_bug_scenario(self):
        """Test the specific bug scenario where temp registers were reused."""
        assembly = """
        MVR i:3, 21    // Load 3 into R21 (simulating dx)
        MVR i:1, 29    // Load 1 into R29 
        MVR i:0, 29    // Load 0 into R29 (THIS WAS THE BUG - overwrites 1!)
        SUB 29, 29     // 0 - 0 = 0 (should be 0 - 1 = -1)
        MULT 21, 0     // 3 * 0 = 0 (should be 3 * -1 = -3)
        HALT
        """
        self.run_assembly(assembly)
        
        
        # This demonstrates the bug - result is 0 instead of -3
        self.assertEqual(self.vm.cpu.registers[0], 0)  # The bug behavior
        self.assertEqual(self.vm.cpu.registers[21], 3)  # dx unchanged
        
    def test_correct_negation_different_registers(self):
        """Test correct negation using different registers."""
        assembly = """
        MVR i:3, 21    // Load 3 into R21 (simulating dx)
        MVR i:1, 29    // Load 1 into R29 
        MVR i:0, 28    // Load 0 into R28 (FIXED - different register!)
        SUB 28, 29     // 0 - 1 = -1
        MULT 21, 0     // 3 * -1 = -3
        HALT
        """
        self.run_assembly(assembly)
        
        
        # This shows the correct behavior
        self.assertEqual(self.vm.cpu.registers[0], self.to_unsigned_16(-3))  # Correct result
        self.assertEqual(self.vm.cpu.registers[21], 3)   # dx unchanged
    
    def test_bitwise_then_arithmetic(self):
        """Test bitwise operation result used in arithmetic."""
        assembly = """
        MVR i:12, 1    // Load 12 (1100 binary) into R1
        MVR i:5, 2     // Load 5 (0101 binary) into R2  
        AND 1, 2       // 1100 & 0101 = 0100 = 4 (result in R0)
        MVR i:3, 3     // Load 3 into R3
        MULT 0, 3      // 4 * 3 = 12 (using bitwise result)
        HALT
        """
        self.run_assembly(assembly)
        
        
        # Result should be 12 in R0
        self.assertEqual(self.vm.cpu.registers[0], 12)
    
    def test_division_remainder_handling(self):
        """Test division with remainder and subsequent operations."""
        assembly = """
        MVR i:17, 1    // Load 17 into R1
        MVR i:5, 2     // Load 5 into R2
        DIV 1, 2       // 17 / 5 = 3 (integer division, result in R0)
        MVR i:2, 3     // Load 2 into R3
        ADD 0, 3       // 3 + 2 = 5 (using division result)
        HALT
        """
        self.run_assembly(assembly)
        
        
        # Result should be 5 in R0
        self.assertEqual(self.vm.cpu.registers[0], 5)
    
    def test_shift_then_multiply(self):
        """Test shift operation result used in multiplication."""
        assembly = """
        MVR i:5, 1     // Load 5 into R1
        MVR i:2, 2     // Load 2 into R2
        SHL 1, 2       // 5 << 2 = 20 (result in R0)
        MVR i:3, 3     // Load 3 into R3
        MULT 0, 3      // 20 * 3 = 60 (using shift result)
        HALT
        """
        self.run_assembly(assembly)
        
        
        # Result should be 60 in R0
        self.assertEqual(self.vm.cpu.registers[0], 60)
    
    def test_nested_expression_simulation(self):
        """Test complex nested expression: (a + b) * (c - d)."""
        assembly = """
        MVR i:7, 1     // Load a=7 into R1
        MVR i:3, 2     // Load b=3 into R2
        ADD 1, 2       // a + b = 10 (result in R0)
        MVR 0, 10      // Store first result in R10
        
        MVR i:15, 3    // Load c=15 into R3
        MVR i:5, 4     // Load d=5 into R4
        SUB 3, 4       // c - d = 10 (result in R0)
        
        MULT 10, 0     // (a+b) * (c-d) = 10 * 10 = 100
        HALT
        """
        self.run_assembly(assembly)
        
        
        # Result should be 100 in R0
        self.assertEqual(self.vm.cpu.registers[0], 100)
    
    def test_alu_register_overwrite_protection(self):
        """Test that ALU register isn't accidentally overwritten."""
        assembly = """
        MVR i:6, 1     // Load 6 into R1
        MVR i:2, 2     // Load 2 into R2
        MULT 1, 2      // 6 * 2 = 12 (result in R0)
        
        // These operations shouldn't affect R0 until we explicitly use it
        MVR i:100, 3   // Load 100 into R3
        MVR i:200, 4   // Load 200 into R4
        
        // Now use the ALU result
        MVR i:5, 5     // Load 5 into R5
        ADD 0, 5       // 12 + 5 = 17 (using preserved ALU result)
        HALT
        """
        self.run_assembly(assembly)
        
        
        # Result should be 17, proving R0 was preserved
        self.assertEqual(self.vm.cpu.registers[0], 17)
    
    def test_bouncing_square_velocity_reversal(self):
        """Test the exact velocity reversal pattern from bouncing square."""
        assembly = """
        // Simulate dx = -1, reverse to dx = 1
        MVR i:1, 21    // dx = -1 (using 1 for simplicity, will negate)
        MVR i:0, 20    // Load 0
        SUB 20, 21     // 0 - 1 = -1 (now dx is -1 in R0)
        MVR 0, 21      // Store -1 back to dx (R21)
        
        // Now reverse: dx = dx * -1
        MVR i:1, 6     // Load 1 into R6
        MVR i:0, 5     // Load 0 into R5 (different register!)
        SUB 5, 6       // 0 - 1 = -1 (create multiplier)
        MULT 21, 0     // dx * -1 = (-1) * (-1) = 1
        MVR 0, 21      // Store result back to dx
        HALT
        """
        self.run_assembly(assembly)
        
        
        # dx should now be 1 (reversed from -1)
        self.assertEqual(self.vm.cpu.registers[21], 1)
        self.assertEqual(self.vm.cpu.registers[0], 1)


class TestALUEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions for ALU operations."""
    
    def setUp(self):
        """Set up VM for each test."""
        self.vm = create_vm({'enable_gpu': False})
    
    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self.vm, 'shutdown'):
            self.vm.shutdown()
    
    def run_assembly(self, assembly):
        """Helper method to load and run assembly code until halt."""
        self.vm.load_program_string(assembly)
        # Step through execution until halt
        while self.vm.cpu.state.name != 'HALTED' and self.vm.step():
            pass
    
    
    
    def test_zero_operations(self):
        """Test operations with zero values."""
        assembly = """
        MVR i:0, 1     // Load 0 into R1
        MVR i:5, 2     // Load 5 into R2
        ADD 1, 2       // 0 + 5 = 5
        MULT 0, 1      // 5 * 0 = 0 (using zero as source)
        HALT
        """
        self.run_assembly(assembly)
        
        
        self.assertEqual(self.vm.cpu.registers[0], 0)
    
    def to_unsigned_16(self, signed_value):
        """Convert signed integer to 16-bit unsigned representation."""
        if signed_value < 0:
            return 65536 + signed_value
        return signed_value

    def test_negative_number_operations(self):
        """Test operations with negative numbers."""
        assembly = """
        MVR i:0, 1     // Load 0 into R1  
        MVR i:3, 2     // Load 3 into R2
        SUB 1, 2       // 0 - 3 = -3
        MVR i:2, 3     // Load 2 into R3
        MULT 0, 3      // -3 * 2 = -6
        HALT
        """
        self.run_assembly(assembly)
        
        
        self.assertEqual(self.vm.cpu.registers[0], self.to_unsigned_16(-6))
    
    def test_large_number_operations(self):
        """Test operations with large numbers (within 16-bit range)."""
        assembly = """
        MVR i:30000, 1    // Load large number
        MVR i:2, 2        // Load 2
        DIV 1, 2          // 30000 / 2 = 15000
        MVR i:2, 3        // Load 2 again
        MULT 0, 3         // 15000 * 2 = 30000
        HALT
        """
        self.run_assembly(assembly)
        
        
        self.assertEqual(self.vm.cpu.registers[0], 30000)
    
    def test_division_by_one(self):
        """Test division by one (should preserve value)."""
        assembly = """
        MVR i:42, 1    // Load 42
        MVR i:1, 2     // Load 1
        DIV 1, 2       // 42 / 1 = 42
        MVR i:3, 3     // Load 3
        ADD 0, 3       // 42 + 3 = 45
        HALT
        """
        self.run_assembly(assembly)
        
        
        self.assertEqual(self.vm.cpu.registers[0], 45)
    
    def test_self_referential_operations(self):
        """Test operations where source and destination overlap via ALU."""
        assembly = """
        MVR i:10, 1    // Load 10 into R1
        ADD 1, 1       // 10 + 10 = 20 (result in R0)
        ADD 0, 0       // 20 + 20 = 40 (using R0 as both operands)
        HALT
        """
        self.run_assembly(assembly)
        
        
        self.assertEqual(self.vm.cpu.registers[0], 40)


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)
