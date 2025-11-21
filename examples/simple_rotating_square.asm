// Simplified 3D Rotating Cube Demo
// Tests basic cube rendering with rotation

// Initialize GPU register for dual buffering
MVR i:0, GPU

// Initialize counter to 0 in memory
MVR i:0, 0
LOAD 0, i:100

// Clear both buffers initially
CLRGRID i:0, i:0, i:32, i:32
OR GPU, i:2      // Switch to buffer 1 for edit
MVR 0, GPU
CLRGRID i:0, i:0, i:32, i:32
AND GPU, i:0xFFFFFFFD  // Switch back to buffer 0 for edit
MVR 0, GPU

main_loop:
    // Clear the current edit buffer
    CLRGRID i:0, i:0, i:32, i:32
    
    // Debug: Draw a test dot to show we're in the loop
    DRLINE i:0, i:0, i:1, i:1
    
    // Draw a simple rotating square for testing
    // Calculate rotation (simple counter-based)
    READ i:100       // Read counter from memory address 100
    ADD 0, i:1       // Increment counter -> R0
    LOAD 0, i:100    // Store back to memory
    
    // Use counter to create rotating square corners
    DIV 0, i:8       // Divide by 8 for slower rotation -> R0, R1 (remainder)
    MVR 1, 5         // Rotation step in R5 (0-7)
    
    // Debug: Draw rotation counter as dots on top row
    DRLINE 5, i:0, 5, i:0  // Draw dot at position (rotation, 0)
    
    // Calculate square corners based on rotation
    // Create a simple 8x8 square at center (16,16)
    // Use rotation step to offset corners slightly
    
    // Base square coordinates (center 16,16, size 8)
    ADD i:12, 5      // X1 = 12 + rotation (left side)
    MVR 0, 1         
    ADD i:12, 5      // Y1 = 12 + rotation (top side)
    MVR 0, 2         
    
    ADD i:20, 5      // X2 = 20 + rotation (right side)
    MVR 0, 3         
    MVR 2, 4         // Y2 = Y1 (same top)
    
    MVR 3, 6         // X3 = X2 (same right)
    ADD i:20, 5      // Y3 = 20 + rotation (bottom side)
    MVR 0, 7         
    
    MVR 1, 8         // X4 = X1 (same left)  
    MVR 7, 9         // Y4 = Y3 (same bottom)
    
    // Clamp coordinates to screen bounds (0-31)
    AND 1, i:31      // Clamp X1
    MVR 0, 1
    AND 2, i:31      // Clamp Y1
    MVR 0, 2
    AND 3, i:31      // Clamp X2
    MVR 0, 3
    AND 4, i:31      // Clamp Y2
    MVR 0, 4
    AND 6, i:31      // Clamp X3
    MVR 0, 6
    AND 7, i:31      // Clamp Y3
    MVR 0, 7
    AND 8, i:31      // Clamp X4
    MVR 0, 8
    AND 9, i:31      // Clamp Y4
    MVR 0, 9
    
    // Debug: Draw corner positions as dots first
    DRLINE 1, 2, 1, 2    // Corner 1
    DRLINE 3, 4, 3, 4    // Corner 2  
    DRLINE 6, 7, 6, 7    // Corner 3
    DRLINE 8, 9, 8, 9    // Corner 4
    
    // Draw square edges
    DRLINE 1, 2, 3, 4    // Top edge
    DRLINE 3, 4, 6, 7    // Right edge
    DRLINE 6, 7, 8, 9    // Bottom edge
    DRLINE 8, 9, 1, 2    // Left edge
    
    // Swap buffers to display the drawn frame
    // Read current state, flip both bits, write back
    MVR GPU, 10          // Copy current GPU register to R10
    XOR 10, i:3          // Flip both buffer bits -> R0
    MVR 0, GPU           // Update GPU register
    
    // Small delay for animation  
    MVR i:5000, 15       // Shorter delay counter
delay_loop:
    SUB 15, i:1          // Decrement -> R0
    MVR 0, 15            // Update counter
    JNZ 15, delay_loop   // Continue if not zero
    
    JMP main_loop        // Repeat forever

HALT