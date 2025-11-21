// 3D Rotating Cube with Bhāskara I's Sine Approximation
// Renders a wireframe cube rotating around the origin
// Uses dual-buffer system for smooth animation

// Memory layout:
// 0-23: Original cube vertices (8 vertices * 3 coordinates each)
// 24-47: Transformed vertices after rotation
// 48: Current yaw angle
// 49: Current pitch angle  
// 50: Current roll angle
// 51: Current edit buffer (0 or 1)
// 52: Temporary computation registers
// 53-60: Sine/cosine lookup values
// 61-68: Matrix computation temporaries

start:
    // Initialize cube vertices (scaled by 10 for better precision)
    // Vertex 0: (-10, -10, -10)
    MVR R2, i:-10
    STORE R2, i:0   // x0
    STORE R2, i:1   // y0  
    STORE R2, i:2   // z0

    // Vertex 1: (10, -10, -10)
    MVR R2, i:10
    STORE R2, i:3   // x1
    MVR R2, i:-10
    STORE R2, i:4   // y1
    STORE R2, i:5   // z1

    // Vertex 2: (10, 10, -10)
    MVR R2, i:10
    STORE R2, i:6   // x2
    STORE R2, i:7   // y2
    MVR R2, i:-10
    STORE R2, i:8   // z2

    // Vertex 3: (-10, 10, -10)
    MVR R2, i:-10
    STORE R2, i:9   // x3
    MVR R2, i:10
    STORE R2, i:10  // y3
    MVR R2, i:-10
    STORE R2, i:11  // z3

    // Vertex 4: (-10, -10, 10)
    MVR R2, i:-10
    STORE R2, i:12  // x4
    STORE R2, i:13  // y4
    MVR R2, i:10
    STORE R2, i:14  // z4

    // Vertex 5: (10, -10, 10)
    MVR R2, i:10
    STORE R2, i:15  // x5
    MVR R2, i:-10
    STORE R2, i:16  // y5
    MVR R2, i:10
    STORE R2, i:17  // z5

    // Vertex 6: (10, 10, 10)
    MVR R2, i:10
    STORE R2, i:18  // x6
    STORE R2, i:19  // y6
    STORE R2, i:20  // z6

    // Vertex 7: (-10, 10, 10)
    MVR R2, i:-10
    STORE R2, i:21  // x7
    MVR R2, i:10
    STORE R2, i:22  // y7
    STORE R2, i:23  // z7

    // Initialize rotation angles
    MVR R2, i:0
    STORE R2, i:48  // yaw = 0
    STORE R2, i:49  // pitch = 0
    STORE R2, i:50  // roll = 0
    STORE R2, i:51  // edit_buffer = 0

    // Set initial GPU state (edit buffer 0, display buffer 0)
    MVR R2, i:0
    MVR GPU, R2

main_loop:
    // Clear the current edit buffer
    CLRGRID i:0, i:0, i:32, i:32

    // Transform and render all 8 vertices
    MVR R7, i:0  // vertex counter
transform_loop:
    // Load original vertex coordinates
    MULT R7, i:3  // vertex_index * 3
    ADD R2, i:0   // base address
    
    LOAD R3, R2   // x coordinate
    STORE R3, i:52
    
    ADD R2, i:1
    LOAD R4, R2   // y coordinate
    STORE R4, i:53
    
    ADD R2, i:1
    LOAD R5, R2   // z coordinate
    STORE R5, i:54

    // Apply rotation transformation
    JAL rotate_point

    // Store transformed coordinates
    MULT R7, i:3
    ADD R2, i:24  // transformed vertices base
    
    LOAD R3, i:55  // transformed x
    STORE R3, R2
    
    ADD R2, i:1
    LOAD R4, i:56  // transformed y
    STORE R4, R2
    
    ADD R2, i:1
    LOAD R5, i:57  // transformed z
    STORE R5, R2

    ADD R7, i:1
    MVR R2, i:8
    SUB R2, R7
    JNZ transform_loop

    // Draw cube edges
    JAL draw_cube_edges

    // Update rotation angles
    LOAD R2, i:48  // yaw
    ADD R2, i:3    // yaw increment (fastest)
    MVR R3, i:360
    MOD R2, R3     // keep in 0-359 range
    STORE R2, i:48

    LOAD R2, i:49  // pitch
    ADD R2, i:2    // pitch increment (medium)
    MOD R2, R3
    STORE R2, i:49

    LOAD R2, i:50  // roll
    ADD R2, i:1    // roll increment (slowest)
    MOD R2, R3
    STORE R2, i:50

    // Swap buffers
    LOAD R2, i:51  // current edit buffer
    XOR R2, i:1    // flip between 0 and 1
    STORE R2, i:51

    // Set GPU to edit new buffer and display the completed one
    MVR R3, R2     // edit buffer
    XOR R2, i:1    // display buffer (opposite of edit)
    MULT R2, i:16  // shift display buffer to bits 16-31
    ADD R2, R3     // combine edit and display buffer bits
    MVR GPU, R2

    JMP main_loop

// Function: rotate_point
// Rotates point at (52,53,54) by angles (48,49,50) using rotation matrices
// Stores result in (55,56,57)
rotate_point:
    // Load angles
    LOAD R2, i:48  // yaw
    LOAD R3, i:49  // pitch 
    LOAD R4, i:50  // roll

    // Calculate sine and cosine values using Bhāskara approximation
    MVR R5, R2
    JAL calculate_sin
    STORE R5, i:58  // sin_yaw
    
    MVR R5, R2
    ADD R5, i:90
    MVR R2, i:360
    MOD R5, R2
    JAL calculate_sin
    STORE R5, i:59  // cos_yaw

    LOAD R5, i:49
    JAL calculate_sin
    STORE R5, i:60  // sin_pitch
    
    LOAD R5, i:49
    ADD R5, i:90
    MVR R2, i:360
    MOD R5, R2
    JAL calculate_sin
    STORE R5, i:61  // cos_pitch

    LOAD R5, i:50
    JAL calculate_sin
    STORE R5, i:62  // sin_roll
    
    LOAD R5, i:50
    ADD R5, i:90
    MVR R2, i:360
    MOD R5, R2
    JAL calculate_sin
    STORE R5, i:63  // cos_roll

    // Apply rotation matrix (simplified combined rotation)
    // This is a simplified version - full 3D rotation would require
    // matrix multiplication of yaw * pitch * roll matrices
    
    LOAD R2, i:52  // original x
    LOAD R3, i:53  // original y
    LOAD R4, i:54  // original z
    
    // Rotate around Y axis (yaw)
    LOAD R5, i:59  // cos_yaw
    LOAD R6, i:58  // sin_yaw
    
    MULT R2, R5    // x * cos_yaw  (result in R0)
    MVR R7, R0     // save x * cos_yaw
    MULT R4, R6    // z * sin_yaw  (result in R0)
    SUB R7, R0     // new_x = x*cos_yaw - z*sin_yaw
    STORE R7, i:64
    
    MULT R2, R6    // x * sin_yaw  (result in R0)
    MVR R7, R0     // save x * sin_yaw
    MULT R4, R5    // z * cos_yaw  (result in R0)
    ADD R7, R0     // new_z = x*sin_yaw + z*cos_yaw
    STORE R7, i:66
    
    STORE R3, i:65 // y unchanged for yaw rotation

    // Rotate around X axis (pitch) 
    LOAD R2, i:65  // y from previous rotation
    LOAD R3, i:66  // z from previous rotation
    LOAD R4, i:61  // cos_pitch
    LOAD R5, i:60  // sin_pitch
    
    MULT R2, R4    // y * cos_pitch  (result in R0)
    MVR R6, R0     // save y * cos_pitch
    MULT R3, R5    // z * sin_pitch  (result in R0)
    SUB R6, R0     // new_y = y*cos_pitch - z*sin_pitch
    STORE R6, i:65
    
    MULT R2, R5    // y * sin_pitch  (result in R0)
    MVR R6, R0     // save y * sin_pitch
    MULT R3, R4    // z * cos_pitch  (result in R0)
    ADD R6, R0     // new_z = y*sin_pitch + z*cos_pitch  
    STORE R6, i:66

    // Rotate around Z axis (roll)
    LOAD R2, i:64  // x from previous rotations
    LOAD R3, i:65  // y from previous rotations  
    LOAD R4, i:63  // cos_roll
    LOAD R5, i:62  // sin_roll
    
    MULT R2, R4    // x * cos_roll  (result in R0)
    MVR R6, R0     // save x * cos_roll
    MULT R3, R5    // y * sin_roll  (result in R0)
    SUB R6, R0     // new_x = x*cos_roll - y*sin_roll
    STORE R6, i:55
    
    MULT R2, R5    // x * sin_roll  (result in R0)
    MVR R6, R0     // save x * sin_roll
    MULT R3, R4    // y * cos_roll  (result in R0)
    ADD R6, R0     // new_y = x*sin_roll + y*cos_roll
    STORE R6, i:56
    
    LOAD R2, i:66  // z unchanged for roll rotation
    STORE R2, i:57

    JMP caller_return

// Function: calculate_sin  
// Input: R5 = angle in degrees (0-359)
// Output: R5 = sine * 1000 (scaled for integer precision)
// Uses Bhāskara I's sine approximation: sin(x) ≈ 4x(180-x)/(40500-x(180-x))
calculate_sin:
    // Ensure angle is in 0-180 range for the approximation
    MVR R2, i:180
    SUB R2, R5     // R2 = 180 - angle
    
    // Check if angle > 180
    JZ sin_second_half
    
    // First half (0-180): use angle directly
    MVR R3, R5     // x = angle
    JMP sin_calculate
    
sin_second_half:
    // Second half (180-360): use 360-angle and negate result  
    MVR R3, i:360
    SUB R3, R5     // x = 360 - angle
    
sin_calculate:
    // Calculate 4x(180-x)
    MVR R4, i:180
    SUB R4, R3     // R4 = 180 - x
    MULT R3, R4    // R3 = x(180-x)  (result in R0)
    MVR R6, R0     // save x(180-x)
    MULT R6, i:4   // R6 = 4x(180-x)  (result in R0)
    MVR R7, R0     // save 4x(180-x)
    
    // Calculate 40500 - x(180-x)
    MVR R8, i:40500
    SUB R8, R6     // R8 = 40500 - x(180-x)
    
    // Scale numerator before division for precision
    MULT R7, i:1000  // result in R0
    MVR R9, R0       // save scaled numerator
    
    // Calculate final result
    DIV R9, R8     // R0 = 4x(180-x)*1000 / (40500-x(180-x))
    MVR R5, R0     // store result in R5
    
    // Handle sign for second half
    MVR R2, i:180
    SUB R2, R5     // check original angle
    JZ sin_negate
    JMP sin_done
    
sin_negate:
    MVR R2, i:0
    SUB R2, R5     // negate result  (result in R0)
    MVR R5, R0
    
sin_done:
    JMP caller_return

// Function: draw_cube_edges
// Draws the 12 edges of the cube using transformed vertices
draw_cube_edges:
    // Bottom face edges (z = -10)
    JAL draw_line_0_1  // vertex 0 to 1
    JAL draw_line_1_2  // vertex 1 to 2  
    JAL draw_line_2_3  // vertex 2 to 3
    JAL draw_line_3_0  // vertex 3 to 0
    
    // Top face edges (z = 10)
    JAL draw_line_4_5  // vertex 4 to 5
    JAL draw_line_5_6  // vertex 5 to 6
    JAL draw_line_6_7  // vertex 6 to 7  
    JAL draw_line_7_4  // vertex 7 to 4
    
    // Vertical edges connecting top and bottom
    JAL draw_line_0_4  // vertex 0 to 4
    JAL draw_line_1_5  // vertex 1 to 5
    JAL draw_line_2_6  // vertex 2 to 6
    JAL draw_line_3_7  // vertex 3 to 7
    
    JMP caller_return

// Individual line drawing functions
draw_line_0_1:
    LOAD R2, i:24  // x0
    LOAD R3, i:25  // y0  
    LOAD R4, i:27  // x1
    LOAD R5, i:28  // y1
    JAL draw_line_coords
    JMP caller_return

draw_line_1_2:
    LOAD R2, i:27  // x1
    LOAD R3, i:28  // y1
    LOAD R4, i:30  // x2  
    LOAD R5, i:31  // y2
    JAL draw_line_coords
    JMP caller_return

draw_line_2_3:
    LOAD R2, i:30  // x2
    LOAD R3, i:31  // y2
    LOAD R4, i:33  // x3
    LOAD R5, i:34  // y3  
    JAL draw_line_coords
    JMP caller_return

draw_line_3_0:
    LOAD R2, i:33  // x3
    LOAD R3, i:34  // y3
    LOAD R4, i:24  // x0
    LOAD R5, i:25  // y0
    JAL draw_line_coords  
    JMP caller_return

draw_line_4_5:
    LOAD R2, i:36  // x4
    LOAD R3, i:37  // y4
    LOAD R4, i:39  // x5
    LOAD R5, i:40  // y5
    JAL draw_line_coords
    JMP caller_return

draw_line_5_6:
    LOAD R2, i:39  // x5  
    LOAD R3, i:40  // y5
    LOAD R4, i:42  // x6
    LOAD R5, i:43  // y6
    JAL draw_line_coords
    JMP caller_return

draw_line_6_7:
    LOAD R2, i:42  // x6
    LOAD R3, i:43  // y6  
    LOAD R4, i:45  // x7
    LOAD R5, i:46  // y7
    JAL draw_line_coords
    JMP caller_return

draw_line_7_4:
    LOAD R2, i:45  // x7
    LOAD R3, i:46  // y7
    LOAD R4, i:36  // x4
    LOAD R5, i:37  // y4  
    JAL draw_line_coords
    JMP caller_return

draw_line_0_4:
    LOAD R2, i:24  // x0
    LOAD R3, i:25  // y0
    LOAD R4, i:36  // x4
    LOAD R5, i:37  // y4
    JAL draw_line_coords
    JMP caller_return

draw_line_1_5:  
    LOAD R2, i:27  // x1
    LOAD R3, i:28  // y1
    LOAD R4, i:39  // x5  
    LOAD R5, i:40  // y5
    JAL draw_line_coords
    JMP caller_return

draw_line_2_6:
    LOAD R2, i:30  // x2
    LOAD R3, i:31  // y2
    LOAD R4, i:42  // x6
    LOAD R5, i:43  // y6
    JAL draw_line_coords  
    JMP caller_return

draw_line_3_7:
    LOAD R2, i:33  // x3
    LOAD R3, i:34  // y3
    LOAD R4, i:45  // x7
    LOAD R5, i:46  // y7
    JAL draw_line_coords
    JMP caller_return

// Function: draw_line_coords
// Draws a line from (R2,R3) to (R4,R5) 
// Converts 3D coordinates to screen coordinates and calls DRLINE
draw_line_coords:
    // Convert coordinates to screen space (16,16) center, scale down
    ADD R2, i:16   // center x  (result in R0)
    MVR R6, R0     // save centered x1
    DIV R6, i:2    // scale down  (result in R0)
    MVR R2, R0     // store scaled x1
    
    ADD R3, i:16   // center y  (result in R0)
    MVR R7, R0     // save centered y1
    DIV R7, i:2    // scale down  (result in R0)
    MVR R3, R0     // store scaled y1
    
    ADD R4, i:16   // center x  (result in R0)
    MVR R8, R0     // save centered x2
    DIV R8, i:2    // scale down  (result in R0)
    MVR R4, R0     // store scaled x2
    
    ADD R5, i:16   // center y  (result in R0)
    MVR R9, R0     // save centered y2
    DIV R9, i:2    // scale down  (result in R0)
    MVR R5, R0     // store scaled y2
    
    // Clamp coordinates to screen bounds (0-31)
    MVR R6, i:0
    MVR R7, i:31
    
    // Clamp x1
    SUB R6, R2     // check if x1 < 0
    JZ clamp_x1_min
    JMP check_x1_max
clamp_x1_min:
    MVR R2, i:0
check_x1_max:
    SUB R2, R7     // check if x1 > 31
    JZ clamp_x1_max  
    JMP check_y1
clamp_x1_max:
    MVR R2, i:31
    
check_y1:
    MVR R6, i:0
    SUB R6, R3     // check if y1 < 0
    JZ clamp_y1_min
    JMP check_y1_max
clamp_y1_min:
    MVR R3, i:0  
check_y1_max:
    SUB R3, R7     // check if y1 > 31
    JZ clamp_y1_max
    JMP check_x2
clamp_y1_max:
    MVR R3, i:31

check_x2:
    MVR R6, i:0
    SUB R6, R4     // check if x2 < 0
    JZ clamp_x2_min
    JMP check_x2_max
clamp_x2_min:
    MVR R4, i:0
check_x2_max:  
    SUB R4, R7     // check if x2 > 31
    JZ clamp_x2_max
    JMP check_y2
clamp_x2_max:
    MVR R4, i:31

check_y2:
    MVR R6, i:0
    SUB R6, R5     // check if y2 < 0
    JZ clamp_y2_min
    JMP check_y2_max
clamp_y2_min:
    MVR R5, i:0
check_y2_max:
    SUB R5, R7     // check if y2 > 31
    JZ clamp_y2_max
    JMP draw_final_line
clamp_y2_max:
    MVR R5, i:31
    
draw_final_line:
    DRLINE R2, R3, R4, R5
    JMP caller_return

caller_return:
    // Return point for function calls
    JMP R15  // Jump to return address stored in R15