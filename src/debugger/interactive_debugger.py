"""MCL Interactive Debugger

Provides a command-line interface for debugging MCL programs.
"""

import cmd
import sys
from typing import Dict, List, Optional, Any
from pathlib import Path

from ..vm.virtual_machine import VirtualMachine, create_vm
from ..vm.cpu import CPUState
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text


class MCLDebugger(cmd.Cmd):
    """Interactive debugger for MCL programs."""
    
    intro = """MCL Interactive Debugger v0.1.0
Type 'help' or '?' for commands.
"""
    prompt = "(mcl-debug) "
    
    def __init__(self):
        super().__init__()
        self.vm: Optional[VirtualMachine] = None
        self.console = Console()
        self.last_dump_address = 0
        self.last_dump_count = 16
    
    def preloop(self):
        """Setup before command loop."""
        self.console.print("[bold blue]MCL Interactive Debugger[/bold blue]")
        self.console.print("Load a program with 'load <filename>' to start debugging.\n")
    
    def postloop(self):
        """Cleanup after command loop."""
        if self.vm:
            self.vm.shutdown()
    
    # File operations
    
    def do_load(self, arg: str) -> None:
        """Load an assembly file: load <filename>"""
        if not arg:
            self.console.print("[red]Error: Please specify a filename[/red]")
            return
        
        try:
            # Create or reset VM
            if self.vm:
                self.vm.shutdown()
            
            self.vm = create_vm()
            self.vm.load_program(arg)
            
            self.console.print(f"[green]Program loaded: {arg}[/green]")
            self._show_status()
            
        except Exception as e:
            self.console.print(f"[red]Error loading program: {e}[/red]")
    
    def do_reload(self, arg: str) -> None:
        """Reload the current program"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        # Note: Would need to track the filename for proper reload
        self.console.print("[yellow]Reload not implemented yet[/yellow]")
    
    # Execution control
    
    def do_run(self, arg: str) -> None:
        """Run the program: run [max_cycles]"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        max_cycles = None
        if arg:
            try:
                max_cycles = int(arg)
            except ValueError:
                self.console.print("[red]Invalid cycle count[/red]")
                return
        
        try:
            self.console.print("[green]Starting execution...[/green]")
            self.vm.start(max_cycles)
            
            # Wait for execution to complete or pause
            import time
            while self.vm.running and not self.vm.paused:
                time.sleep(0.1)
            
            self._show_status()
            
        except Exception as e:
            self.console.print(f"[red]Execution error: {e}[/red]")
    
    def do_step(self, arg: str) -> None:
        """Execute one instruction: step [count]"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        count = 1
        if arg:
            try:
                count = int(arg)
            except ValueError:
                self.console.print("[red]Invalid step count[/red]")
                return
        
        for i in range(count):
            if not self.vm.step():
                break
        
        self._show_status()
    
    def do_continue(self, arg: str) -> None:
        """Continue execution: continue"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        if not self.vm.running:
            self.do_run("")
        else:
            self.vm.resume()
    
    def do_pause(self, arg: str) -> None:
        """Pause execution: pause"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        self.vm.pause()
        self.console.print("[yellow]Execution paused[/yellow]")
    
    def do_stop(self, arg: str) -> None:
        """Stop execution: stop"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        self.vm.stop()
        self.console.print("[yellow]Execution stopped[/yellow]")
        self._show_status()
    
    def do_reset(self, arg: str) -> None:
        """Reset the virtual machine: reset"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        self.vm.reset()
        self.console.print("[green]Virtual machine reset[/green]")
        self._show_status()
    
    # Breakpoints
    
    def do_break(self, arg: str) -> None:
        """Set breakpoint: break <address>"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        if not arg:
            self._list_breakpoints()
            return
        
        try:
            address = self._parse_address(arg)
            self.vm.set_breakpoint(address)
            self.console.print(f"[green]Breakpoint set at 0x{address:04X}[/green]")
        except ValueError:
            self.console.print("[red]Invalid address[/red]")
    
    def do_delete(self, arg: str) -> None:
        """Delete breakpoint: delete <address>"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        if not arg:
            self.console.print("[red]Please specify breakpoint address[/red]")
            return
        
        try:
            address = self._parse_address(arg)
            self.vm.clear_breakpoint(address)
            self.console.print(f"[yellow]Breakpoint cleared at 0x{address:04X}[/yellow]")
        except ValueError:
            self.console.print("[red]Invalid address[/red]")
    
    def do_clear(self, arg: str) -> None:
        """Clear all breakpoints: clear"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        self.vm.clear_all_breakpoints()
        self.console.print("[yellow]All breakpoints cleared[/yellow]")
    
    # Information display
    
    def do_status(self, arg: str) -> None:
        """Show VM status: status"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        self._show_status()
    
    def do_registers(self, arg: str) -> None:
        """Show registers: registers [start] [count]"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        start = 0
        count = 16
        
        if arg:
            parts = arg.split()
            if len(parts) >= 1:
                try:
                    start = int(parts[0])
                except ValueError:
                    self.console.print("[red]Invalid start register[/red]")
                    return
            if len(parts) >= 2:
                try:
                    count = int(parts[1])
                except ValueError:
                    self.console.print("[red]Invalid count[/red]")
                    return
        
        self._show_registers(start, count)
    
    def do_memory(self, arg: str) -> None:
        """Show memory: memory [address] [count]"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        address = self.last_dump_address
        count = self.last_dump_count
        
        if arg:
            parts = arg.split()
            if len(parts) >= 1:
                try:
                    address = self._parse_address(parts[0])
                except ValueError:
                    self.console.print("[red]Invalid address[/red]")
                    return
            if len(parts) >= 2:
                try:
                    count = int(parts[1])
                except ValueError:
                    self.console.print("[red]Invalid count[/red]")
                    return
        
        self.last_dump_address = address
        self.last_dump_count = count
        
        self._show_memory(address, count)
    
    def do_program(self, arg: str) -> None:
        """Show program: program [start] [count]"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        start = max(0, self.vm.cpu.pc - 5)
        count = 10
        
        if arg:
            parts = arg.split()
            if len(parts) >= 1:
                try:
                    start = int(parts[0])
                except ValueError:
                    self.console.print("[red]Invalid start address[/red]")
                    return
            if len(parts) >= 2:
                try:
                    count = int(parts[1])
                except ValueError:
                    self.console.print("[red]Invalid count[/red]")
                    return
        
        self._show_program(start, count)
    
    # Memory/Register modification
    
    def do_set(self, arg: str) -> None:
        """Set register or memory: set reg <reg> <value> | set mem <addr> <value>"""
        if not self.vm:
            self.console.print("[red]No program loaded[/red]")
            return
        
        parts = arg.split()
        if len(parts) < 3:
            self.console.print("[red]Usage: set reg <reg> <value> | set mem <addr> <value>[/red]")
            return
        
        try:
            if parts[0] == 'reg':
                reg_id = int(parts[1])
                value = self._parse_value(parts[2])
                self.vm.set_register(reg_id, value)
                self.console.print(f"[green]Register {reg_id} = 0x{value:08X}[/green]")
            
            elif parts[0] == 'mem':
                address = self._parse_address(parts[1])
                value = self._parse_value(parts[2])
                self.vm.write_memory(address, value)
                self.console.print(f"[green]Memory[0x{address:04X}] = 0x{value:08X}[/green]")
            
            else:
                self.console.print("[red]Usage: set reg <reg> <value> | set mem <addr> <value>[/red]")
        
        except (ValueError, Exception) as e:
            self.console.print(f"[red]Error: {e}[/red]")
    
    # Utility commands
    
    def do_quit(self, arg: str) -> bool:
        """Quit the debugger: quit"""
        self.console.print("[blue]Goodbye![/blue]")
        return True
    
    def do_exit(self, arg: str) -> bool:
        """Exit the debugger: exit"""
        return self.do_quit(arg)
    
    def do_help(self, arg: str) -> None:
        """Show help: help [command]"""
        if arg:
            super().do_help(arg)
        else:
            self.console.print(Panel(
                "[bold]MCL Debugger Commands[/bold]\n\n"
                "[green]File Operations:[/green]\n"
                "  load <file>     - Load assembly file\n"
                "  reload          - Reload current program\n\n"
                "[green]Execution Control:[/green]\n"
                "  run [cycles]    - Run program\n"
                "  step [count]    - Execute instruction(s)\n"
                "  continue        - Continue execution\n"
                "  pause           - Pause execution\n"
                "  stop            - Stop execution\n"
                "  reset           - Reset VM\n\n"
                "[green]Breakpoints:[/green]\n"
                "  break [addr]    - Set/list breakpoints\n"
                "  delete <addr>   - Delete breakpoint\n"
                "  clear           - Clear all breakpoints\n\n"
                "[green]Information:[/green]\n"
                "  status          - Show VM status\n"
                "  registers       - Show registers\n"
                "  memory [addr]   - Show memory\n"
                "  program [addr]  - Show program\n\n"
                "[green]Modification:[/green]\n"
                "  set reg <r> <v> - Set register\n"
                "  set mem <a> <v> - Set memory\n\n"
                "[green]Other:[/green]\n"
                "  help [cmd]      - Show help\n"
                "  quit/exit       - Exit debugger",
                title="Help",
                border_style="blue"
            ))
    
    # Helper methods
    
    def _show_status(self) -> None:
        """Display VM status."""
        if not self.vm:
            return
        
        state = self.vm.get_state()
        cpu_state = state['cpu']
        vm_state = state['vm']
        
        # Status panel
        status_text = f"""[bold]CPU State:[/bold] {cpu_state['state']}
[bold]PC:[/bold] 0x{cpu_state['pc']:04X}
[bold]Instructions:[/bold] {cpu_state['instruction_count']}
[bold]Cycles:[/bold] {cpu_state['cycle_count']}
[bold]Running:[/bold] {vm_state['running']}
[bold]Paused:[/bold] {vm_state['paused']}"""
        
        if cpu_state.get('halt_reason'):
            status_text += f"\n[bold]Halt Reason:[/bold] {cpu_state['halt_reason']}"
        
        self.console.print(Panel(status_text, title="VM Status", border_style="green"))
    
    def _show_registers(self, start: int = 0, count: int = 16) -> None:
        """Display registers."""
        table = Table(title="Registers")
        table.add_column("Reg", style="cyan")
        table.add_column("Hex", style="green")
        table.add_column("Dec", style="yellow")
        table.add_column("Bin", style="blue")
        
        for i in range(start, min(start + count, len(self.vm.cpu.registers))):
            value = self.vm.get_register(i)
            table.add_row(
                f"R{i}",
                f"0x{value & 0xFFFFFFFF:08X}",
                f"{value}",
                f"{value & 0xFFFFFFFF:032b}"
            )
        
        self.console.print(table)
    
    def _show_memory(self, address: int, count: int = 16) -> None:
        """Display memory contents."""
        try:
            memory_data = self.vm.get_memory_dump(address, count)
            
            table = Table(title=f"Memory (0x{address:04X})")
            table.add_column("Address", style="cyan")
            table.add_column("Hex", style="green")
            table.add_column("Dec", style="yellow")
            table.add_column("ASCII", style="blue")
            
            for addr, value in memory_data.items():
                ascii_char = chr(value & 0xFF) if 32 <= (value & 0xFF) <= 126 else '.'
                table.add_row(
                    f"0x{addr:04X}",
                    f"0x{value:08X}",
                    f"{value}",
                    ascii_char
                )
            
            self.console.print(table)
            
        except Exception as e:
            self.console.print(f"[red]Error reading memory: {e}[/red]")
    
    def _show_program(self, start: int = 0, count: int = 10) -> None:
        """Display program instructions."""
        try:
            program_data = self.vm.get_program_dump(start, count)
            
            table = Table(title="Program")
            table.add_column("Address", style="cyan")
            table.add_column("Instruction", style="green")
            table.add_column("PC", style="red")
            
            for i, line in enumerate(program_data):
                addr = start + i
                pc_marker = ">>>" if addr == self.vm.cpu.pc else ""
                breakpoint_marker = "*" if addr in self.vm.breakpoints else ""
                
                table.add_row(
                    f"{addr:04d}",
                    line.split(': ', 1)[1] if ': ' in line else line,
                    f"{pc_marker} {breakpoint_marker}"
                )
            
            self.console.print(table)
            
        except Exception as e:
            self.console.print(f"[red]Error reading program: {e}[/red]")
    
    def _list_breakpoints(self) -> None:
        """List all breakpoints."""
        if not self.vm.breakpoints:
            self.console.print("[yellow]No breakpoints set[/yellow]")
            return
        
        table = Table(title="Breakpoints")
        table.add_column("Address", style="cyan")
        
        for addr in sorted(self.vm.breakpoints):
            table.add_row(f"0x{addr:04X}")
        
        self.console.print(table)
    
    def _parse_address(self, addr_str: str) -> int:
        """Parse address string (hex or decimal)."""
        if addr_str.startswith('0x') or addr_str.startswith('0X'):
            return int(addr_str, 16)
        return int(addr_str)
    
    def _parse_value(self, value_str: str) -> int:
        """Parse value string (hex or decimal)."""
        if value_str.startswith('0x') or value_str.startswith('0X'):
            return int(value_str, 16)
        return int(value_str)


def start_interactive_debugger(program_file: Optional[str] = None) -> None:
    """Start the interactive debugger.
    
    Args:
        program_file: Optional program file to load automatically
    """
    debugger = MCLDebugger()
    
    if program_file:
        debugger.onecmd(f"load {program_file}")
    
    try:
        debugger.cmdloop()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    finally:
        if debugger.vm:
            debugger.vm.shutdown()