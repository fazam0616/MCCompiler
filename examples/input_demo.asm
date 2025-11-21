func_main:
MVR 0, 0  // Function: main
MVR 5, i:4096  // Load literal 4096
MVR 5, 4  // Initialize input_address
MVR 7, i:0  // Load literal 0
MVR 7, 6  // Initialize result
MVR 8, i:42  // Load literal 42
MVR 8, 6  // Assign to result
MVR 6, 0  // Set return value
JMP caller_return  // Return to caller
func_read_multiple_chars:
MVR 0, 0  // Function: read_multiple_chars
MVR 13, i:0  // Load literal 0
MVR 13, 12  // Initialize total
MVR 14, i:0  // Load literal 0
MVR 14, 11  // Assign to i
for_loop0:
MVR 0, 0
SUB 11, 5  // Comparison
MVR 15, i:0
JMP comp_end4
true3:
MVR 0, 0  // Label: true3
MVR 15, i:1  // True case
comp_end4:
MVR 0, 0
JZ for_end2, 15  // For condition
MVR 16, i:1  // Load literal 1
ADD 12, 16  // + operation
MVR 0, 12  // Assign to total
for_continue1:
MVR 0, 0
MVR 17, i:1  // Load literal 1
ADD 11, 17  // + operation
MVR 0, 11  // Assign to i
JMP for_loop0  // For loop back
for_end2:
MVR 0, 0
MVR 12, 0  // Set return value
JMP caller_return  // Return to caller