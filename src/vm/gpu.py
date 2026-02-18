"""MCL Virtual Machine GPU

Dual-buffer GPU with 32x32 display using 32-bit row storage.
Each row is stored as a 32-bit integer where each bit represents a pixel.
"""

import pygame
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import threading
import time


class GPUException(Exception):
    """Base exception for GPU-related errors."""
    pass


@dataclass
class Sprite:
    """Represents a 5x3 sprite (15 bits of data)."""
    id: int
    data: int  # 15 bits of sprite data


@dataclass
class TextChar:
    """Represents a text character in buffer."""
    id: int
    char_code: int  # 6-bit character code


class GPU:
    """MCL Virtual Machine GPU with dual-buffer system."""
    
    def __init__(self, width: int = 32, height: int = 32, scale: int = 16):
        """Initialize GPU with dual-buffer system.
        
        Args:
            width: Display width in pixels (32x32 display)
            height: Display height in pixels (32x32 display)  
            scale: Scaling factor for display window (larger for visibility)
        """
        self.width = width
        self.height = height
        self.scale = scale
        
        # Dual buffer system - each row is a 32-bit integer
        # Buffer 0 and Buffer 1 (32 rows each)
        self.buffer_0 = [0x00000000 for _ in range(32)]
        self.buffer_1 = [0x00000000 for _ in range(32)]
        
        # Buffer control registers
        self.display_buffer_id = 0  # Which buffer is connected to display output
        self.edit_buffer_id = 0     # Which buffer is currently being edited
        
        # Sprite storage (5x3 pixels = 15 bits data + 5 bits address = 20 bits total)
        self.sprites: Dict[int, Sprite] = {}  # Max 32 sprites (5-bit addressing)
        
        # Text storage (6-bit char + 14 bits address = 20 bits total)
        self.text_chars: Dict[int, TextChar] = {}  # Max 16384 text positions
        
        # Font data for 3x4 character rendering
        self.font_data = self._create_3x4_font()
        
        # Pygame display
        self.pygame_initialized = False
        self.screen = None
        self.clock = None
        self.running = False
        
        # GPU statistics
        self.frame_count = 0
        self.command_count = 0
        
        # CPU reference for input handling
        self._cpu = None
        
        # UI Controls
        self.cpu_paused = False 
        self.ui_font = None
        self.slider_rect = None
        self.play_button_rect = None
        self.pause_button_rect = None
        self.slider_dragging = False
        self.slider_position = 0.1  # Linear position [0,1], default middle
        self.highspeed_mode = False  # New: High Speed toggle state

        
        # UI dimensions
        self.ui_height = 60  # Space for controls above input area
        
        # GPU Control Register (32-bit)
        # Bit 0: Display Buffer ID (0 or 1)
        # Bit 1: Edit Buffer ID (0 or 1)
        # Bits 2-31: Reserved for future use
        self.gpu_register = 0x00000000
    
    def set_cpu_reference(self, cpu) -> None:
        """Set reference to CPU for input handling."""
        self._cpu = cpu
    
    def initialize_display(self) -> bool:
        """Initialize pygame display with input area."""
        try:
            pygame.init()
            
            # Main display + UI controls + input area
            display_height = self.height * self.scale
            input_area_height = 32
            total_height = display_height + self.ui_height + input_area_height
            
            self.screen = pygame.display.set_mode(
                (self.width * self.scale, total_height)
            )
            pygame.display.set_caption("MCL VM Display")
            self.clock = pygame.time.Clock()
            
            # Initialize fonts for text and UI
            pygame.font.init()
            self.ui_font = pygame.font.Font(None, 24)
            self.input_font = pygame.font.Font(None, 24)
            
            self.pygame_initialized = True
            self.running = True
            return True
        except Exception as e:
            print(f"Failed to initialize display: {e}")
            return False
    
    def shutdown_display(self) -> None:
        """Shutdown pygame display."""
        if self.pygame_initialized:
            pygame.quit()
            self.pygame_initialized = False
            self.running = False
    
    def get_edit_buffer(self) -> List[int]:
        """Get the currently active edit buffer."""
        self._update_buffers_from_register()  # Always sync from register
        return self.buffer_0 if self.edit_buffer_id == 0 else self.buffer_1
    
    def get_display_buffer(self) -> List[int]:
        """Get the currently active display buffer."""
        self._update_buffers_from_register()  # Always sync from register
        return self.buffer_0 if self.display_buffer_id == 0 else self.buffer_1
    
    def _update_buffers_from_register(self) -> None:
        """Update buffer IDs from GPU register bits."""
        self.display_buffer_id = self.gpu_register & 0x00000001
        self.edit_buffer_id = (self.gpu_register & 0x00000002) >> 1
    
    def execute_command(self, opcode: str, operands: List[Any]) -> None:
        """Execute a GPU command.
        
        Args:
            opcode: GPU command opcode
            operands: Command operands from registers
        """
        self.command_count += 1
        
        if opcode == 'DRLINE':
            self._draw_line(operands)
        elif opcode == 'DRGRD':
            self._fill_grid(operands)
        elif opcode == 'CLRGRID':
            self._clear_grid(operands)
        elif opcode == 'LDSPR':
            self._load_sprite(operands)
        elif opcode == 'DRSPR':
            self._draw_sprite(operands)
        elif opcode == 'LDTXT':
            self._load_text(operands)
        elif opcode == 'DRTXT':
            self._draw_text(operands)
        elif opcode == 'SCRLBFR':
            self._scroll_buffer(operands)
        else:
            raise GPUException(f"Unknown GPU command: {opcode}")
    
    def _draw_line(self, operands: List[Any]) -> None:
        """Draw a line using row-by-row algorithm.
        
        Args:
            operands: [x1, y1, x2, y2, color] 
        """
        if len(operands) < 4:
            return
        
        x1, y1, x2, y2 = operands[:4]
        
        # Clamp coordinates to 32x32 display
        x1 = max(0, min(31, x1))
        y1 = max(0, min(31, y1))
        x2 = max(0, min(31, x2))
        y2 = max(0, min(31, y2))
        
        # Setup phase (once per line)
        y_min = min(y1, y2)
        y_max = max(y1, y2)
        x_at_y_min = x1 if y1 < y2 else x2
        x_at_y_max = x2 if y1 < y2 else x1
        
        dx = x_at_y_max - x_at_y_min
        dy = y_max - y_min

        # x never goes outside this range for any point on the line
        x_bound_lo = min(x_at_y_min, x_at_y_max)
        x_bound_hi = max(x_at_y_min, x_at_y_max)

        if dy == 0:
            # Horizontal line
            y_scan = y_min
            if 0 <= y_scan < 32:
                x_start = min(x1, x2)
                x_end = max(x1, x2)
                self._fill_row_range(y_scan, x_start, x_end)
            return
        
        # Per scanline: fill the x span the line covers between this row and the next
        buffer = self.get_edit_buffer()
        for y_scan in range(y_min, y_max + 1):
            y_offset = y_scan - y_min
            
            x_numerator = dx * y_offset
            x_position = x_at_y_min + (x_numerator // dy)
            x_next = x_at_y_min + ((x_numerator + dx) // dy)
            
            # Ensure proper ordering
            x_start = min(x_position, x_next)
            x_end = max(x_position, x_next)

            # Clamp to the line's own x extent (prevents overshoot past endpoints)
            x_start = max(x_bound_lo, x_start)
            x_end = min(x_bound_hi, x_end)
            
            # Clamp to screen bounds
            x_start = max(0, min(31, x_start))
            x_end = max(0, min(31, x_end))
            
            # Fill pixels from x_start to x_end
            self._fill_row_range(y_scan, x_start, x_end)
    
    def _fill_row_range(self, y: int, x_start: int, x_end: int) -> None:
        """Fill a range of pixels in a row using bit manipulation."""
        if y < 0 or y >= 32:
            return
            
        buffer = self.get_edit_buffer()
        
        # Create mask for the range
        width = x_end - x_start + 1
        if width <= 0:
            return

        # Create mask: 'width' consecutive 1-bits placed at x_start..x_end
        # (x=0 is MSB / bit 31, x=31 is LSB / bit 0)
        mask = ((1 << width) - 1) << (32 - x_start - width)
        
        # OR the mask into the buffer
        buffer[y] |= mask
    
    def _fill_grid(self, operands: List[Any]) -> None:
        """Fill a rectangular area by setting bits to 1.
        
        Args:
            operands: [x, y, width, height]
        """
        if len(operands) < 4:
            return
        
        x, y, width, height = operands[:4]
        
        # Clamp to screen bounds
        x = max(0, min(31, x))
        y = max(0, min(31, y))
        width = max(0, min(32 - x, width))
        height = max(0, min(32 - y, height))
        
        buffer = self.get_edit_buffer()
        
        # Fill each row in the rectangle
        for row in range(y, min(32, y + height)):
            if width > 0:
                # Create mask for this row
                mask = (0xFFFFFFFF >> (32 - width)) << (32 - x - width)
                buffer[row] |= mask
    
    def _clear_grid(self, operands: List[Any]) -> None:
        """Clear a rectangular area by setting bits to 0.
        
        Args:
            operands: [x, y, width, height] 
        """
        if len(operands) < 4:
            return
        
        x, y, width, height = operands[:4]
        
        # Clamp to screen bounds
        x = max(0, min(31, x))
        y = max(0, min(31, y))
        width = max(0, min(32 - x, width))
        height = max(0, min(32 - y, height))
        
        buffer = self.get_edit_buffer()
        
        # Clear each row in the rectangle
        for row in range(y, min(32, y + height)):
            if width > 0:
                # Create inverse mask for this row 
                mask = (0xFFFFFFFF >> (32 - width)) << (32 - x - width)
                buffer[row] &= ~mask  # Clear bits with AND NOT
    
    def _load_sprite(self, operands: List[Any]) -> None:
        """Load sprite data (5x3 pixels = 15 bits).
        
        Args:
            operands: [id, data] where data contains 15 bits of sprite + 5 bits address
        """
        if len(operands) < 2:
            return
        
        sprite_id, data = operands[:2]
        
        # Extract sprite ID from address bits (lower 5 bits)
        sprite_id = sprite_id & 0x1F  # 5-bit sprite ID (0-31)
        
        # Extract sprite data (15 bits for 5x3 sprite)
        sprite_data = data & 0x7FFF  # 15 bits of sprite data
        
        self.sprites[sprite_id] = Sprite(id=sprite_id, data=sprite_data)
    
    def _draw_sprite(self, operands: List[Any]) -> None:
        """Draw a 5x3 sprite on the display.
        
        Args:
            operands: [sprite_id, x, y]
        """
        if len(operands) < 3:
            return
        
        sprite_id, x, y = operands[:3]
        sprite_id = sprite_id & 0x1F  # 5-bit sprite ID
        
        if sprite_id not in self.sprites:
            return
        
        sprite = self.sprites[sprite_id]
        
        # Clamp position to screen
        x = max(0, min(31 - 4, x))  # 5 pixels wide, so max x = 27
        y = max(0, min(31 - 2, y))  # 3 pixels tall, so max y = 29
        
        buffer = self.get_edit_buffer()
        
        # Draw 5x3 sprite from 15-bit data
        sprite_data = sprite.data
        
        for row in range(3):  # 3 rows
            for col in range(5):  # 5 columns
                bit_index = row * 5 + col
                if sprite_data & (1 << bit_index):
                    # Set pixel at (x + col, y + row)
                    pixel_x = x + col
                    pixel_y = y + row
                    
                    if 0 <= pixel_x < 32 and 0 <= pixel_y < 32:
                        buffer[pixel_y] |= (1 << (31 - pixel_x))
    
    def _load_text(self, operands: List[Any]) -> None:
        """Load text character (6-bit char + 14-bit address).
        
        Args:
            operands: [text_id, data] where data contains 6-bit char + 14-bit address
        """
        if len(operands) < 2:
            return
        
        text_id, data = operands[:2]
        
        # Extract address (lower 14 bits)
        address = text_id & 0x3FFF  # 14-bit address (0-16383)
        
        # Extract character code (6 bits)
        char_code = data & 0x3F  # 6-bit character code
        
        self.text_chars[address] = TextChar(id=address, char_code=char_code)
    
    def _draw_text(self, operands: List[Any]) -> None:
        """Draw text character using 5x5 font.
        
        Args:
            operands: [text_id, x, y]
        """
        if len(operands) < 3:
            return
        
        text_id, x, y = operands[:3]
        
        # Find character in text buffer
        if text_id not in self.text_chars:
            return
        
        text_char = self.text_chars[text_id]
        char_code = text_char.char_code
        
        # Clamp position for 3x4 character
        x = max(0, min(31 - 2, x))  # 3 pixels wide
        y = max(0, min(31 - 3, y))  # 4 pixels tall
        
        # Decode 6-bit character to actual character
        actual_char = self._decode_6bit_char(char_code)
        
        # Get character pattern from font
        char_pattern = self.font_data.get(actual_char, self.font_data.get('?', 0))
        
        buffer = self.get_edit_buffer()
        
        # Render 3x4 character
        for row in range(4):
            for col in range(3):
                bit_index = row * 3 + col
                if char_pattern & (1 << bit_index):
                    pixel_x = x + col
                    pixel_y = y + row
                    
                    if 0 <= pixel_x < 32 and 0 <= pixel_y < 32:
                        buffer[pixel_y] |= (1 << (31 - pixel_x))
    
    def _scroll_buffer(self, operands: List[Any]) -> None:
        """Scroll the display buffer using bit shifts.
        
        Args:
            operands: [offx, offy] - offset amounts for scrolling
        """
        if len(operands) < 2:
            return
        
        offx, offy = operands[:2]
        
        buffer = self.get_edit_buffer()
        
        # Handle vertical scrolling (offy)
        if offy != 0:
            new_buffer = [0x00000000 for _ in range(32)]
            
            for row in range(32):
                new_row = row + offy
                if 0 <= new_row < 32:
                    new_buffer[row] = buffer[new_row]
            
            buffer[:] = new_buffer
        
        # Handle horizontal scrolling (offx)  
        if offx != 0:
            for row in range(32):
                if offx > 0:
                    # Scroll right - shift bits left
                    buffer[row] = (buffer[row] << offx) & 0xFFFFFFFF
                else:
                    # Scroll left - shift bits right
                    buffer[row] = buffer[row] >> (-offx)
    
    def _encode_6bit_char(self, char: str) -> int:
        """Encode character to 6-bit code.
        
        Character set: A-Z (0-25), 0-9 (26-35), !?+-*., (36-42)
        """
        if 'A' <= char <= 'Z':
            return ord(char) - ord('A')  # 0-25
        elif '0' <= char <= '9':
            return ord(char) - ord('0') + 26  # 26-35
        elif char in "!?+-*.,":
            special_chars = "!?+-*.,"
            return special_chars.index(char) + 36  # 36-42
        else:
            return 37  # Default to '?' for unknown characters
    
    def _decode_6bit_char(self, code: int) -> str:
        """Decode 6-bit code to character."""
        code = code & 0x3F  # Ensure 6-bit range
        
        if 0 <= code <= 25:
            return chr(ord('A') + code)  # A-Z
        elif 26 <= code <= 35:
            return chr(ord('0') + (code - 26))  # 0-9
        elif 36 <= code <= 42:
            special_chars = "!?+-*.,"
            return special_chars[code - 36]
        else:
            return '?'  # Unknown code
    
    def _create_3x4_font(self) -> Dict[str, int]:
        """Create a 3x4 font with 12-bit patterns."""
        font = {}
        
        # Letters A-Z (3x4 patterns)
        font['A'] = 0b101111101111  # A
        font['B'] = 0b111101111011  # B
        font['C'] = 0b111001001111  # C
        font['D'] = 0b011101101011  # D
        font['E'] = 0b111001011111  # E
        font['F'] = 0b001011001111  # F
        font['G'] = 0b111101001111  # G
        font['H'] = 0b101101111101  # H
        font['I'] = 0b111010010111  # I
        font['J'] = 0b011010010111  # J
        font['K'] = 0b101011011101  # K
        font['L'] = 0b111001001001  # L
        font['M'] = 0b101111111101  # M
        font['N'] = 0b101101101111  # N
        font['O'] = 0b111101101111  # O
        font['P'] = 0b001111101111  # P
        font['Q'] = 0b100111101111  # Q
        font['R'] = 0b101011111111  # R
        font['S'] = 0b111110001111  # S
        font['T'] = 0b010010010111  # T
        font['U'] = 0b111101101101  # U
        font['V'] = 0b010101101101  # V
        font['W'] = 0b111111111101  # W
        font['X'] = 0b101110011101  # X
        font['Y'] = 0b010010111101  # Y
        font['Z'] = 0b111001110111  # Z
        font['0'] = 0b111101101110  # 0
        font['1'] = 0b010010010011  # 1
        font['2'] = 0b111011100111  # 2
        font['3'] = 0b111100110111  # 3
        font['4'] = 0b100111101101  # 4
        font['5'] = 0b111100011111  # 5
        font['6'] = 0b111111001111  # 6
        font['7'] = 0b100110100111  # 7
        font['8'] = 0b111101111111  # 8
        font['9'] = 0b111100111111  # 9
        font['!'] = 0b010000010010  # !
        font['?'] = 0b010000100111  # ?
        font['+'] = 0b000010111010  # +
        font['-'] = 0b000000111000  # -
        font['*'] = 0b000000010000  # *
        font['.'] = 0b010000000000  # .
        font[','] = 0b011010000000  # ,

        
        return font
    

    
    def update_display(self) -> bool:
        """Update the pygame display using bit-based buffer.
        
        Returns:
            True if display was updated successfully, False otherwise
        """
        if not self.pygame_initialized:
            return False
        
        if not hasattr(self, 'screen') or self.screen is None:
            return False
        
        try:
            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return False
                elif event.type == pygame.KEYDOWN and self._cpu:
                    self._handle_keyboard_input(event)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_mouse_input(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self._handle_mouse_release(event)
                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(event)
            
            # Get display buffer
            display_buffer = self.get_display_buffer()
            
            # Convert bit buffer to pygame surface (main display area)
            for y in range(32):
                row_data = display_buffer[y]
                
                for x in range(32):
                    # Extract bit for this pixel (MSB = leftmost pixel)
                    pixel_bit = (row_data >> (31 - x)) & 1
                    
                    # Set color based on bit (1 = white, 0 = black)
                    color = (255, 255, 255) if pixel_bit else (0, 0, 0)
                    
                    # Draw scaled pixel
                    rect = pygame.Rect(
                        x * self.scale, 
                        y * self.scale, 
                        self.scale, 
                        self.scale
                    )
                    pygame.draw.rect(self.screen, color, rect)
            
            # Draw UI controls between main display and input box
            self._draw_ui_controls()
            
            # Draw input text box below controls
            self._draw_input_box()
            
            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS
            self.frame_count += 1
            
            return True
            
        except Exception as e:
            print(f"Display update error: {e}")
            return False
    
    def _draw_input_box(self) -> None:
        """Draw the input text box below the main display."""
        if not self.pygame_initialized or not self._cpu:
            return
            
        try:
            # Input box area (below the main 32x32 display)
            input_y = self.height * self.scale + self.ui_height
            input_height = 32
            
            # Clear input area with dark background
            input_rect = pygame.Rect(0, input_y, self.width * self.scale, input_height)
            pygame.draw.rect(self.screen, (20, 20, 20), input_rect)
            
            # Draw border around input box
            pygame.draw.rect(self.screen, (100, 100, 100), input_rect, 2)
            
            # Get input buffer content between read and write positions
            input_text = ""
            if hasattr(self._cpu, 'input_buffer') and hasattr(self._cpu, 'input_read_pos') and hasattr(self._cpu, 'input_write_pos'):
                read_pos = self._cpu.input_read_pos
                write_pos = self._cpu.input_write_pos
                
                # Build display string from buffer
                pos = read_pos
                while pos != write_pos:
                    char_code = self._cpu.input_buffer[pos]
                    # Convert 6-bit code to character
                    if 0 <= char_code <= 25:  # A-Z
                        input_text += chr(ord('A') + char_code)
                    elif 26 <= char_code <= 35:  # 0-9
                        input_text += chr(ord('0') + (char_code - 26))
                    elif 36 <= char_code <= 42:  # Special chars
                        special_chars = "!?+-*.,"
                        input_text += special_chars[char_code - 36]
                    else:
                        input_text += "?"
                    
                    pos = (pos + 1) % len(self._cpu.input_buffer)
            
            # Render text with cursor
            cursor_text = input_text + "|"  # Simple blinking cursor
            if hasattr(self, 'input_font'):
                text_surface = self.input_font.render(cursor_text, True, (255, 255, 255))
                self.screen.blit(text_surface, (5, input_y + 5))
                
        except Exception as e:
            # Silently handle input box drawing errors
            pass
    
    def _handle_keyboard_input(self, event) -> None:
        """Handle keyboard input events and add to CPU input buffer."""
        if not self._cpu:
            return
            
        try:
            # Get the pressed key
            key_name = pygame.key.name(event.key).upper()
            
            # Handle special keys
            if event.key == pygame.K_BACKSPACE:
                if hasattr(self._cpu, 'backspace_input'):
                    self._cpu.backspace_input()
                return
            
            # Convert key to 6-bit character code
            char_code = None
            if len(key_name) == 1:
                char = key_name[0]
                if char.isalpha():
                    char_code = ord(char) - ord('A')  # A-Z = 0-25
                elif char.isdigit():
                    char_code = ord(char) - ord('0') + 26  # 0-9 = 26-35
                elif char in "!?+-*.,":
                    special_chars = "!?+-*.,"
                    char_code = special_chars.index(char) + 36  # Special = 36-42
            
            # Add to input buffer if valid
            if char_code is not None and hasattr(self._cpu, 'add_input_char'):
                self._cpu.add_input_char(char_code)
                
        except Exception as e:
            # Silently handle keyboard input errors
            pass
    
    def _draw_ui_controls(self) -> None:
        """Draw UI controls (speed slider and pause/play buttons)."""
        if not self.pygame_initialized or not self.ui_font:
            return
        try:
            # Control area starts after main display
            control_y = self.height * self.scale
            control_height = self.ui_height
            # Fill control area background
            control_rect = pygame.Rect(0, control_y, self.width * self.scale, control_height)
            pygame.draw.rect(self.screen, (64, 64, 64), control_rect)

            # Speed label with appropriate units
            cpu_speed = 1.0
            if self._cpu and hasattr(self._cpu, 'vm') and hasattr(self._cpu.vm, 'cpu_speed'):
                cpu_speed = self._cpu.vm.cpu_speed
            # Always show the correct unit and value, even at exact boundaries
            if cpu_speed >= 1_000_000:
                value = cpu_speed / 1_000_000
                unit = "MHz"
            elif cpu_speed >= 1_000:
                value = cpu_speed / 1_000
                unit = "kHz"
            elif cpu_speed >= 1:
                value = cpu_speed
                unit = "Hz"
            else:
                value = cpu_speed
                unit = "Hz"
            # Use more decimal places for MHz/kHz, less for Hz
            if unit == "MHz":
                speed_text = f"Speed: {value:.3f} {unit}"
            elif unit == "kHz":
                speed_text = f"Speed: {value:.2f} {unit}"
            elif value >= 1:
                speed_text = f"Speed: {value:.1f} {unit}"
            else:
                speed_text = f"Speed: {value:.2f} {unit}"
            speed_label = self.ui_font.render(speed_text, True, (255, 255, 255))
            self.screen.blit(speed_label, (10, control_y + 5))


            # Speed slider (visual position based on self.slider_position)
            slider_x = 10
            slider_y = control_y + 30
            slider_width = 200
            slider_height = 20
            self.slider_rect = pygame.Rect(slider_x, slider_y, slider_width, slider_height)
            slider_color = (80, 80, 80) if self.highspeed_mode else (128, 128, 128)
            pygame.draw.rect(self.screen, slider_color, self.slider_rect)

            # Slider handle (positioned by self.slider_position)
            handle_x = slider_x + int(self.slider_position * (slider_width - 10))
            handle_rect = pygame.Rect(handle_x, slider_y - 2, 10, slider_height + 4)
            handle_color = (180, 180, 180) if self.highspeed_mode else (255, 255, 255)
            pygame.draw.rect(self.screen, handle_color, handle_rect)

            # High Speed checkbox
            checkbox_x = slider_x + slider_width + 20
            checkbox_y = slider_y
            checkbox_size = 20
            self.highspeed_checkbox_rect = pygame.Rect(checkbox_x, checkbox_y, checkbox_size, checkbox_size)
            pygame.draw.rect(self.screen, (200, 200, 200), self.highspeed_checkbox_rect, 2)
            if self.highspeed_mode:
                # Draw checkmark
                pygame.draw.line(self.screen, (0, 255, 0), (checkbox_x+4, checkbox_y+10), (checkbox_x+9, checkbox_y+16), 3)
                pygame.draw.line(self.screen, (0, 255, 0), (checkbox_x+9, checkbox_y+16), (checkbox_x+16, checkbox_y+4), 3)
            # Label
            hs_label = self.ui_font.render("High Speed", True, (255,255,255))
            self.screen.blit(hs_label, (checkbox_x + checkbox_size + 8, checkbox_y - 2))

            # Pause/Play buttons
            button_x = checkbox_x + checkbox_size + 120
            button_y = control_y + 10
            button_size = 40
            self.play_button_rect = pygame.Rect(button_x, button_y, button_size, button_size)
            play_color = (0, 255, 0) if self.cpu_paused else (64, 128, 64)
            pygame.draw.rect(self.screen, play_color, self.play_button_rect)
            if self.cpu_paused:
                triangle_points = [
                    (button_x + 10, button_y + 10),
                    (button_x + 30, button_y + 20),
                    (button_x + 10, button_y + 30)
                ]
                pygame.draw.polygon(self.screen, (0, 0, 0), triangle_points)
            pause_x = button_x + button_size + 10
            self.pause_button_rect = pygame.Rect(pause_x, button_y, button_size, button_size)
            pause_color = (255, 128, 0) if not self.cpu_paused else (128, 64, 0)
            pygame.draw.rect(self.screen, pause_color, self.pause_button_rect)
            if not self.cpu_paused:
                pygame.draw.rect(self.screen, (0, 0, 0), (pause_x + 10, button_y + 8, 6, 24))
                pygame.draw.rect(self.screen, (0, 0, 0), (pause_x + 24, button_y + 8, 6, 24))
        except Exception as e:
            # Silently handle UI drawing errors
            pass
    
    def _handle_mouse_input(self, event) -> None:
        """Handle mouse button press events."""
        if not self.pygame_initialized:
            return
        
        mouse_x, mouse_y = event.pos
        
        try:

            # Check highspeed checkbox
            if hasattr(self, 'highspeed_checkbox_rect') and self.highspeed_checkbox_rect.collidepoint(mouse_x, mouse_y):
                self.highspeed_mode = not self.highspeed_mode
                # Inform VM if possible
                if self._cpu and hasattr(self._cpu, 'vm'):
                    self._cpu.vm.set_highspeed_mode(self.highspeed_mode)
                return

            # Check slider interaction (only if not highspeed)
            if not self.highspeed_mode and self.slider_rect and self.slider_rect.collidepoint(mouse_x, mouse_y):
                self.slider_dragging = True
                self._update_slider_from_mouse(mouse_x)
            
            # Check play button
            if self.play_button_rect and self.play_button_rect.collidepoint(mouse_x, mouse_y):
                if self.cpu_paused:
                    self.cpu_paused = False
                    if self._cpu and hasattr(self._cpu, 'vm'):
                        self._cpu.vm.resume()
            
            # Check pause button
            if self.pause_button_rect and self.pause_button_rect.collidepoint(mouse_x, mouse_y):
                if not self.cpu_paused:
                    self.cpu_paused = True
                    if self._cpu and hasattr(self._cpu, 'vm'):
                        self._cpu.vm.pause()
                        
        except Exception as e:
            # Silently handle mouse input errors
            pass
    
    def _handle_mouse_release(self, event) -> None:
        """Handle mouse button release events."""
        self.slider_dragging = False
    
    def _handle_mouse_motion(self, event) -> None:
        """Handle mouse motion events for slider dragging."""
        if self.slider_dragging and self.slider_rect:
            mouse_x, mouse_y = event.pos
            self._update_slider_from_mouse(mouse_x)
    
    def _update_slider_from_mouse(self, mouse_x: int) -> None:
        """Update slider position and CPU speed based on mouse position."""
        if not self.slider_rect:
            return
        # Calculate position relative to slider
        relative_x = mouse_x - self.slider_rect.x
        relative_x = max(0, min(self.slider_rect.width - 10, relative_x))
        # Linear position [0,1]
        self.slider_position = relative_x / (self.slider_rect.width - 10)
            # Exponential mapping: 0.5 * (10 ** (4.477 * ratio)) gives range 0.5 to 15000
        import math
        new_speed = 0.5 * (10 ** (math.log10(60000) * self.slider_position))
        # Update VM CPU speed if available (only if not highspeed)
        if not self.highspeed_mode and self._cpu and hasattr(self._cpu, 'vm'):
            self._cpu.vm.set_cpu_speed(new_speed)
    
    def get_state(self) -> Dict[str, Any]:
        """Get GPU state for debugging."""
        return {
            'display_size': (self.width, self.height),
            'sprites': len(self.sprites),
            'frame_count': self.frame_count,
            'command_count': self.command_count,
            'pygame_initialized': self.pygame_initialized,
            'running': self.running
        }
    
    def capture_frame(self) -> List[int]:
        """Capture the current display buffer."""
        return self.get_display_buffer().copy()
    
    def set_gpu_register(self, value: int) -> None:
        """Set GPU control register and update buffer settings."""
        self.gpu_register = value & 0xFFFFFFFF
        self._update_buffers_from_register()
    
    def get_gpu_register(self) -> int:
        """Get current GPU control register value."""
        return self.gpu_register
    
    def set_pixel(self, x: int, y: int, value: int) -> None:
        """Set a single pixel bit."""
        if 0 <= x < 32 and 0 <= y < 32:
            buffer = self.get_edit_buffer()
            if value:
                buffer[y] |= (1 << (31 - x))  # Set bit
            else:
                buffer[y] &= ~(1 << (31 - x))  # Clear bit