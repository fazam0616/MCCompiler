// Character Cycle Display Program
// Infinitely loops through all ASCII characters (32-126)
// Each character is displayed in the top-left corner for 2 cycles
// then clears the screen and moves to the next character

// Initialize character counter to 32 (space character)
MVR i:32, 1

// Main loop - cycle through characters
main_loop:
    // Clear the entire screen (32x32 pixels)
    CLRGRID i:0, i:0, i:32, i:32
    
    // Load current character into text buffer at address 0
    LDTXT i:0, 1
    
    // Draw the character at position (0,0) - top left corner
    DRTXT i:0, i:0, i:0
    
    // Wait 2 cycles by doing some dummy operations
    MVR i:0, 10      // Cycle 1: Move 0 to register 10
    MVR i:0, 11      // Cycle 2: Move 0 to register 11
    
    // Increment character counter
    ADD 1, i:1
    MVR 0, 1         // Move result back to R1
    
    // Check if we've reached 127 (past printable ASCII)
    SUB 1, i:127
    JZ reset_counter, 0    // If R1 == 127, reset to 32
    
    // Continue with next character
    JMP main_loop
    
reset_counter:
    // Reset counter back to 32 (space character)
    MVR i:32, 1
    JMP main_loop

HALT