# GPU Built-in Functions in MCL

## Overview

The MCL language provides built-in GPU functions for graphics operations on a 32x32 pixel display. The GPU uses a dual-buffer system where each row is stored as a 32-bit integer, with each bit representing one pixel.

## GPU Architecture

### Dual Buffer System
- **Buffer 0** and **Buffer 1**: Two 32×32 pixel buffers
- **Edit buffer**: the buffer currently being drawn to — controlled by `setGPUBuffer(0, id)`
- **Display buffer**: the buffer currently shown on screen — controlled by `setGPUBuffer(1, id)`
- **Row storage**: each row is a 32-bit integer; MSB = leftmost pixel (bit 31 = x=0, bit 0 = x=31)

Buffer selection is managed exclusively through the `setGPUBuffer()` and `getGPUBuffer()` built-in functions. There is no general-purpose assembly register for buffer control.

### Pixel Operations
All drawing operations use bitwise OR, meaning:
- Setting a pixel: `row |= (1 << (31 - x))`
- Clearing pixels: `row &= ~mask`
- Pixels are 1-bit (black/white): 1 = white, 0 = black

## Built-in Functions

### Display Management

#### `clearGrid(x: int, y: int, width: int, height: int)`
Clears (sets to 0) pixels in a rectangular area.
- **Assembly**: `CLRGRID`
- **Example**: `clearGrid(0, 0, 32, 32);` // Clear entire screen

#### `fillGrid(x: int, y: int, width: int, height: int)`  
Fills (sets to 1) pixels in a rectangular area.
- **Assembly**: `DRGRD`
- **Example**: `fillGrid(10, 10, 5, 5);` // Fill 5x5 square

### Line Drawing

#### `drawLine(x1: int, y1: int, x2: int, y2: int)`
Draws a line using row-by-row algorithm with proper anti-aliasing.
- **Assembly**: `DRLINE`
- **Algorithm**: Uses precise integer math for pixel-perfect lines
- **Example**: `drawLine(0, 0, 31, 31);` // Diagonal line

### Sprite System

#### `loadSprite(id: int, data: int)`
Loads a 5x3 pixel sprite into sprite memory.
- **Assembly**: `LDSPR`
- **Data Format**: 15 bits of sprite data (5x3 pixels)
- **ID Range**: 0-31 (5-bit addressing)
- **Example**: `loadSprite(1, 0x7FFF);` // Load filled sprite

#### `drawSprite(id: int, x: int, y: int)`
Draws a loaded sprite at the specified position.
- **Assembly**: `DRSPR`  
- **Size**: 5x3 pixels
- **Example**: `drawSprite(1, 10, 10);` // Draw sprite 1 at (10,10)

### Text Rendering

#### `loadText(id: int, data: int)`
Loads a 6-bit character into text memory.
- **Assembly**: `LDTXT`
- **Data Format**: 6-bit character code (A-Z, 0-9, !?+-*.,')
- **ID Range**: 0-16383 (14-bit addressing)
- **Character Set**: A-Z (0-25), 0-9 (26-35), !?+-*., (36-42)
- **Example**: `loadText(0, 0);` // Load character 'A' (code 0)

#### `drawText(id: int, x: int, y: int)`
Renders a loaded text character using 5x5 font.
- **Assembly**: `DRTXT`
- **Text System**: 5x5 font with 14-bit addressing (16384 characters max)
- **Example**: `drawText(0, 5, 5);` // Draw character at (5,5)

### Buffer Control

#### `setGPUBuffer(buffer_id: int, value: int)`
Sets one of the two GPU buffer selectors.
- `buffer_id = 0` — sets the **edit buffer** (which buffer drawing commands write to)
- `buffer_id = 1` — sets the **display buffer** (which buffer is shown on screen)
- `value` — buffer index: `0` = buffer 0, `1` = buffer 1
- **Example**: `setGPUBuffer(0, 1);` // draw to buffer 1
- **Example**: `setGPUBuffer(1, 0);` // display buffer 0

#### `getGPUBuffer(buffer_id: int) -> int`
Reads the current buffer selector.
- `buffer_id = 0` — returns the current **edit buffer** index
- `buffer_id = 1` — returns the current **display buffer** index
- **Example**: `var eb: int = getGPUBuffer(0);`

#### `scrollBuffer(offx: int, offy: int)`
Scrolls the edit buffer by the specified offsets.
- **Assembly**: `SCRLBFR`
- **X Offset**: Positive = scroll right, Negative = scroll left
- **Y Offset**: Positive = scroll down, Negative = scroll up
- **Example**: `scrollBuffer(1, 0);` // Scroll right by 1 pixel

## Usage Examples

### Basic Graphics
```mcl
function drawFrame() -> void {
    // Clear screen
    clearGrid(0, 0, 32, 32);
    
    // Draw border
    drawLine(0, 0, 31, 0);   // Top
    drawLine(0, 31, 31, 31); // Bottom  
    drawLine(0, 0, 0, 31);   // Left
    drawLine(31, 0, 31, 31); // Right
    
    // Fill center area
    fillGrid(10, 10, 12, 12);
}
```

### Sprite Animation
```mcl
function animateSprite() -> void {
    // Load sprite data (5x3 cross pattern)
    var crossSprite: int = 0x4E4;  // 01001 11100 01000
    loadSprite(1, crossSprite);
    
    // Animate across screen
    var x: int = 0;
    while (x < 28) {
        clearGrid(0, 0, 32, 32);
        drawSprite(1, x, 15);
        x = x + 1;
    }
}
```

### Text Display
```mcl
function showMessage() -> void {
    clearGrid(0, 0, 32, 32);
    
    // Load and display "HELLO"
    loadText(0, 7);   // 'H' (A=0, B=1... H=7)
    loadText(1, 4);   // 'E' (E=4)
    loadText(2, 11);  // 'L' (L=11)
    loadText(3, 11);  // 'L' (L=11)
    loadText(4, 14);  // 'O' (O=14)
    
    // Render at positions
    drawText(0, 2, 10);   // H
    drawText(1, 8, 10);   // E
    drawText(2, 14, 10);  // L
    drawText(3, 20, 10);  // L
    drawText(4, 26, 10);  // O
}
```

### Dual Buffer Animation
```mcl
function animate() {
    while (1) {
        // Draw frame A on buffer 0, display buffer 1
        setGPUBuffer(0, 0);           // edit → buffer 0
        clearGrid(0, 0, 32, 32);
        fillGrid(10, 10, 5, 5);
        setGPUBuffer(1, 1);           // display → buffer 1 (previously drawn)

        // Draw frame B on buffer 1, display buffer 0
        setGPUBuffer(0, 1);           // edit → buffer 1
        clearGrid(0, 0, 32, 32);
        fillGrid(15, 15, 5, 5);
        setGPUBuffer(1, 0);           // display → buffer 0
    }
}
```

## Technical Details

### Line Drawing Algorithm
The `drawLine` function uses a precise row-by-row algorithm:

1. **Setup Phase**: Calculate line parameters once
2. **Per Scanline**: For each row, calculate exact pixel range
3. **Bit Manipulation**: Use shifts and masks for efficient pixel setting

### Sprite Format
5x3 sprites are stored as 15-bit integers:
```
Bit pattern for 5x3 sprite:
Row 0: bits 14-10
Row 1: bits 9-5  
Row 2: bits 4-0
```

### 6-bit Character System
The text system uses a compact 6-bit encoding:

**Character Encoding:**
- A-Z: codes 0-25
- 0-9: codes 26-35  
- Special: codes 36-42 (!?+-*.,)

**Font Format:**
5x5 patterns stored as 25-bit integers:
```
Font 'A' (code 0):
01110  -> 0b0111010001100011111110001
10001
10001  
11111
10001
```

**Memory Layout:**
- 6-bit character code + 14-bit address = 20 bits total
- Max 16,384 text positions (14-bit addressing)
- No space character (not in character set)

### Performance Notes
- All operations work directly on 32-bit row data
- Bit operations are highly efficient
- OR-based drawing allows overlay effects
- Real-time rendering at 60 FPS supported