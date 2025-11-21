"""MCL Debug Adapter

Implements the Debug Adapter Protocol for VSCode integration.
"""

import json
import sys
import threading
import asyncio
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from ..vm.virtual_machine import VirtualMachine, create_vm
from ..vm.cpu import CPUState


class DebugAdapterError(Exception):
    """Exception for debug adapter errors."""
    pass


class DebugMessage:
    """Debug adapter protocol message."""
    
    def __init__(self, msg_type: str, seq: int, **kwargs):
        self.type = msg_type
        self.seq = seq
        self.data = kwargs
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'type': self.type,
            'seq': self.seq
        }
        result.update(self.data)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DebugMessage':
        msg_type = data.pop('type')
        seq = data.pop('seq')
        return cls(msg_type, seq, **data)


class MCLDebugAdapter:
    """Debug Adapter for MCL language."""
    
    def __init__(self, input_stream=None, output_stream=None):
        """Initialize debug adapter.
        
        Args:
            input_stream: Input stream (default: stdin)
            output_stream: Output stream (default: stdout)
        """
        self.input_stream = input_stream or sys.stdin
        self.output_stream = output_stream or sys.stdout
        
        # State
        self.vm: Optional[VirtualMachine] = None
        self.sequence = 0
        self.client_seq = 0
        self.running = False
        
        # Source mapping
        self.source_file: Optional[str] = None
        self.source_lines: List[str] = []
        
        # Request handlers
        self.request_handlers = {
            'initialize': self._handle_initialize,
            'launch': self._handle_launch,
            'attach': self._handle_attach,
            'setBreakpoints': self._handle_set_breakpoints,
            'continue': self._handle_continue,
            'next': self._handle_next,
            'stepIn': self._handle_step_in,
            'stepOut': self._handle_step_out,
            'pause': self._handle_pause,
            'stackTrace': self._handle_stack_trace,
            'scopes': self._handle_scopes,
            'variables': self._handle_variables,
            'evaluate': self._handle_evaluate,
            'disconnect': self._handle_disconnect,
        }
    
    def run(self) -> None:
        """Start the debug adapter."""
        self.running = True
        
        try:
            while self.running:
                message = self._read_message()
                if message:
                    self._handle_message(message)
        except Exception as e:
            self._send_error_response(0, str(e))
        finally:
            if self.vm:
                self.vm.shutdown()
    
    def _read_message(self) -> Optional[Dict[str, Any]]:
        """Read a message from the input stream."""
        try:
            # Read Content-Length header
            while True:
                line = self.input_stream.readline()
                if not line:
                    return None
                
                line = line.strip()
                if line.startswith('Content-Length:'):
                    length = int(line.split(':')[1].strip())
                    break
                elif line == '':
                    # Empty line, look for content length in next lines
                    continue
            
            # Read empty line
            self.input_stream.readline()
            
            # Read message body
            content = self.input_stream.read(length)
            return json.loads(content)
            
        except (json.JSONDecodeError, ValueError, IOError):
            return None
    
    def _send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to the output stream."""
        try:
            content = json.dumps(message)
            header = f"Content-Length: {len(content)}\r\n\r\n"
            
            self.output_stream.write(header)
            self.output_stream.write(content)
            self.output_stream.flush()
            
        except IOError:
            pass
    
    def _send_response(self, request_seq: int, command: str, success: bool = True, 
                      message: str = None, body: Dict[str, Any] = None) -> None:
        """Send a response message."""
        self.sequence += 1
        
        response = {
            'type': 'response',
            'seq': self.sequence,
            'request_seq': request_seq,
            'success': success,
            'command': command
        }
        
        if message:
            response['message'] = message
        
        if body:
            response['body'] = body
        
        self._send_message(response)
    
    def _send_event(self, event: str, body: Dict[str, Any] = None) -> None:
        """Send an event message."""
        self.sequence += 1
        
        event_msg = {
            'type': 'event',
            'seq': self.sequence,
            'event': event
        }
        
        if body:
            event_msg['body'] = body
        
        self._send_message(event_msg)
    
    def _send_error_response(self, request_seq: int, error_message: str) -> None:
        """Send an error response."""
        self._send_response(request_seq, 'error', False, error_message)
    
    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message."""
        msg_type = message.get('type')
        
        if msg_type == 'request':
            self._handle_request(message)
        elif msg_type == 'response':
            # Handle responses if needed
            pass
        elif msg_type == 'event':
            # Handle events if needed
            pass
    
    def _handle_request(self, message: Dict[str, Any]) -> None:
        """Handle a request message."""
        command = message.get('command')
        seq = message.get('seq', 0)
        arguments = message.get('arguments', {})
        
        handler = self.request_handlers.get(command)
        if handler:
            try:
                handler(seq, arguments)
            except Exception as e:
                self._send_error_response(seq, str(e))
        else:
            self._send_error_response(seq, f"Unknown command: {command}")
    
    # Request handlers
    
    def _handle_initialize(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle initialize request."""
        capabilities = {
            'supportsConfigurationDoneRequest': True,
            'supportsFunctionBreakpoints': False,
            'supportsConditionalBreakpoints': False,
            'supportsHitConditionalBreakpoints': False,
            'supportsEvaluateForHovers': True,
            'exceptionBreakpointFilters': [],
            'supportsStepBack': False,
            'supportsSetVariable': True,
            'supportsRestartFrame': False,
            'supportsGotoTargetsRequest': False,
            'supportsStepInTargetsRequest': False,
            'supportsCompletionsRequest': False
        }
        
        self._send_response(seq, 'initialize', True, body=capabilities)
        self._send_event('initialized')
    
    def _handle_launch(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle launch request."""
        try:
            program = args.get('program')
            if not program:
                raise DebugAdapterError("No program specified")
            
            # Create VM and load program
            self.vm = create_vm()
            self.vm.load_program(program)
            
            # Load source file for debugging
            self.source_file = program
            try:
                with open(program, 'r') as f:
                    self.source_lines = f.readlines()
            except IOError:
                self.source_lines = []
            
            self._send_response(seq, 'launch', True)
            
            # Send stopped event
            self._send_event('stopped', {
                'reason': 'entry',
                'threadId': 1
            })
            
        except Exception as e:
            self._send_error_response(seq, str(e))
    
    def _handle_attach(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle attach request."""
        self._send_error_response(seq, "Attach not supported")
    
    def _handle_set_breakpoints(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle setBreakpoints request."""
        if not self.vm:
            self._send_error_response(seq, "No program loaded")
            return
        
        source = args.get('source', {})
        breakpoints = args.get('breakpoints', [])
        
        # Clear existing breakpoints
        self.vm.clear_all_breakpoints()
        
        # Set new breakpoints
        verified_breakpoints = []
        for bp in breakpoints:
            line = bp.get('line', 0)
            # Convert line number to instruction address
            # This is simplified - a real implementation would need
            # proper source-to-assembly mapping
            address = max(0, line - 1)
            
            self.vm.set_breakpoint(address)
            
            verified_breakpoints.append({
                'verified': True,
                'line': line,
                'id': address
            })
        
        self._send_response(seq, 'setBreakpoints', True, body={
            'breakpoints': verified_breakpoints
        })
    
    def _handle_continue(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle continue request."""
        if not self.vm:
            self._send_error_response(seq, "No program loaded")
            return
        
        # Start execution in a separate thread
        def run_vm():
            self.vm.start()
            
            # Wait for execution to stop
            while self.vm.running and not self.vm.paused:
                if self.vm.cpu.state == CPUState.BREAKPOINT:
                    self._send_event('stopped', {
                        'reason': 'breakpoint',
                        'threadId': 1
                    })
                    return
                elif self.vm.cpu.state != CPUState.RUNNING:
                    reason = 'exception' if self.vm.cpu.state == CPUState.ERROR else 'exit'
                    self._send_event('stopped', {
                        'reason': reason,
                        'threadId': 1,
                        'text': self.vm.cpu.halt_reason
                    })
                    return
            
            # import time
            # time.sleep(0.01)
        
        threading.Thread(target=run_vm, daemon=True).start()
        
        self._send_response(seq, 'continue', True, body={
            'allThreadsContinued': True
        })
    
    def _handle_next(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle next (step over) request."""
        if not self.vm:
            self._send_error_response(seq, "No program loaded")
            return
        
        self.vm.step()
        
        self._send_response(seq, 'next', True)
        self._send_event('stopped', {
            'reason': 'step',
            'threadId': 1
        })
    
    def _handle_step_in(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle stepIn request."""
        # For now, same as next
        self._handle_next(seq, args)
    
    def _handle_step_out(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle stepOut request."""
        # For now, same as next
        self._handle_next(seq, args)
    
    def _handle_pause(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle pause request."""
        if not self.vm:
            self._send_error_response(seq, "No program loaded")
            return
        
        self.vm.pause()
        
        self._send_response(seq, 'pause', True)
        self._send_event('stopped', {
            'reason': 'pause',
            'threadId': 1
        })
    
    def _handle_stack_trace(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle stackTrace request."""
        if not self.vm:
            self._send_error_response(seq, "No program loaded")
            return
        
        # Simplified stack trace - just current PC
        frames = [{
            'id': 1,
            'name': 'main',
            'line': self.vm.cpu.pc + 1,  # 1-indexed for VSCode
            'column': 1,
            'source': {
                'name': Path(self.source_file).name if self.source_file else 'program',
                'path': self.source_file
            }
        }]
        
        self._send_response(seq, 'stackTrace', True, body={
            'stackFrames': frames,
            'totalFrames': 1
        })
    
    def _handle_scopes(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle scopes request."""
        scopes = [
            {
                'name': 'Registers',
                'variablesReference': 1,
                'expensive': False
            },
            {
                'name': 'Memory',
                'variablesReference': 2,
                'expensive': True
            }
        ]
        
        self._send_response(seq, 'scopes', True, body={
            'scopes': scopes
        })
    
    def _handle_variables(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle variables request."""
        if not self.vm:
            self._send_error_response(seq, "No program loaded")
            return
        
        variables_ref = args.get('variablesReference', 0)
        variables = []
        
        if variables_ref == 1:  # Registers
            for i in range(min(16, len(self.vm.cpu.registers))):
                value = self.vm.get_register(i)
                variables.append({
                    'name': f'R{i}',
                    'value': f'0x{value:08X} ({value})',
                    'variablesReference': 0
                })
        
        elif variables_ref == 2:  # Memory
            memory_dump = self.vm.get_memory_dump(0, 16)
            for addr, value in memory_dump.items():
                variables.append({
                    'name': f'0x{addr:04X}',
                    'value': f'0x{value:08X} ({value})',
                    'variablesReference': 0
                })
        
        self._send_response(seq, 'variables', True, body={
            'variables': variables
        })
    
    def _handle_evaluate(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle evaluate request."""
        if not self.vm:
            self._send_error_response(seq, "No program loaded")
            return
        
        expression = args.get('expression', '')
        
        try:
            # Simple expression evaluation
            if expression.startswith('r') or expression.startswith('R'):
                # Register access: r0, R1, etc.
                reg_num = int(expression[1:])
                value = self.vm.get_register(reg_num)
                result = f'0x{value:08X} ({value})'
            
            elif expression.startswith('0x'):
                # Memory access
                addr = int(expression, 16)
                value = self.vm.read_memory(addr)
                result = f'0x{value:08X} ({value})'
            
            else:
                result = "Expression not supported"
            
            self._send_response(seq, 'evaluate', True, body={
                'result': result,
                'variablesReference': 0
            })
        
        except Exception as e:
            self._send_error_response(seq, str(e))
    
    def _handle_disconnect(self, seq: int, args: Dict[str, Any]) -> None:
        """Handle disconnect request."""
        if self.vm:
            self.vm.shutdown()
        
        self._send_response(seq, 'disconnect', True)
        self.running = False


def start_debug_adapter() -> None:
    """Start the debug adapter."""
    adapter = MCLDebugAdapter()
    adapter.run()


if __name__ == '__main__':
    start_debug_adapter()