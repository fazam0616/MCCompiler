func_main:
MVR 0, 0  // Function: main
MVR i:4096, 29  // malloc(4) -> 4096
MVR 29, 30  // Initialize ptr (R30)
MVR i:42, 28  // Load literal 42
LOAD 28, 30  // Pointer dereference assignment
MVR 0, 0  // free(R30) - memory deallocated at compile time
MVR i:0, 0  // Default return 0
HALT  // Halt execution