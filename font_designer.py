#!/usr/bin/env python3
"""
Font Designer for MCL 3x4 Character Set
Interactive tool to design 3x4 pixel fonts for the MCL virtual machine.
"""

import pygame
import sys

# MCL Character set (same as in GPU)
CHARACTERS = [
    # Letters A-Z (0-25)
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    # Numbers 0-9 (26-35)
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    # Special characters (36-42)
    '!', '?', '+', '-', '*', '.', ','
]

class FontDesigner:
    def __init__(self):
        pygame.init()
        
        # Display settings
        self.cell_size = 80
        self.grid_width = 3
        self.grid_height = 4
        self.padding = 20
        
        # Calculate window size
        grid_pixel_width = self.grid_width * self.cell_size
        grid_pixel_height = self.grid_height * self.cell_size
        self.window_width = grid_pixel_width + (self.padding * 2)
        self.window_height = grid_pixel_height + (self.padding * 3) + 60  # Extra space for text
        
        # Create display
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("MCL 3x4 Font Designer")
        
        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.GRAY = (128, 128, 128)
        self.GREEN = (0, 255, 0)
        self.RED = (255, 0, 0)
        self.BLUE = (0, 0, 255)
        
        # Font for text display
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        # Current state
        self.current_char_index = 0
        self.grid = [[False for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        # Results storage
        self.font_data = {}
        
        self.clock = pygame.time.Clock()
        self.running = True
    
    def get_current_char(self):
        """Get the current character being edited."""
        return CHARACTERS[self.current_char_index]
    
    def grid_to_binary(self):
        """Convert the current grid to a 12-bit integer."""
        binary_value = 0
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                bit_index = row * self.grid_width + col
                if self.grid[row][col]:
                    binary_value |= (1 << bit_index)
        return binary_value
    
    def binary_to_grid(self, binary_value):
        """Convert a 12-bit integer to grid pattern."""
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                bit_index = row * self.grid_width + col
                self.grid[row][col] = bool(binary_value & (1 << bit_index))
    
    def get_cell_at_pos(self, mouse_x, mouse_y):
        """Get grid cell coordinates from mouse position."""
        grid_start_x = self.padding
        grid_start_y = self.padding + 40  # Account for header text
        
        if (grid_start_x <= mouse_x < grid_start_x + self.grid_width * self.cell_size and
            grid_start_y <= mouse_y < grid_start_y + self.grid_height * self.cell_size):
            
            col = (mouse_x - grid_start_x) // self.cell_size
            row = (mouse_y - grid_start_y) // self.cell_size
            
            if 0 <= row < self.grid_height and 0 <= col < self.grid_width:
                return row, col
        return None, None
    
    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    # Save current character and move to next
                    self.save_current_character()
                    self.next_character()
                    
                elif event.key == pygame.K_ESCAPE:
                    # Quit
                    self.running = False
                    
                elif event.key == pygame.K_SPACE:
                    # Clear current grid
                    self.clear_grid()
                    
                elif event.key == pygame.K_BACKSPACE:
                    # Go back to previous character
                    self.previous_character()
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    row, col = self.get_cell_at_pos(event.pos[0], event.pos[1])
                    if row is not None and col is not None:
                        # Toggle the cell
                        self.grid[row][col] = not self.grid[row][col]
    
    def save_current_character(self):
        """Save the current character pattern."""
        char = self.get_current_char()
        binary_data = self.grid_to_binary()
        self.font_data[char] = binary_data
        
        # Print the result
        print(f"{char}: 0b{binary_data:012b}")
    
    def next_character(self):
        """Move to the next character."""
        if self.current_char_index < len(CHARACTERS) - 1:
            self.current_char_index += 1
            self.clear_grid()
        else:
            print("\nAll characters completed!")
            print("\nFinal font data:")
            for char in CHARACTERS:
                if char in self.font_data:
                    print(f"font['{char}'] = 0b{self.font_data[char]:012b}  # {char}")
            self.running = False
    
    def previous_character(self):
        """Move to the previous character."""
        if self.current_char_index > 0:
            self.current_char_index -= 1
            # Load previous character's data if it exists
            char = self.get_current_char()
            if char in self.font_data:
                self.binary_to_grid(self.font_data[char])
            else:
                self.clear_grid()
    
    def clear_grid(self):
        """Clear the current grid."""
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                self.grid[row][col] = False
    
    def draw(self):
        """Draw the interface."""
        self.screen.fill(self.WHITE)
        
        # Draw title and current character
        current_char = self.get_current_char()
        title_text = self.font.render(f"Designing: '{current_char}' ({self.current_char_index + 1}/{len(CHARACTERS)})", True, self.BLACK)
        self.screen.blit(title_text, (self.padding, 10))
        
        # Draw grid
        grid_start_x = self.padding
        grid_start_y = self.padding + 40
        
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                x = grid_start_x + col * self.cell_size
                y = grid_start_y + row * self.cell_size
                
                # Cell rectangle
                rect = pygame.Rect(x, y, self.cell_size, self.cell_size)
                
                # Fill cell based on state
                if self.grid[row][col]:
                    pygame.draw.rect(self.screen, self.BLACK, rect)
                else:
                    pygame.draw.rect(self.screen, self.WHITE, rect)
                
                # Draw border
                pygame.draw.rect(self.screen, self.GRAY, rect, 2)
        
        # Draw bit indices for reference
        for row in range(self.grid_height):
            for col in range(self.grid_width):
                x = grid_start_x + col * self.cell_size + self.cell_size // 2
                y = grid_start_y + row * self.cell_size + self.cell_size // 2
                
                bit_index = row * self.grid_width + col
                text_color = self.WHITE if self.grid[row][col] else self.GRAY
                index_text = self.small_font.render(str(bit_index), True, text_color)
                text_rect = index_text.get_rect(center=(x, y))
                self.screen.blit(index_text, text_rect)
        
        # Draw current binary value
        binary_value = self.grid_to_binary()
        binary_text = f"Binary: 0b{binary_value:012b} (0x{binary_value:03X})"
        binary_surface = self.small_font.render(binary_text, True, self.BLACK)
        self.screen.blit(binary_surface, (self.padding, grid_start_y + self.grid_height * self.cell_size + 10))
        
        # Draw instructions
        instructions = [
            "Click cells to toggle | ENTER: Save & next | SPACE: Clear | BACKSPACE: Previous | ESC: Quit"
        ]
        
        for i, instruction in enumerate(instructions):
            inst_surface = self.small_font.render(instruction, True, self.BLUE)
            self.screen.blit(inst_surface, (self.padding, grid_start_y + self.grid_height * self.cell_size + 35 + i * 20))
        
        pygame.display.flip()
    
    def run(self):
        """Main game loop."""
        print("MCL 3x4 Font Designer")
        print("====================")
        print("Design each character by clicking on the 3x4 grid.")
        print("Press ENTER to save and move to the next character.")
        print("Grid bit layout:")
        print("0  1  2")
        print("3  4  5") 
        print("6  7  8")
        print("9  10 11")
        print()
        
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()

if __name__ == "__main__":
    designer = FontDesigner()
    designer.run()