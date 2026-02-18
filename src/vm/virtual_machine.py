"""MCL Virtual Machine

Main virtual machine that coordinates CPU, memory, and GPU components.
"""

from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import threading
import time
import sys

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from .cpu import CPU, CPUState
    from .memory import Memory
    from .gpu import GPU
    from .assembly_loader import load_assembly_file, load_assembly_string
except ImportError:
    from vm.cpu import CPU, CPUState
    from vm.memory import Memory
    from vm.gpu import GPU
    from vm.assembly_loader import load_assembly_file, load_assembly_string


class VMException(Exception):
    """Base exception for virtual machine errors."""
    pass


class VirtualMachine:
    """MCL Virtual Machine - coordinates all components."""
    
    def __init__(self, 
                 ram_size: int = 0x8000,
                 rom_size: int = 0x4000,
                 num_registers: int = 32,
                 display_width: int = 32,
                 display_height: int = 32,
                 enable_gpu: bool = True):
        """Initialize virtual machine.
        
        Args:
            ram_size: Size of RAM in 16-bit words (default 32KB)
            rom_size: Size of ROM in 16-bit words (default 16KB)
            num_registers: Number of CPU registers (16-bit each)
            display_width: GPU display width (32x32 pixels)
            display_height: GPU display height (32x32 pixels)
            enable_gpu: Whether to enable GPU
        """
        # Initialize components
        self.memory = Memory(ram_size, rom_size)
        self.gpu = GPU(display_width, display_height) if enable_gpu else None
        self.cpu = CPU(self.memory, self.gpu, num_registers)
        
        # Set GPU-CPU reference for input display
        if self.gpu:
            self.gpu.set_cpu_reference(self.cpu)
            
        # Set VM reference in CPU for GPU callbacks
        self.cpu.vm = self
        
        # VM state
        self.running = False
        self.paused = True  # Start paused by default
        self.execution_thread: Optional[threading.Thread] = None
        
        # Debugging
        self.breakpoints: set[int] = set()
        self.step_mode = False
        self.debug_callbacks: List[Callable] = []
        
        # CPU speed control
        self.cpu_speed = 1.0  # Instructions per second (0.1 to 1000.0)
        self.last_execution_time = 0
        self.highspeed_mode = True  # Default: run as fast as possible
        
        # Statistics
        self.start_time: Optional[float] = None
        self.execution_time = 0.0
    
    def load_program(self, filename: str) -> None:
        """Load a program from assembly file.
        
        Args:
            filename: Path to assembly file
        """
        try:
            instructions, labels = load_assembly_file(filename)
            # self.reset()
            self.memory.load_program(instructions, labels)
            self.cpu.set_labels(self.memory.labels)
            # Start execution at PC=0 (initialization code)
            # The initialization code will JMP to func_main
            self.cpu.pc = 0
        except Exception as e:
            raise VMException(f"Failed to load program '{filename}': {e}")
    
    def load_program_string(self, assembly_code: str) -> None:
        """Load a program from assembly string.
        
        Args:
            assembly_code: Assembly code as string
        """
        try:
            # self.reset()
            instructions, labels = load_assembly_string(assembly_code)
            self.memory.load_program(instructions, labels)
            self.cpu.set_labels(self.memory.labels)

            # Start execution at PC=0 (initialization code)
            # The initialization code will JMP to func_main
            self.cpu.pc = 0
        except Exception as e:
            raise VMException(f"Failed to load program: {e}")
    
    def reset(self) -> None:
        """Reset VM to initial state."""
        self.stop()
        self.cpu.reset()
        self.memory.clear_ram()
        
        if self.gpu:
            # Clear GPU state
            self.gpu._clear_grid([0])
        
        self.execution_time = 0.0
    
    def start(self, max_cycles: Optional[int] = None) -> None:
        """Start VM execution.
        
        Args:
            max_cycles: Maximum cycles to execute (None for unlimited)
        """
        if self.running:
            return
        
        self.running = True
        # Keep initial paused state (starts paused by default)
        self.start_time = time.time()
        
        # Initialize GPU display if enabled
        if self.gpu and not self.gpu.pygame_initialized:
            success = self.gpu.initialize_display()
            if not success:
                print("Failed to initialize display")
                return
        
        # Run execution loop directly (single-threaded for pygame compatibility)
        self._execution_loop(max_cycles)
        
        # Keep display open for a few seconds after program completion
        if self.gpu and self.gpu.pygame_initialized:
            self._keep_display_open()
    
    def stop(self) -> None:
        """Stop VM execution."""
        self.running = False
        self.paused = False
        
        if self.execution_thread and self.execution_thread.is_alive():
            self.execution_thread.join(timeout=1.0)
        
        if self.start_time:
            self.execution_time += time.time() - self.start_time
            self.start_time = None
    
    def pause(self) -> None:
        """Pause VM execution."""
        if self.running:
            self.paused = True
    
    def set_highspeed_mode(self, enabled: bool) -> None:
        """Enable or disable high speed mode (disables timing logic)."""
        self.highspeed_mode = enabled
    
    def resume(self) -> None:
        """Resume VM execution."""
        if self.running and self.paused:
            self.paused = False
    
    def set_cpu_speed(self, speed: float) -> None:
        """Set CPU execution speed in instructions per second.
        
        Args:
            speed: Instructions per second (0.1 to 15000.0+)
        """
        self.cpu_speed = max(0.1, speed)
    
    def step(self) -> bool:
        """Execute one instruction.
        
        Returns:
            True if instruction was executed, False if VM is halted
        """
        if not self.running:
            self.cpu.state = CPUState.RUNNING
        
        # Check breakpoints
        if self.cpu.pc in self.breakpoints:
            self.cpu.state = CPUState.BREAKPOINT
            self._trigger_debug_callbacks()
            return False
        
        success = self.cpu.step()
        
        self._trigger_debug_callbacks()
        
        return success
    
    def _execution_loop(self, max_cycles: Optional[int]) -> None:
        """Main execution loop with integrated display updates."""
        self.cpu.state = CPUState.RUNNING
        cycles = 0
        last_display_time = time.time()
        
        try:
            while self.running and self.cpu.state == CPUState.RUNNING:
                current_time = time.time()
                
                # Always update display at 60 FPS regardless of pause state
                if current_time - last_display_time >= 0.016:  # ~60 FPS
                    if self.gpu and self.gpu.pygame_initialized:
                        if not self.gpu.update_display():
                            self.running = False
                            break
                    last_display_time = current_time
                
                # Handle pause (CPU execution paused, but display continues)
                if self.paused:
                    pass  # Removed sleep to prevent busy waiting
                    continue
                
                if not self.running:
                    break
                
                # Check cycle limit
                if max_cycles and cycles >= max_cycles:
                    self.cpu.state = CPUState.STOPPED
                    self.cpu.halt_reason = "Max cycles reached"
                    break
                
                # Execute instruction with speed control
                should_execute = True
                if not getattr(self, 'highspeed_mode', False):
                    elapsed = current_time - self.last_execution_time
                    target_delay = 1 / self.cpu_speed
                    should_execute = elapsed >= target_delay
                # In highspeed mode, always execute as fast as possible
                if should_execute:
                    if not getattr(self, 'highspeed_mode', False) and self.cpu_speed < 500.0:
                        # Verbose execution log: show PC, instruction, operands, and register values
                        pc = self.cpu.pc
                        instr = self.memory.rom[pc] if hasattr(self.memory, 'rom') and pc < len(self.memory.rom) else None
                        if instr:
                            op = getattr(instr, 'opcode', None)
                            ops = getattr(instr, 'operands', [])
                            # Build operand display info for alignment
                            op_strs = []
                            val_strs = []
                            # First, collect display strings and value strings for each operand
                            for operand in ops:
                                try:
                                    val = self.cpu._get_operand_value(operand)
                                except Exception:
                                    val = 'ERR'
                                # Determine operand display string and value string
                                if isinstance(operand, str) and operand.startswith('i:'):
                                    seg = operand[2:]
                                    is_number = False
                                    try:
                                        int(seg, 0)
                                        is_number = True
                                    except Exception:
                                        is_number = False
                                    if is_number:
                                        op_disp = str(operand)
                                        val_disp = ''
                                    else:
                                        op_disp = str(operand)
                                        val_disp = f'={val}'
                                elif isinstance(operand, int):
                                    op_disp = str(operand)
                                    val_disp = ''
                                elif isinstance(operand, str) and hasattr(self.memory, 'labels') and operand in self.memory.labels:
                                    # Label operand
                                    op_disp = operand
                                    val_disp = f'={self.memory.labels[operand]}'
                                else:
                                    op_disp = f'R{str(operand)}'
                                    val_disp = f'={val}'
                                op_strs.append(op_disp)
                                val_strs.append(val_disp)
                            # Find max width for each operand column
                            num_ops = len(op_strs)
                            col_widths = [0] * num_ops
                            for i in range(num_ops):
                                col_widths[i] = max(len(op_strs[i]) + len(val_strs[i]), 1)
                            # Build aligned columns
                            aligned_cols = []
                            for i in range(num_ops):
                                s = op_strs[i] + val_strs[i]
                                aligned_cols.append(s.ljust(col_widths[i]))
                            reg_val_str = '\t'.join(aligned_cols)
                            print(f"PC={pc:04X} {op}\t{reg_val_str}")
                        else:
                            print(f"Executing instruction at PC={self.cpu.pc:04X}")
                    if not self.step():
                        break
                    cycles += 1
                    self.last_execution_time = current_time
                
        
        except Exception as e:
            self.cpu.state = CPUState.ERROR
            self.cpu.halt_reason = f"Execution error: {e}"
        
        finally:
            if self.start_time:
                self.execution_time += time.time() - self.start_time
                self.start_time = None
            
            self.running = False
    
    def set_breakpoint(self, address: int) -> None:
        """Set a breakpoint at the given address."""
        self.breakpoints.add(address)
    
    def clear_breakpoint(self, address: int) -> None:
        """Clear a breakpoint at the given address."""
        self.breakpoints.discard(address)
    
    def clear_all_breakpoints(self) -> None:
        """Clear all breakpoints."""
        self.breakpoints.clear()
    
    def add_debug_callback(self, callback: Callable) -> None:
        """Add a debug callback function.
        
        Args:
            callback: Function to call on debug events
        """
        self.debug_callbacks.append(callback)
    
    def remove_debug_callback(self, callback: Callable) -> None:
        """Remove a debug callback function."""
        if callback in self.debug_callbacks:
            self.debug_callbacks.remove(callback)
    
    def _trigger_debug_callbacks(self) -> None:
        """Trigger all debug callbacks."""
        for callback in self.debug_callbacks:
            try:
                callback(self)
            except Exception as e:
                print(f"Debug callback error: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get complete VM state for debugging."""
        state = {
            'vm': {
                'running': self.running,
                'paused': self.paused,
                'execution_time': self.execution_time,
                'breakpoints': list(self.breakpoints)
            },
            'cpu': self.cpu.get_state(),
            'memory': self.memory.get_memory_map()
        }
        
        if self.gpu:
            state['gpu'] = self.gpu.get_state()
        
        return state
    
    def get_register(self, reg_id: int) -> int:
        """Get CPU register value."""
        return self.cpu.get_register(reg_id)
    
    def set_register(self, reg_id: int, value: int) -> None:
        """Set CPU register value."""
        self.cpu.set_register(reg_id, value)
    
    def read_memory(self, address: int) -> int:
        """Read memory value."""
        return self.memory.read(address)
    
    def write_memory(self, address: int, value: int) -> None:
        """Write memory value."""
        self.memory.write(address, value)
    
    def get_memory_dump(self, start: int = 0, count: int = 16) -> Dict[int, int]:
        """Get memory dump for debugging."""
        return self.memory.dump_ram(start, count)
    
    def get_program_dump(self, start: int = 0, count: int = 10) -> List[str]:
        """Get program dump for debugging."""
        return self.memory.dump_program(start, count)
    

    def _keep_display_open(self, duration: float = 5.0) -> None:
        """Keep display open for specified duration after program completion."""
        if not self.gpu or not self.gpu.pygame_initialized:
            return
            
        print(f"Program completed. Display will remain open for {duration} seconds...")
        print("Press any key or close window to exit.")
        
        import pygame
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN:
                    return
            
            # Update display at 60 FPS
            if self.gpu and self.gpu.pygame_initialized:
                if not self.gpu.update_display():
                    return
            # time.sleep(0.016)  # ~60 FPS
    
    def shutdown(self) -> None:
        """Shutdown the virtual machine."""
        self.stop()
        
        if self.gpu:
            self.gpu.shutdown_display()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


def create_vm(config: Optional[Dict[str, Any]] = None) -> VirtualMachine:
    """Create a virtual machine with optional configuration.
    
    Args:
        config: Optional configuration dictionary
    
    Returns:
        Configured VirtualMachine instance
    """
    if config is None:
        config = {}
    
    return VirtualMachine(
        ram_size=config.get('ram_size', 0x8000),
        rom_size=config.get('rom_size', 0x4000),
        num_registers=config.get('num_registers', 32),
        display_width=config.get('display_width', 32),
        display_height=config.get('display_height', 32),
        enable_gpu=config.get('enable_gpu', True)
    )


def main():
    """Main entry point for VM when run as script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='MCL Virtual Machine')
    parser.add_argument('--file', '-f', type=str, help='Assembly file to load and run')
    parser.add_argument('--headless', action='store_true', help='Run without graphics')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--scale', type=int, default=2, help='Display scale factor')
    parser.add_argument('--paused', action='store_true', help='Start the simulator paused')
    
    args = parser.parse_args()
    
    try:
        config = {
            'enable_gpu': not args.headless,
            'display_scale': args.scale
        }
        
        vm = create_vm(config)
        
        if args.file:
            print(f"Loading assembly file: {args.file}")
            vm.load_program(args.file)
            print("Running program...")
            # When run from CLI, start immediately at full speed (not paused)
            # unless --paused flag is set
            if args.paused:
                print("Starting paused. Press Space or use the UI to resume.")
                vm.paused = True
                if vm.gpu:
                    vm.gpu.cpu_paused = True
                    vm.gpu.highspeed_mode = True  # Speed is still full when unpaused
            else:
                vm.paused = False
                vm.highspeed_mode = True
                # Sync GPU UI state so play/highspeed buttons show correct state
                if vm.gpu:
                    vm.gpu.cpu_paused = False
                    vm.gpu.highspeed_mode = True
            vm.start()
            
            # Shutdown cleanly
            vm.shutdown()
        else:
            print("MCL Virtual Machine started")
            print("Use --file to load an assembly program")
            vm.start()
            vm.shutdown()
            
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())