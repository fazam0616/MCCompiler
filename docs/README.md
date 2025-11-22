# Getting Started with MCL

## What is MCL?

MCL (Minecraft Computer Language) is a simple, C-like programming language designed for a 16 bit computer, implemented in Minecraft. It compiles to a custom assembly language that runs on a simulated virtual machine with graphics capabilities.

## Your First MCL Program

### 1. Hello World

Create a file called `my_first_program.mcl`:

```mcl
// My first MCL program
function main() {
    var greeting: int = 72;  // ASCII value for 'H'
    return greeting;
}
```

### 2. Compile the Program

```bash
python src/compiler/main.py my_first_program.mcl
```

This creates `my_first_program.asm` containing the assembly code.

### 3. Run the Program

```bash
python src/vm/virtual_machine.py --file my_first_program.asm
```

## Language Basics

### Language Features

MCL supports:
- **Variable Declarations**: Both `var name: type` and C-style `type name` syntax
- **Data Types**: `int`, `char`, `void`, pointers (`type*`), arrays (`type[size]`)
- **Operators**: 
  - Arithmetic: `+`, `-`, `*`, `/`, `%`
  - Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
  - Logical: `&&`, `||`, `!`
  - Bitwise: `&`, `|`, `^`, `~`, `<<`, `>>`
- **Keyword Operators**: `and`, `or`, `xor`, `not` (bitwise operations)
- **Memory Management**: Built-in `malloc()` and `free()` functions
- **GPU Functions**: Built-in graphics functions (see GPU section)
- **Pointers**: Address-of with `@`, dereference with `*`
- **Control Flow**: `if`/`else`, `while`, `for`, `switch`/`case`/`default`
- **Function Control**: `return`, `break`, `continue`
- **Comments**: Single-line with `//`
- **Literals**: Integer (decimal/hex), character with escape sequences

### Variables and Types

```mcl
function main() {
    // Integer variables (default type)
    var age: int = 25;
    var year: int;
    
    // Character variables  
    var letter: char = 'A';
    
    // C-style declarations also supported
    int count = 10;
    int* ptr;
    
    // Arrays
    var numbers: int[10];
    var letters: char[5];
    
    return 0;
}
```

### Control Flow

```mcl
// If statements
function check_number(x: int) {
    if (x > 0) {
        return 1;  // Positive
    } else if (x < 0) {
        return -1; // Negative  
    } else {
        return 0;  // Zero
    }
}

// While loops
function count_down(start: int) {
    var i: int = start;
    
    while (i > 0) {
        i = i - 1;
    }
    
    return i;
}

// For loops
function sum_to_n(n: int) {
    var sum: int = 0;
    var i: int;
    
    for (i = 1; i <= n; i = i + 1) {
        sum = sum + i;
    }
    
    return sum;
}
```

### Functions

```mcl
// Function with parameters and return value
function add(a: int, b: int) {
    return a + b;
}

// Function with no return value
function print_number(n: int) {
    // In a real implementation, this might output the number
    var temp: int = n;
}

// Recursive function
function factorial(n: int) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
```

### Pointers and Arrays

```mcl
function array_example() {
    var numbers: int[5];
    var i: int;
    var ptr: int*;
    
    // Initialize array
    for (i = 0; i < 5; i = i + 1) {
        numbers[i] = i * 10;
    }
    
    // Use pointers (@ is address-of operator)
    ptr = @numbers[0];  // Point to first element
    var first: int = *ptr;  // Dereference to get value
    
    // Pointer arithmetic
    ptr = ptr + 1;  // Move to next element
    var second: int = *ptr;
    
    return first + second;
}
```

### Switch Statements

```mcl
function grade_to_gpa(grade: char) {
    switch (grade) {
        case 'A': {
            return 4;
        }
        case 'B': {
            return 3;
        }
        case 'C': {
            return 2;
        }
        case 'D': {
            return 1;
        }
        default: {
            return 0;
        }
    }
}
```

## GPU Programming

### Dual Buffer System

MCL supports advanced graphics programming through a dual-buffer GPU system:

```mcl
function animate_square() {
    // MCL has built-in GPU functions:
    // drawLine, fillGrid, clearGrid, loadSprite, drawSprite,
    // loadText, drawText, scrollBuffer
    // setGPUBuffer, getGPUBuffer

    // Clear and draw a square
    clearGrid(0, 0, 32, 32);
    fillGrid(10, 10, 5, 5);

    // Draw a line
    drawLine(0, 0, 31, 31);

    // Set edit buffer to 1 (buffer 1)
    setGPUBuffer(0, 1); // 0 = edit buffer, 1 = buffer 1

    // Set display buffer to 0 (buffer 0)
    setGPUBuffer(1, 0); // 1 = display buffer, 0 = buffer 0

    // Query buffer state
    var editBuf: int = getGPUBuffer(0); // returns 0 or 1
    var dispBuf: int = getGPUBuffer(1); // returns 0 or 1

    return 0;
}
```

#### setGPUBuffer(a, b)
Sets the GPU buffer state. `a` is 0 for edit buffer, 1 for display buffer. `b` is 0 or 1 (buffer index).

#### getGPUBuffer(a)
Returns the current buffer index (0 or 1) for the requested buffer. `a` is 0 for edit buffer, 1 for display buffer.

### Assembly GPU Register Access

For direct GPU control, use assembly language:

```assembly
// Switch edit buffer to buffer 1
MVR i:1, 0
MVR 0, GPU

// Draw operations happen on buffer 1
// ... drawing commands ...

// Switch display to buffer 1 (value 17 = edit buffer 1 + display buffer 1)
MVR i:17, 0
MVR 0, GPU
```

The GPU register bits:
- Bits 0-15: Edit buffer selection (0 or 1) 
- Bits 16-31: Display buffer selection (0 or 1)

## Working with the Tools

### Compiler Options

```bash
# Basic compilation
python src/compiler/main.py program.mcl

# Specify output file
python src/compiler/main.py program.mcl -o custom_name.asm

# Enable debug output
python src/compiler/main.py program.mcl --debug

# Validate syntax only (don't generate assembly)
python src/compiler/main.py program.mcl --validate-only
```

### Virtual Machine Options

```bash
# Run with graphics
python src/vm/virtual_machine.py --file program.asm

# Run without graphics (faster)
python src/vm/virtual_machine.py --file program.asm --headless

# Enable debugging output  
python src/vm/virtual_machine.py --file program.asm --debug

# Set display scale (default is 2)
python src/vm/virtual_machine.py --file program.asm --scale 3

# Control CPU speed (0.5Hz to 1kHz exponential scaling)
# Speed is adjustable via GUI slider during execution
```

### Interactive Debugger

```bash
# Start debugger
python src/debugger/main.py program.asm

# Debugger commands:
# step      - Execute one instruction
# next      - Execute until next line
# continue  - Continue execution
# break 10  - Set breakpoint at line 10
# registers - Show all register values
# memory    - Show memory contents
# quit      - Exit debugger
```

## Common Patterns

### Finding Maximum in Array

```mcl
function find_max(arr: int*, size: int) {
    var max: int = arr[0];
    var i: int;
    
    for (i = 1; i < size; i = i + 1) {
        if (arr[i] > max) {
            max = arr[i];
        }
    }
    
    return max;
}
```

### Bubble Sort

```mcl
function bubble_sort(arr: int*, size: int) {
    var i: int;
    var j: int;
    var temp: int;
    
    for (i = 0; i < size - 1; i = i + 1) {
        for (j = 0; j < size - i - 1; j = j + 1) {
            if (arr[j] > arr[j + 1]) {
                // Swap elements
                temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
}
```

### Binary Search

```mcl
function binary_search(arr: int*, size: int, target: int) {
    var left: int = 0;
    var right: int = size - 1;
    var mid: int;
    
    while (left <= right) {
        mid = (left + right) / 2;
        
        if (arr[mid] == target) {
            return mid;  // Found at index mid
        } else if (arr[mid] < target) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    
    return -1;  // Not found
}
```

## Assembly Syntax Examples

### Valid Syntax

```assembly
// Moving values to registers
MVR i:42, 5          // Move decimal 42 to register 5
MVR 0xFF, 6          // Move hex 255 to register 6  
MVR 5, 7             // Copy register 5 to register 7

// Memory operations
LOAD i:123, i:100    // Store 123 at memory address 100
LOAD 0x7B, 0x64      // Store 123 at memory address 100 (hex)
READ i:100, 8        // Load from address 100 into register 8
READ 0x64, 9         // Load from address 100 into register 9

// Arithmetic with mixed operands
ADD i:10, 5          // Add 10 to register 5, result in register 0
SUB 3, i:20          // Subtract 20 from register 3
MULT 0x0A, 0x14      // Multiply hex 10 and hex 20
```

### Invalid Syntax (Will Cause Errors)

```assembly
// ❌ Immediate destinations not allowed for MVR/READ
MVR i:42, i:5        // ERROR: MVR destination cannot be immediate
READ i:100, i:8      // ERROR: READ destination cannot be immediate

// ❌ Raw decimals treated as registers, not immediate values
MVR 42, 5            // This moves register 42 to register 5, not value 42!
```

## Understanding the Assembly Output

When you compile MCL code, you get assembly that looks like this:

```assembly
// Generated assembly for simple addition
func_main:
    MVR i:10, 4           // Load 10 into register 4
    MVR i:20, 5           // Load 20 into register 5
    ADD 4, 5              // Add register 5 to register 4, result in register 0
    MVR 0, 6              // Move result from register 0 to register 6
    JMP caller_return     // Return from function
```

### Key Assembly Instructions

- `MVR src, dest`: Move value to register (dest must be register, src can be immediate/hex/register)
- `LOAD value, addr`: Store value at memory address (both can be immediate/hex/register)
- `READ addr, reg`: Load from memory address into register (reg must be register)
- `ADD/SUB/MULT/DIV`: Arithmetic operations (operands can be immediate/hex/register)
- `JMP/JZ/JNZ`: Jump instructions
- `JAL`: Jump and link (function calls)
- `HALT`: Stop execution
- **Special Registers**: `GPU` register for direct GPU control

### Assembly Syntax Rules

- **Immediate decimals**: Use `i:` prefix (e.g., `i:42`, `i:100`)
- **Immediate hex**: Use `0x` prefix (e.g., `0xFF`, `0x100`) 
- **Raw decimals**: Always register numbers (e.g., `5` = register 5)
- **Destinations**: Must be registers for MVR and READ instructions
- **Comments**: Use `//` for line comments or `;` for inline comments

### Built-in Functions

MCL provides several built-in functions that are recognized as keywords:

#### Memory Management
- `malloc(size)`: Allocate memory
- `free(ptr)`: Free allocated memory

#### GPU Functions
- `drawLine(x1, y1, x2, y2)`: Draw a line
- `fillGrid(x, y, width, height)`: Fill a rectangular area
- `clearGrid(x, y, width, height)`: Clear a rectangular area
- `loadSprite(data)`: Load sprite data
- `drawSprite(x, y, sprite_id)`: Draw a loaded sprite
- `loadText(text)`: Load text data
- `drawText(x, y, text_id)`: Draw loaded text
- `scrollBuffer()`: Scroll the display buffer

## Troubleshooting

### Common Compilation Errors

1. **Syntax Error: Unexpected token**
   - Check for missing semicolons
   - Verify bracket matching `{}`
   - Check function declaration syntax

2. **Undefined variable**
   - Declare variables with `var` keyword
   - Check variable scope
   
3. **Type mismatch** 
   - Verify function return types
   - Check array indexing with integers
   
### Runtime Issues

1. **Infinite loops**
   - Check loop conditions
   - Ensure loop variables are modified
   
2. **Stack overflow**
   - Check for infinite recursion
   - Verify base cases in recursive functions

### Getting Help

- Look at examples in the `examples/` directory
- Run the test suite: `python tests/run_tests.py`
- Check compiler output with `--debug` flag
- Use the interactive debugger to step through code

## Next Steps

1. **Try the examples**: Compile and run programs in `examples/`
2. **Set up VSCode**: Install the extension for better editing experience
3. **Write your own programs**: Start with simple algorithms
4. **Explore the virtual machine**: Try graphics programming with GPU commands
5. **Study the assembly**: Learn how high-level constructs map to assembly

Happy coding with MCL! 🎮