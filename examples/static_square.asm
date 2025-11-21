// Static Square Test - verify basic drawing works
MVR i:0, GPU

// Draw a simple square in center of screen
DRLINE i:0, i:0, i:20, i:2    // Top edge
DRLINE i:20, i:10, i:20, i:20    // Right edge  
DRLINE i:20, i:20, i:10, i:20    // Bottom edge
DRLINE i:10, i:20, i:10, i:10    // Left edge

// Draw diagonal
// DRLINE i:10, i:10, i:20, i:20     Diagonal

// Infinite loop to keep display
loop:
    // Small delay
    MVR i:10000, 1
wait:
    SUB 1, i:1
    MVR 0, 1
    JNZ 1, wait
    
    JMP loop

HALT