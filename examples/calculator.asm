func_calculate:
MVR 0, 0  // Function: calculate
MVR 7, i:43  // Load char '+' (43)
SUB 4, 7  // Compare case 0
JZ switch_case1, 0  // Jump if equal
MVR 9, i:45  // Load char '-' (45)
SUB 4, 9  // Compare case 1
JZ switch_case2, 0  // Jump if equal
MVR 11, i:42  // Load char '*' (42)
SUB 4, 11  // Compare case 2
JZ switch_case3, 0  // Jump if equal
MVR 13, i:47  // Load char '/' (47)
SUB 4, 13  // Compare case 3
JZ switch_case4, 0  // Jump if equal
JMP switch_default5  // Jump to default
switch_case1:
MVR 0, 0
ADD 5, 6  // + operation
MVR 0, 0  // Set return value
JMP caller_return  // Return to caller
switch_case2:
MVR 0, 0
SUB 5, 6  // - operation
MVR 0, 0  // Set return value
JMP caller_return  // Return to caller
switch_case3:
MVR 0, 0
MULT 5, 6  // * operation
MVR 0, 0  // Set return value
JMP caller_return  // Return to caller
switch_case4:
MVR 0, 0
MVR 15, i:0  // Load literal 0
SUB 6, 15  // Comparison
JNZ true6, 0
MVR 16, i:0
JMP comp_end7
true6:
MVR 0, 0  // Label: true6
MVR 16, i:1  // True case
comp_end7:
MVR 0, 0
JZ else8, 16  // If condition
DIV 5, 6  // / operation
MVR 0, 0  // Set return value
JMP caller_return  // Return to caller
JMP endif9  // Skip else
else8:
MVR 0, 0
endif9:
MVR 0, 0
MVR 17, i:0  // Load literal 0
MVR 17, 0  // Set return value
JMP caller_return  // Return to caller
switch_default5:
MVR 0, 0
MVR 18, i:0  // Load literal 0
MVR 18, 0  // Set return value
JMP caller_return  // Return to caller
switch_end0:
MVR 0, 0
MVR 0, i:0  // Default return 0
JMP caller_return  // Return to caller
func_main:
MVR 0, 0  // Function: main
MVR 20, i:43  // Load char '+' (43)
MVR 20, 4  // Pass argument 0
MVR 21, i:10  // Load literal 10
MVR 21, 5  // Pass argument 1
MVR 22, i:5  // Load literal 5
MVR 22, 6  // Pass argument 2
JAL func_calculate  // Call calculate
MVR 0, 19  // Initialize result1
MVR 24, i:42  // Load char '*' (42)
MVR 24, 4  // Pass argument 0
MVR 25, i:4  // Load literal 4
MVR 25, 5  // Pass argument 1
MVR 26, i:7  // Load literal 7
MVR 26, 6  // Pass argument 2
JAL func_calculate  // Call calculate
MVR 0, 23  // Initialize result2
MVR 28, i:47  // Load char '/' (47)
MVR 28, 4  // Pass argument 0
MVR 29, i:20  // Load literal 20
MVR 29, 5  // Pass argument 1
MVR 30, i:4  // Load literal 4
MVR 30, 6  // Pass argument 2
JAL func_calculate  // Call calculate
MVR 0, 27  // Initialize result3
ADD 19, 23  // + operation
ADD 0, 27  // + operation
MVR 0, 0  // Set return value
JMP caller_return  // Return to caller
func_factorial:
MVR 0, 0  // Function: factorial
MVR 32, i:1  // Load literal 1
SUB 4, 32  // Comparison
MVR 33, i:0
JMP comp_end11
true10:
MVR 0, 0  // Label: true10
MVR 33, i:1  // True case
comp_end11:
MVR 0, 0
JZ else12, 33  // If condition
MVR 34, i:1  // Load literal 1
MVR 34, 0  // Set return value
JMP caller_return  // Return to caller
JMP endif13  // Skip else
else12:
MVR 0, 0
endif13:
MVR 0, 0
MVR 35, i:1  // Load literal 1
SUB 4, 35  // - operation
MVR 0, 4  // Pass argument 0
JAL func_factorial  // Call factorial
MULT 4, 0  // * operation
MVR 0, 0  // Set return value
JMP caller_return  // Return to caller
func_power:
MVR 0, 0  // Function: power
MVR 39, i:1  // Load literal 1
MVR 39, 38  // Initialize result
MVR 41, i:0  // Load literal 0
MVR 41, 40  // Assign to i
for_loop14:
MVR 0, 0
SUB 40, 5  // Comparison
MVR 42, i:0
JMP comp_end18
true17:
MVR 0, 0  // Label: true17
MVR 42, i:1  // True case
comp_end18:
MVR 0, 0
JZ for_end16, 42  // For condition
MULT 38, 4  // * operation
MVR 0, 38  // Assign to result
for_continue15:
MVR 0, 0
MVR 43, i:1  // Load literal 1
ADD 40, 43  // + operation
MVR 0, 40  // Assign to i
JMP for_loop14  // For loop back
for_end16:
MVR 0, 0
MVR 38, 0  // Set return value
JMP caller_return  // Return to caller