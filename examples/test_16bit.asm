func_main:
MVR 0, 0  // Function: main
MVR 5, i:4096  // Load literal 4096
MVR 5, 4  // Initialize buffer_addr
MVR 9, i:65  // Load literal 65
MVR 9, 6  // Assign to char1
MVR 10, i:66  // Load literal 66
MVR 10, 7  // Assign to char2
ADD 6, 7  // + operation
MVR 0, 8  // Assign to result
MVR 8, 0  // Set return value
JMP caller_return  // Return to caller
func_test_16bit_limits:
MVR 0, 0  // Function: test_16bit_limits
MVR 12, i:65535  // Load literal 65535
MVR 12, 11  // Initialize max_val
MVR 14, i:1  // Load literal 1
ADD 11, 14  // + operation
MVR 0, 13  // Assign to overflow
MVR 13, 0  // Set return value
JMP caller_return  // Return to caller
func_test_array_ops:
MVR 0, 0  // Function: test_array_ops
MVR 16, i:8192  // Load literal 8192
MVR 16, 15  // Initialize base_addr
MVR 18, i:5  // Load literal 5
MVR 18, 17  // Initialize index
ADD 15, 17  // + operation
MVR 0, 19  // Assign to element_addr
MVR 19, 0  // Set return value
JMP caller_return  // Return to caller