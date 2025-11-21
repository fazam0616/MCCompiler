// GPU Buffer Control Test
// Demonstrates dual-buffer functionality using bitwise operations on GPU register

// Initialize GPU register - both display and edit use buffer 0
MVR i:0, GPU                    // GPU register: bit1=0 (edit buf 0), bit0=0 (disp buf 0)

// Clear both buffers
CLRGRID i:0, i:0, i:32, i:32    // Clear buffer 0 (current edit buffer)
OR GPU, i:2                     // Set bit 1: edit buffer = 1 (result in R0)
MVR 0, GPU                      // Move result from R0 to GPU register
CLRGRID i:0, i:0, i:32, i:32    // Clear buffer 1
AND GPU, i:0xFFFFFFFD           // Clear bit 1: edit buffer = 0 (result in R0)  
MVR 0, GPU                      // Move result from R0 to GPU register

// Draw 'A' on buffer 0 (edit buffer)
MVR i:65, 0                     // Load 'A' character code into reg 0
LDTXT 0, 0                      // Load character into text buffer
DRTXT 0, i:2, i:2               // Draw 'A' at position (2,2)

// Switch to edit buffer 1 while keeping display on buffer 0
OR GPU, i:2                     // Set bit 1: edit buffer = 1 (result in R0)
MVR 0, GPU                      // Move result from R0 to GPU register

// Draw 'B' on buffer 1 (now the edit buffer)
MVR i:66, 0                     // Load 'B' character code into reg 0
LDTXT 1, 0                      // Load character into text buffer  
DRTXT 1, i:10, i:10             // Draw 'B' at position (10,10)

// Wait loop before switching display
MVR i:500000, 1                 // Counter for delay
loop1:
    SUB 1, i:1                  // Subtract 1 from reg1 (result in R0)
    MVR 0, 1                    // Move result from R0 back to reg1
    JNZ 1, loop1                // Continue if not zero

// Switch display to buffer 1 (now shows 'B')
OR GPU, i:1                     // Set bit 0: display buffer = 1 (result in R0)
MVR 0, GPU                      // Move result from R0 to GPU register

// Wait again  
MVR i:500000, 1                 // Counter for delay
loop2:
    SUB 1, i:1                  // Subtract 1 from reg1 (result in R0)
    MVR 0, 1                    // Move result from R0 back to reg1
    JNZ 1, loop2                // Continue if not zero

// Manually swap buffers: flip both buffer bits
XOR GPU, i:3                    // XOR with 0b11 to flip both bits (result in R0)
MVR 0, GPU                      // Write back - now display=0 (shows 'A'), edit=0

// Wait to see the manual swap
MVR i:500000, 1                 // Counter for delay  
loop3:
    SUB 1, i:1                  // Subtract 1 from reg1 (result in R0)
    MVR 0, 1                    // Move result from R0 back to reg1
    JNZ 1, loop3                // Continue if not zero

HALT                            // End program