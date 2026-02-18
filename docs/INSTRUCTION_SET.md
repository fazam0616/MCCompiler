# MCL CPU Instruction Set Reference

This document is the complete datasheet for the MCL virtual CPU. All instructions, their operand order, operand types, and side effects are described here.

---

## Notation

| Token | Meaning |
|---|---|
| `Rx` | A general-purpose register number (0–31) |
| `imm` | An immediate (literal) integer value — written as `i:N` in assembly |
| `addr` | A RAM address — either immediate (`i:0x1000`) or the value of a register |
| `label` | A symbolic label that resolves to an instruction address at load time |
| `R0` / `R1` | **ALU output registers** — written by every arithmetic/bitwise instruction |
| `R2` | **Return-address register** — written by `JAL` |
| `R3` | **Stack pointer** — managed by software convention |
| `R4` | **Frame pointer** — managed by software convention |

Operand sources accept either a register number or an immediate value unless stated otherwise. An operand noted as `reg` is **register-only** (immediates are rejected at runtime).

---

## Register File

| Register | Role | Notes |
|---|---|---|
| R0 | Primary ALU output / return value | Overwritten by every ALU instruction |
| R1 | Secondary ALU output | Overwritten by `MULT` (high word) and `DIV` (remainder) |
| R2 | Return address | Written by `JAL`; must be saved/restored across calls |
| R3 | Stack pointer (by convention) | Not enforced by hardware |
| R4 | Frame pointer (by convention) | Not enforced by hardware |
| R5–R31 | General purpose | No hardware meaning |

All general-purpose registers are **16-bit unsigned** (values wrap at 65 536).

---

## Memory Instructions

### `LOAD  src, dst_addr`
Store a value into RAM.

| # | Operand | Accepts |
|---|---|---|
| 1 | `src` — value to write | register **or** immediate |
| 2 | `dst_addr` — RAM address to write to | register (value used as address) **or** immediate address |

```assembly
LOAD  31, i:0x1000    // RAM[0x1000] = R31
LOAD  i:42, i:0x1001  // RAM[0x1001] = 42
LOAD  5, 3            // RAM[R3] = R5
```

---

### `READ  src_addr, dst`
Load a value from RAM into a register.

| # | Operand | Accepts |
|---|---|---|
| 1 | `src_addr` — RAM address to read from | register (value used as address) **or** immediate address |
| 2 | `dst` — destination register | **register only** |

```assembly
READ  i:0x1000, 31    // R31 = RAM[0x1000]
READ  3, 5            // R5  = RAM[R3]
```

---

### `MVR  src, dst`
Move a value into a register. No ALU side-effects; R0 is **not** clobbered.

| # | Operand | Accepts |
|---|---|---|
| 1 | `src` — value to move | register **or** immediate |
| 2 | `dst` — destination | **register only** (including `GPU`) |

```assembly
MVR  i:123, 31        // R31 = 123
MVR  30, 31           // R31 = R30
MVR  0, 5             // R5 = R0  (save ALU result)
```

---

### `MVM  src_addr, dst_addr`
Copy a value from one RAM address to another.

| # | Operand | Accepts |
|---|---|---|
| 1 | `src_addr` — source RAM address | register (value used as address) **or** immediate address |
| 2 | `dst_addr` — destination RAM address | register (value used as address) **or** immediate address |

```assembly
MVM  i:0x1000, i:0x1001   // RAM[0x1001] = RAM[0x1000]
MVM  5, 6                 // RAM[R6] = RAM[R5]
```

---

## Arithmetic Instructions

All arithmetic instructions write their **primary result to R0**. `MULT` and `DIV` also write a secondary result to R1.

### `ADD  A, B`
`R0 = A + B` (16-bit, wraps on overflow)

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | register **or** immediate |
| 2 | `B` | register **or** immediate |

```assembly
ADD  5, 6       // R0 = R5 + R6
ADD  5, i:1     // R0 = R5 + 1   (e.g. SP increment)
```

---

### `SUB  A, B`
`R0 = A − B` (16-bit two's complement)

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` (minuend) | register **or** immediate |
| 2 | `B` (subtrahend) | register **or** immediate |

```assembly
SUB  5, 6       // R0 = R5 - R6
SUB  3, i:1     // R0 = SP - 1   (e.g. SP decrement)
```

> **Sign convention**: the result is 16-bit two's complement. To test `A < B` check the sign bit (`0x8000`) of `R0` after `SUB A, B`.

---

### `MULT  A, B`
`R0 = (A × B) & 0xFFFF` (low 16 bits),  `R1 = (A × B) >> 16` (high 16 bits)

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | register **or** immediate |
| 2 | `B` | register **or** immediate |

```assembly
MULT  5, 6      // R0 = low16(R5 × R6),  R1 = high16(R5 × R6)
```

---

### `DIV  A, B`
Signed integer division.  
`R0 = quotient`,  `R1 = remainder`

Division uses C-style truncation (rounds toward zero).

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` (dividend) | register **or** immediate |
| 2 | `B` (divisor) | register **or** immediate |

```assembly
DIV  5, 6       // R0 = R5 / R6,  R1 = R5 % R6
```

> Raises a runtime exception on division by zero.

---

## Shift / Rotate Instructions

All shift instructions write their result to **R0**.

### `SHL  A, B`
`R0 = A << B` (logical left shift, 16-bit)

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | register **or** immediate |
| 2 | `B` — shift amount | register **or** immediate |

```assembly
SHL  5, i:2     // R0 = R5 << 2
```

---

### `SHR  A, B`
`R0 = A >> B` (logical right shift, 16-bit)

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | register **or** immediate |
| 2 | `B` — shift amount | register **or** immediate |

```assembly
SHR  5, i:1     // R0 = R5 >> 1
```

---

### `SHLR  A, B`
`R0 = rotate_left(A, B)` — 16-bit left rotation (bits shifted out of the MSB wrap to the LSB).

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | register **or** immediate |
| 2 | `B` — rotation amount | register **or** immediate |

```assembly
SHLR  5, i:3    // R0 = R5 rotated left by 3 bits
```

---

## Bitwise Instructions

All bitwise binary instructions write their result to **R0**.

### `AND  A, B`
`R0 = A & B`

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | register **or** immediate |
| 2 | `B` | register **or** immediate |

```assembly
AND  5, i:0xFF00   // R0 = R5 & 0xFF00
AND  0, 31         // R0 = R0 & R31   (mask ALU result)
```

---

### `OR  A, B`
`R0 = A | B`

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | register **or** immediate |
| 2 | `B` | register **or** immediate |

```assembly
OR  5, i:0x0001    // R0 = R5 | 1
```

---

### `XOR  A, B`
`R0 = A ^ B`

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | register **or** immediate |
| 2 | `B` | register **or** immediate |

```assembly
XOR  5, 5          // R0 = 0  (clear self)
```

---

### `NOT  A`
`A = ~A` — bitwise NOT written **back into the source register** (not into R0).

| # | Operand | Accepts |
|---|---|---|
| 1 | `A` | **register only** — immediates are rejected |

```assembly
NOT  5    // R5 = ~R5  (result stored in R5, R0 unchanged)
```

> `NOT` is the only arithmetic/bitwise instruction that **modifies its source** and does **not** write to R0.

---

## Control-Flow Instructions

### `JMP  target`
Unconditional jump. PC is set to `target`; the next sequential instruction is **not** executed.

| # | Operand | Accepts |
|---|---|---|
| 1 | `target` | **label**, immediate address, or register (register value used as address) |

```assembly
JMP  loop_start    // jump to label
JMP  2             // jump to address in R2  (i.e. return)
JMP  i:0x0010      // jump to literal address
```

---

### `JAL  target`
Jump-and-link: `R2 = PC + 1`, then jump to `target`. Used for subroutine calls.

| # | Operand | Accepts |
|---|---|---|
| 1 | `target` | **label**, immediate address, or register |

```assembly
JAL  func_foo      // R2 = return address, PC = func_foo
```

---

### `JZ  target, cond`
Jump if zero: if `cond == 0` then `PC = target`, else `PC = PC + 1`.

| # | Operand | Accepts |
|---|---|---|
| 1 | `target` | label, immediate address, or register |
| 2 | `cond` | register **or** immediate |

```assembly
JZ  end_label, 0   // jump if R0 == 0
JZ  else_label, 5  // jump if R5 == 0
```

---

### `JNZ  target, cond`
Jump if not zero: if `cond != 0` then `PC = target`, else `PC = PC + 1`.

| # | Operand | Accepts |
|---|---|---|
| 1 | `target` | label, immediate address, or register |
| 2 | `cond` | register **or** immediate |

```assembly
JNZ  loop, 5       // jump if R5 != 0
```

---

### `JBT  target, x, y`
Jump if greater-than: if `x > y` (unsigned comparison) then `PC = target`, else `PC = PC + 1`.

| # | Operand | Accepts |
|---|---|---|
| 1 | `target` | label, immediate address, or register |
| 2 | `x` | register **or** immediate |
| 3 | `y` | register **or** immediate |

```assembly
JBT  overflow, 5, i:100   // jump if R5 > 100
```

---

## System Instructions

### `KEYIN  addr`
Blocking keyboard read. Waits until a character is available, then writes its **6-bit character code** to RAM at `addr`.

| # | Operand | Accepts |
|---|---|---|
| 1 | `addr` — destination RAM address | immediate address or register (value used as address) |

**Character encoding:**

| Range | Characters | Codes |
|---|---|---|
| Letters | A–Z | 0–25 |
| Digits | 0–9 | 26–35 |
| Symbols | `! ? + - * . ,` | 36–42 |

```assembly
KEYIN  i:0x2000    // wait for key; write code to RAM[0x2000]
KEYIN  5           // wait for key; write code to RAM[R5]
```

In GUI mode the instruction blocks until a key is pressed. In headless mode it prompts stdin.

---

### `HALT`
Stop execution immediately. Takes no operands.

```assembly
HALT
```

---

## GPU Instructions

GPU instructions delegate to the GPU unit. Operands may be registers or immediates. If no GPU is attached the instructions are silently ignored.

Buffer selection (which of the two 32×32 buffers is drawn to vs. displayed) is controlled via the `setGPUBuffer()` and `getGPUBuffer()` MCL built-in functions — see [GPU_FUNCTIONS.md](../GPU_FUNCTIONS.md).

---

### `DRLINE  x1, y1, x2, y2`
Draw a pixel-perfect line from `(x1, y1)` to `(x2, y2)`.

| # | Operand | Range |
|---|---|---|
| 1 | `x1` | 0–31 |
| 2 | `y1` | 0–31 |
| 3 | `x2` | 0–31 |
| 4 | `y2` | 0–31 |

```assembly
DRLINE  i:0, i:0, i:31, i:31   // diagonal line
```

---

### `DRGRD  x, y, width, height`
Fill a rectangular region with **white** (set pixels to 1).

| # | Operand | Range |
|---|---|---|
| 1 | `x` | 0–31 |
| 2 | `y` | 0–31 |
| 3 | `width` | 1–32 |
| 4 | `height` | 1–32 |

```assembly
DRGRD  i:10, i:10, i:5, i:5    // fill 5×5 square at (10,10)
```

---

### `CLRGRID  x, y, width, height`
Clear a rectangular region (set pixels to 0).

| # | Operand | Range |
|---|---|---|
| 1 | `x` | 0–31 |
| 2 | `y` | 0–31 |
| 3 | `width` | 1–32 |
| 4 | `height` | 1–32 |

```assembly
CLRGRID  i:0, i:0, i:32, i:32  // clear entire screen
```

---

### `LDSPR  id, data`
Load a **5×3 sprite** (15 bits) into sprite slot `id`.

| # | Operand | Range / notes |
|---|---|---|
| 1 | `id` | 0–31 (5-bit slot index) |
| 2 | `data` | 15-bit integer; MSB = top-left pixel, row-major |

```assembly
LDSPR  i:1, i:0x7FFF    // load all-white sprite into slot 1
```

Sprite bit layout (5 wide × 3 tall, MSB first):
```
Bit 14 13 12 11 10 | 9 8 7 6 5 | 4 3 2 1 0
Row    0           |    1      |    2
```

---

### `DRSPR  id, x, y`
Draw the sprite in slot `id` at position `(x, y)`.

| # | Operand | Range |
|---|---|---|
| 1 | `id` | 0–31 |
| 2 | `x` | 0–31 |
| 3 | `y` | 0–31 |

```assembly
DRSPR  i:1, i:10, i:10  // draw sprite 1 at (10,10)
```

---

### `LDTXT  id, char_code`
Load a character code into text slot `id`.

| # | Operand | Range / notes |
|---|---|---|
| 1 | `id` | 0–16383 (14-bit slot index) |
| 2 | `char_code` | 0–42 (see KEYIN encoding above) |

```assembly
LDTXT  i:0, i:7    // slot 0 = 'H'
LDTXT  i:1, i:4    // slot 1 = 'E'
```

---

### `DRTXT  id, x, y`
Render the character in text slot `id` using the 5×5 font at `(x, y)`.

| # | Operand | Range |
|---|---|---|
| 1 | `id` | 0–16383 |
| 2 | `x` | 0–31 |
| 3 | `y` | 0–31 |

```assembly
DRTXT  i:0, i:2, i:10   // draw text slot 0 at (2,10)
```

---

### `SCRLBFR  offx, offy`
Scroll the current edit buffer by `(offx, offy)` pixels. Pixels scrolled off the edge are discarded.

| # | Operand | Notes |
|---|---|---|
| 1 | `offx` | Positive = right, negative = left |
| 2 | `offy` | Positive = down, negative = up |

```assembly
SCRLBFR  i:1, i:0    // scroll right by 1
SCRLBFR  i:0, i:-1   // scroll up by 1
```

---

## Instruction Quick-Reference

| Instruction | Operands | Output / effect |
|---|---|---|
| `LOAD` | `src, dst_addr` | `RAM[dst_addr] = src` |
| `READ` | `src_addr, dst_reg` | `dst_reg = RAM[src_addr]` |
| `MVR` | `src, dst_reg` | `dst_reg = src` (no R0 side-effect) |
| `MVM` | `src_addr, dst_addr` | `RAM[dst_addr] = RAM[src_addr]` |
| `ADD` | `A, B` | `R0 = A + B` |
| `SUB` | `A, B` | `R0 = A − B` |
| `MULT` | `A, B` | `R0 = low16(A×B)`, `R1 = high16(A×B)` |
| `DIV` | `A, B` | `R0 = A÷B` (quotient), `R1 = A%B` (remainder) |
| `SHL` | `A, B` | `R0 = A << B` |
| `SHR` | `A, B` | `R0 = A >> B` |
| `SHLR` | `A, B` | `R0 = rotate_left(A, B)` (16-bit) |
| `AND` | `A, B` | `R0 = A & B` |
| `OR` | `A, B` | `R0 = A \| B` |
| `XOR` | `A, B` | `R0 = A ^ B` |
| `NOT` | `A` | `A = ~A` (in-place; R0 unchanged) |
| `JMP` | `target` | `PC = target` |
| `JAL` | `target` | `R2 = PC+1; PC = target` |
| `JZ` | `target, cond` | `if cond==0: PC = target` |
| `JNZ` | `target, cond` | `if cond!=0: PC = target` |
| `JBT` | `target, x, y` | `if x>y: PC = target` (unsigned) |
| `KEYIN` | `addr` | `RAM[addr] = keyboard char code` (blocking) |
| `HALT` | _(none)_ | Stop execution |
| `DRLINE` | `x1, y1, x2, y2` | Draw line on GPU edit buffer |
| `DRGRD` | `x, y, w, h` | Fill rectangle white |
| `CLRGRID` | `x, y, w, h` | Clear rectangle to black |
| `LDSPR` | `id, data` | Load 5×3 sprite into slot |
| `DRSPR` | `id, x, y` | Draw sprite at position |
| `LDTXT` | `id, char_code` | Load character into text slot |
| `DRTXT` | `id, x, y` | Render text character at position |
| `SCRLBFR` | `offx, offy` | Scroll edit buffer |
