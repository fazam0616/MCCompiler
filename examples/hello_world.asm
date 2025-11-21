func_main:
MVR 0, 0  // Function: main
MVR 5, i:72  // Load literal 72
MVR 5, 4  // Initialize message
MVR 8, i:0  // Load literal 0
MVR 8, 6  // Assign to i
for_loop0:
MVR 0, 0
MVR 9, i:5  // Load literal 5
SUB 6, 9  // Comparison
MVR 10, i:0
JMP comp_end4
true3:
MVR 0, 0  // Label: true3
MVR 10, i:1  // True case
comp_end4:
MVR 0, 0
JZ for_end2, 10  // For condition
ADD 4, 6  // + operation
MVR 0, 4  // Assign to message
for_continue1:
MVR 0, 0
MVR 11, i:1  // Load literal 1
ADD 6, 11  // + operation
MVR 0, 6  // Assign to i
JMP for_loop0  // For loop back
for_end2:
MVR 0, 0
MVR 4, 0  // Set return value
JMP caller_return  // Return to caller
func_add_numbers:
MVR 0, 0  // Function: add_numbers
ADD 4, 5  // + operation
MVR 0, 0  // Set return value
JMP caller_return  // Return to caller
func_fibonacci:
MVR 0, 0  // Function: fibonacci
MVR 15, i:1  // Load literal 1
SUB 4, 15  // Comparison
MVR 16, i:0
JMP comp_end6
true5:
MVR 0, 0  // Label: true5
MVR 16, i:1  // True case
comp_end6:
MVR 0, 0
JZ else7, 16  // If condition
MVR 4, 0  // Set return value
JMP caller_return  // Return to caller
JMP endif8  // Skip else
else7:
MVR 0, 0
endif8:
MVR 0, 0
MVR 17, i:1  // Load literal 1
SUB 4, 17  // - operation
MVR 0, 4  // Pass argument 0
JAL func_fibonacci  // Call fibonacci
MVR 18, i:2  // Load literal 2
SUB 4, 18  // - operation
MVR 0, 4  // Pass argument 0
JAL func_fibonacci  // Call fibonacci
ADD 0, 0  // + operation
MVR 0, 0  // Set return value
JMP caller_return  // Return to caller