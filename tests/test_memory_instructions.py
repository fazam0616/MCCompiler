"""
Tests for memory instructions: LOAD, READ, MVM.

These instructions handle reading from and writing to memory.
- LOAD: Store register value to memory address
- READ: Load memory value to register  
- MVM: Copy memory address to memory address
"""

import unittest
from test_assembly_framework import BaseAssemblyTestCase, AssemblyTestCase


class TestMemoryInstructions(BaseAssemblyTestCase):
    """Test memory access instructions."""
    
    def test_load_instruction(self):
        """Test LOAD instruction (value to memory)."""
        test_cases = [
            AssemblyTestCase(
                "load_register_value",
                "MVR i:42, 1\nLOAD 1, i:1000\nHALT",
                {1: 42},
                expected_memory={1000: 42}
            ),
            AssemblyTestCase(
                "load_immediate_value",
                "LOAD i:123, i:1001\nHALT",
                {},
                expected_memory={1001: 123}
            ),
            AssemblyTestCase(
                "load_multiple_values",
                "MVR i:100, 0\nMVR i:200, 1\nMVR i:300, 2\nLOAD 0, i:500\nLOAD 1, i:501\nLOAD 2, i:502\nHALT",
                {0: 100, 1: 200, 2: 300},
                expected_memory={500: 100, 501: 200, 502: 300}
            ),
            AssemblyTestCase(
                "load_register_address",
                "MVR i:123, 5\nMVR i:2000, 6\nLOAD 5, 6\nHALT",  # Use register for address
                {5: 123, 6: 2000},
                expected_memory={2000: 123}
            ),
            AssemblyTestCase(
                "load_immediate_to_register_address",
                "MVR i:1500, 7\nLOAD i:999, 7\nHALT",  # Immediate value to register address
                {7: 1500},
                expected_memory={1500: 999}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_read_instruction(self):
        """Test READ instruction (memory to register)."""
        test_cases = [
            AssemblyTestCase(
                "read_after_load",
                "MVR i:55, 1\nLOAD 1, i:800\nREAD i:800, 2\nHALT",
                {1: 55, 2: 55},
                expected_memory={800: 55}
            ),
            AssemblyTestCase(
                "read_multiple_locations",
                "MVR i:10, 0\nMVR i:20, 1\nMVR i:30, 2\nLOAD 0, i:100\nLOAD 1, i:101\nLOAD 2, i:102\nREAD i:100, 10\nREAD i:101, 11\nREAD i:102, 12\nHALT",
                {0: 10, 1: 20, 2: 30, 10: 10, 11: 20, 12: 30},
                expected_memory={100: 10, 101: 20, 102: 30}
            ),
            AssemblyTestCase(
                "read_register_address",
                "MVR i:99, 3\nMVR i:1500, 4\nLOAD 3, 4\nREAD 4, 5\nHALT",  # Use register for read address
                {3: 99, 4: 1500, 5: 99}
            ),
            AssemblyTestCase(
                "read_uninitialized_memory",
                "READ i:9999, 7\nHALT",  # Should read 0 from uninitialized memory
                {7: 0}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_mvm_instruction(self):
        """Test MVM instruction (memory to memory copy)."""
        test_cases = [
            AssemblyTestCase(
                "mvm_basic_copy",
                "MVR i:77, 1\nLOAD 1, i:400\nMVM i:400, i:500\nREAD i:500, 2\nHALT",
                {1: 77, 2: 77},
                expected_memory={400: 77, 500: 77}
            ),
            AssemblyTestCase(
                "mvm_register_addresses", 
                "MVR i:88, 0\nMVR i:600, 1\nMVR i:700, 2\nLOAD 0, 1\nMVM 1, 2\nREAD 2, 3\nHALT",
                {0: 88, 1: 600, 2: 700, 3: 88}
            ),
            AssemblyTestCase(
                "mvm_chain_copies",
                "MVR i:333, 0\nLOAD 0, i:100\nMVM i:100, i:200\nMVM i:200, i:300\nREAD i:300, 1\nHALT",
                {0: 333, 1: 333},
                expected_memory={100: 333, 200: 333, 300: 333}
            ),
            AssemblyTestCase(
                "mvm_overwrite_memory",
                "MVR i:111, 0\nMVR i:222, 1\nLOAD 0, i:150\nLOAD 1, i:151\nMVM i:151, i:150\nREAD i:150, 2\nHALT",
                {0: 111, 1: 222, 2: 222},  # 222 overwrites 111
                expected_memory={150: 222, 151: 222}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_memory_address_ranges(self):
        """Test memory operations at various address ranges."""
        test_cases = [
            AssemblyTestCase(
                "memory_low_addresses",
                "MVR i:11, 0\nMVR i:22, 1\nLOAD 0, i:0\nLOAD 1, i:1\nREAD i:0, 2\nREAD i:1, 3\nHALT",
                {0: 11, 1: 22, 2: 11, 3: 22},
                expected_memory={0: 11, 1: 22}
            ),
            AssemblyTestCase(
                "memory_high_ram_addresses",
                "MVR i:99, 4\nLOAD 4, i:32767\nREAD i:32767, 5\nHALT",  # Max RAM address (0x7FFF)
                {4: 99, 5: 99},
                expected_memory={32767: 99}
            ),
            AssemblyTestCase(
                "memory_mid_range",
                "MVR i:456, 6\nLOAD 6, i:16384\nREAD i:16384, 7\nHALT",  # Middle of RAM space
                {6: 456, 7: 456},
                expected_memory={16384: 456}
            )
        ]
        
        self.run_test_cases(test_cases)
    
    def test_memory_patterns(self):
        """Test various memory access patterns."""
        test_cases = [
            AssemblyTestCase(
                "memory_array_simulation",
                # Simulate array: arr[0]=10, arr[1]=20, arr[2]=30
                "MVR i:10, 0\nMVR i:20, 1\nMVR i:30, 2\nLOAD 0, i:1000\nLOAD 1, i:1001\nLOAD 2, i:1002\nREAD i:1001, 10\nHALT",  # Read middle element
                {0: 10, 1: 20, 2: 30, 10: 20}
            ),
            AssemblyTestCase(
                "memory_swap_simulation", 
                # Swap memory locations 500 and 600
                "MVR i:111, 0\nMVR i:222, 1\nLOAD 0, i:500\nLOAD 1, i:600\nMVM i:500, i:999\nMVM i:600, i:500\nMVM i:999, i:600\nREAD i:500, 2\nREAD i:600, 3\nHALT",
                {0: 111, 1: 222, 2: 222, 3: 111},  # Values swapped
                expected_memory={500: 222, 600: 111}
            ),
            AssemblyTestCase(
                "memory_register_indirect",
                # Use register value as address for another register
                "MVR i:44, 0\nMVR i:1234, 1\nMVR i:5678, 2\nLOAD 0, 1\nREAD 1, 2\nHALT",  # Store R0 at address in R1, then read back to R2
                {0: 44, 1: 1234, 2: 44}
            )
        ]
        
        self.run_test_cases(test_cases)


if __name__ == '__main__':
    unittest.main()