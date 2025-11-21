// GPU Register Debug Test  
// Test buffer switching with obvious visual patterns

// Initialize - both buffers use buffer 0
LOAD GPU, i:0                   

// Fill buffer 0 with a pattern (diagonal lines)
LOAD GPU, i:0                   // Display=0, Edit=0
DRGRD i:0, i:0, i:32, i:16      // Fill top half with white
CLRGRID i:0, i:16, i:32, i:16   // Keep bottom half black

// Short pause to see pattern A (top white, bottom black)
LOAD 1, i:300000
loop1:
    SUB 1, i:1
    LOAD 1, 0
    JNZ 1, loop1

// Switch to edit buffer 1 and draw different pattern
LOAD GPU, i:2                   // Display=0, Edit=1
CLRGRID i:0, i:0, i:32, i:16    // Clear top half (black)
DRGRD i:0, i:16, i:32, i:16     // Fill bottom half (white)

// Switch display to buffer 1 (should show bottom white, top black)
LOAD GPU, i:3                   // Display=1, Edit=1

// Longer pause to see pattern B (top black, bottom white)  
LOAD 1, i:600000
loop2:
    SUB 1, i:1
    LOAD 1, 0
    JNZ 1, loop2

// Switch back to display buffer 0 (should show pattern A again)
LOAD GPU, i:2                   // Display=0, Edit=1

// Pause to see pattern A again
LOAD 1, i:600000
loop3:
    SUB 1, i:1
    LOAD 1, 0
    JNZ 1, loop3

HALT