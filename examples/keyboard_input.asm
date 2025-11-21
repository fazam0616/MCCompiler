func_main:
MVR 0, 0  // Function: main
MVR 5, i:4096  // Load literal 4096
MVR 5, 4  // Initialize input_buffer
MVR 7, i:0  // Load literal 0
MVR 7, 6  // Initialize char_count
MVR 10, i:0  // Load literal 0
MVR 10, 9  // Assign to i
for_loop0:
MVR 0, 0
MVR 11, i:10  // Load literal 10
SUB 9, 11  // Comparison
MVR 12, i:0
JMP comp_end4
true3:
MVR 0, 0  // Label: true3
MVR 12, i:1  // True case
comp_end4:
MVR 0, 0
JZ for_end2, 12  // For condition
MVR 13, i:1  // Load literal 1
ADD 6, 13  // + operation
MVR 0, 6  // Assign to char_count
for_continue1:
MVR 0, 0
MVR 14, i:1  // Load literal 1
ADD 9, 14  // + operation
MVR 0, 9  // Assign to i
JMP for_loop0  // For loop back
for_end2:
MVR 0, 0
MVR 6, 0  // Set return value
JMP caller_return  // Return to caller
func_read_char:
MVR 0, 0  // Function: read_char
MVR 16, i:0  // Load literal 0
MVR 16, 0  // Set return value
JMP caller_return  // Return to caller
func_process_input:
MVR 0, 0  // Function: process_input
MVR 21, i:0  // Load literal 0
MVR 21, 20  // Initialize sum
MVR 23, i:0  // Load literal 0
MVR 23, 19  // Assign to i
for_loop5:
MVR 0, 0
SUB 19, 5  // Comparison
MVR 24, i:0
JMP comp_end9
true8:
MVR 0, 0  // Label: true8
MVR 24, i:1  // True case
comp_end9:
MVR 0, 0
JZ for_end7, 24  // For condition
ADD 4, 19  // + operation
MVR 0, 22  // Assign to current_addr
for_continue6:
MVR 0, 0
MVR 25, i:1  // Load literal 1
ADD 19, 25  // + operation
MVR 0, 19  // Assign to i
JMP for_loop5  // For loop back
for_end7:
MVR 0, 0
MVR 20, 0  // Set return value
JMP caller_return  // Return to caller