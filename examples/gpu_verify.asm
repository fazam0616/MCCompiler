// Simple GPU Register Verification
// Test if GPU register can be read and written

// Test 1: Write to GPU register and read it back
LOAD GPU, i:42                  // Set GPU register to 42
LOAD 5, GPU                     // Read GPU register into reg 5
// If working correctly, reg 5 should now contain 42

// Test 2: Use GPU register for buffer control
LOAD GPU, i:0                   // Both buffers = 0
CLRGRID i:0, i:0, i:32, i:32    // Clear screen

// Fill entire screen with white
DRGRD i:0, i:0, i:32, i:32      

// Wait to see white screen
LOAD 1, i:200000
wait1:
    SUB 1, i:1
    LOAD 1, 0
    JNZ 1, wait1

// Switch to buffer 1 for display (should show black screen)
LOAD GPU, i:1                   // Display=1, Edit=0

// Wait to see black screen  
LOAD 1, i:400000
wait2:
    SUB 1, i:1
    LOAD 1, 0
    JNZ 1, wait2

// Switch back to buffer 0 (should show white screen again)
LOAD GPU, i:0                   // Display=0, Edit=0

// Wait to see white screen again
LOAD 1, i:400000
wait3:
    SUB 1, i:1
    LOAD 1, 0
    JNZ 1, wait3

HALT