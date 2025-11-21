// Assembly program demonstrating KEYIN instruction
// This shows direct use of the new 16-bit input system

func_main:
    // Set up input buffer address
    MVR 1, i:0x1000         // R1 = input buffer address
    
    // Simulate adding some characters to the input buffer
    // (In real use, this would be done by the system/user input)
    
    // Read first character using KEYIN
    KEYIN 1                 // Load system input into address 0x1000
    
    // Read the character back from memory to check it worked
    READ 1, 2               // R2 = memory[0x1000] (first char)
    
    // Read second character using KEYIN to next address
    MVR 3, i:0x1001         // R3 = next buffer address
    KEYIN 3                 // Load system input into address 0x1001
    
    // Read the second character back
    READ 3, 4               // R4 = memory[0x1001] (second char)
    
    // Calculate sum of both characters (16-bit arithmetic)
    ADD 2, 4                // Add char1 + char2, result in R0
    
    // Store result in memory for verification
    MVR 5, i:0x2000         // R5 = result storage address
    LOAD 0, 5               // Store result at address 0x2000
    
    // Return the result
    JMP caller_return       // Return to caller (result in R0)

// Demo function showing 16-bit arithmetic limits
func_test_limits:
    // Test maximum 16-bit value
    MVR 1, i:65535          // R1 = 0xFFFF (max 16-bit)
    MVR 2, i:1              // R2 = 1
    ADD 1, 2                // Add max + 1, should wrap to 0
    
    // Test with input buffer operations
    MVR 3, i:0x1500         // R3 = another buffer address
    KEYIN 3                 // Read input to this buffer
    
    // Return result of arithmetic operation
    JMP caller_return

// Function to demonstrate multiple KEYIN calls
func_multi_input:
    MVR 1, i:0x3000         // Base address for input array
    MVR 2, i:0              // Counter i = 0
    MVR 3, i:5              // Loop limit (read 5 characters)
    
input_loop:
    // Check if we've read enough characters
    SUB 2, 3                // Compare i with limit
    JZ input_done, 0        // If result is 0 (i >= limit), exit
    
    // Calculate current buffer address (base + i)
    ADD 1, 2                // R0 = base_addr + i
    MVR 4, 0                // R4 = current address
    
    // Read input character
    KEYIN 4                 // Read input to current address
    
    // Increment counter
    MVR 5, i:1              // R5 = 1
    ADD 2, 5                // i = i + 1
    MVR 2, 0                // Update counter
    
    // Continue loop
    JMP input_loop
    
input_done:
    // Return number of characters read
    MVR 0, 2                // Return counter value
    JMP caller_return