func_main:
MVR 0, 0  // Function: main
MVR i:4096, 29  // malloc(4) -> 4096
MVR 29, 30  // Initialize small_buffer (R30)
MVR i:4100, 27  // malloc(16) -> 4100
MVR 27, 28  // Initialize medium_buffer (R28)
MVR i:4116, 25  // malloc(100) -> 4116
MVR 25, 26  // Initialize large_buffer (R26)
MVR i:42, 24  // Load literal 42
LOAD 24, 30  // Pointer dereference assignment
READ 30, 22  // Dereference
MVR 22, 23  // Initialize value (R23)
MVR i:4216, 21  // malloc(8) -> 4216
MVR 21, 22  // Initialize ptr (R22)
MVR i:10, 20  // Load literal 10
LOAD 20, 22  // Pointer dereference assignment
MVR i:1, 19  // Load literal 1
ADD 22, 19  // + operation
MVR 0, 22  // Assign to ptr (R22)
MVR i:20, 19  // Load literal 20
LOAD 19, 22  // Pointer dereference assignment
MVR 0, 0  // free(R30) - memory deallocated at compile time
MVR 0, 0  // free(R28) - memory deallocated at compile time
MVR 0, 0  // free(R26) - memory deallocated at compile time
MVR i:1, 18  // Load literal 1
SUB 22, 18  // - operation
MVR 0, 0  // free(R0) - memory deallocated at compile time
MVR i:10, 16  // Load literal 10
MVR 16, 17  // Initialize size (R17)
MVR i:5, 15  // Load literal 5
SUB 17, 15  // Comparison
MVR i:32768, 13  // Load sign bit mask
AND 0, 13  // Check sign bit
JNZ true4, 0  // Jump if negative (less than)
MVR i:0, 14
JMP comp_end5
true4:
MVR 0, 0  // Label: true4
MVR i:1, 14  // True case
comp_end5:
MVR 0, 0
JZ else6, 14  // If condition
MVR i:4224, 15  // malloc(4) -> 4224
MVR 15, 18  // Assign to conditional_ptr (R18)
JMP endif7  // Skip else
else6:
MVR 0, 0
MVR i:20, 14  // Load literal 20
SUB 17, 14  // Comparison
MVR i:32768, 12  // Load sign bit mask
AND 0, 12  // Check sign bit
JNZ true9, 0  // Jump if negative (less than)
MVR i:0, 13
JMP comp_end10
true9:
MVR 0, 0  // Label: true9
MVR i:1, 13  // True case
comp_end10:
MVR 0, 0
JZ else11, 13  // If condition
MVR i:4228, 14  // malloc(16) -> 4228
MVR 14, 18  // Assign to conditional_ptr (R18)
JMP endif12  // Skip else
else11:
MVR 0, 0
MVR i:4244, 13  // malloc(64) -> 4244
MVR 13, 18  // Assign to conditional_ptr (R18)
endif12:
MVR 0, 0
endif7:
MVR 0, 0
MVR i:2, 12  // Load literal 2
MULT 17, 12  // * operation
LOAD 0, 18  // Pointer dereference assignment
MVR 0, 0  // free(R18) - memory deallocated at compile time
MVR i:0, 0  // Default return 0
HALT  // Halt execution