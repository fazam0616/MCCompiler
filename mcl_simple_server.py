#!/usr/bin/env python3
"""
Simple MCL Language Server
A minimal working language server for MCL files using basic JSON-RPC
"""

import json
import sys
import os
import threading
import time
from typing import Dict, List, Any

class SimpleMCLLanguageServer:
    """A simple Language Server Protocol implementation for MCL"""
    
    def __init__(self):
        self.documents = {}
        
        # MCL Language definitions
        self.keywords = [
            'var', 'function', 'if', 'else', 'elif', 'while', 'for',
            'switch', 'case', 'default', 'return', 'break', 'continue'
        ]
        
        self.types = ['int', 'char', 'void']
        
        self.builtins = [
            'malloc', 'free', 'drawLine', 'fillGrid', 'clearGrid',
            'loadSprite', 'drawSprite', 'loadText', 'drawText', 'scrollBuffer'
        ]
    
    def send_response(self, request_id: Any, result: Any):
        """Send a response message"""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        self.send_message(response)
    
    def send_notification(self, method: str, params: Any = None):
        """Send a notification message"""
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params is not None:
            notification["params"] = params
        self.send_message(notification)
    
    def send_message(self, message: Dict[str, Any]):
        """Send a JSON-RPC message"""
        content = json.dumps(message, separators=(',', ':'))
        content_length = len(content)
        
        print(f"Sending response ({content_length} chars): {content}", file=sys.stderr)
        
        # Send using text mode to avoid encoding issues
        sys.stdout.write(f"Content-Length: {content_length}\r\n\r\n")
        sys.stdout.write(content)
        sys.stdout.flush()
    
    def handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        return {
            "capabilities": {
                "textDocumentSync": 1,  # Full sync
                "completionProvider": {
                    "triggerCharacters": [".", ":", " "]
                },
                "hoverProvider": True
            }
        }
    
    def handle_completion(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completion request"""
        items = []
        
        # Add keywords
        for keyword in self.keywords:
            items.append({
                "label": keyword,
                "kind": 14,  # Keyword
                "detail": "MCL keyword",
                "insertText": keyword
            })
        
        # Add types
        for type_name in self.types:
            items.append({
                "label": type_name,
                "kind": 25,  # TypeParameter
                "detail": "MCL type",
                "insertText": type_name
            })
        
        # Add built-in functions
        for builtin in self.builtins:
            items.append({
                "label": builtin,
                "kind": 3,  # Function
                "detail": "MCL built-in function",
                "insertText": f"{builtin}()"
            })
        
        return {
            "isIncomplete": False,
            "items": items
        }
    
    def handle_hover(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle hover request"""
        docs = {
            'function': 'Declares a function',
            'var': 'Declares a variable',
            'if': 'Conditional statement',
            'while': 'Loop statement',
            'int': '32-bit signed integer type',
            'char': 'Character type (ASCII)',
            'void': 'No return type',
            'malloc': 'Allocates memory dynamically',
            'free': 'Frees allocated memory',
            'drawLine': 'Draws a line on the GPU buffer'
        }
        
        # For simplicity, return a generic hover message
        return {
            "contents": {
                "kind": "markdown",
                "value": "**MCL Language Server**\n\nHover over MCL keywords for documentation."
            }
        }
    
    def handle_did_open(self, params: Dict[str, Any]):
        """Handle textDocument/didOpen"""
        doc = params["textDocument"]
        self.documents[doc["uri"]] = doc["text"]
    
    def handle_did_change(self, params: Dict[str, Any]):
        """Handle textDocument/didChange"""
        doc_uri = params["textDocument"]["uri"]
        for change in params["contentChanges"]:
            if "text" in change:
                self.documents[doc_uri] = change["text"]
    
    def run(self):
        """Run the language server"""
        print("MCL Simple Language Server starting on stdio...", file=sys.stderr)
        sys.stderr.flush()
        
        # Use binary mode for reliable reading
        stdin_binary = sys.stdin.buffer
        
        try:
            while True:
                try:
                    # Read headers
                    headers = {}
                    while True:
                        # Read line by line in binary mode
                        line_bytes = b''
                        while True:
                            byte = stdin_binary.read(1)
                            if not byte:
                                print("EOF received", file=sys.stderr)
                                return
                            line_bytes += byte
                            if line_bytes.endswith(b'\r\n'):
                                break
                        
                        line = line_bytes[:-2].decode('utf-8')  # Remove \r\n and decode
                        
                        if not line:
                            # Empty line means end of headers
                            break
                        
                        if ':' in line:
                            key, value = line.split(':', 1)
                            headers[key.strip()] = value.strip()
                    
                    # Get content length
                    if 'Content-Length' not in headers:
                        print("Missing Content-Length header", file=sys.stderr)
                        continue
                    
                    content_length = int(headers['Content-Length'])
                    print(f"Content-Length: {content_length}", file=sys.stderr)
                    
                    # Read exact content
                    content_bytes = stdin_binary.read(content_length)
                    if len(content_bytes) != content_length:
                        print(f"Expected {content_length} bytes, got {len(content_bytes)}", file=sys.stderr)
                        continue
                    
                    content = content_bytes.decode('utf-8')
                    print(f"Read {len(content)} characters successfully", file=sys.stderr)
                    
                    # Parse JSON using Python's built-in json module
                    try:
                        message = json.loads(content)
                        method = message.get("method")
                        request_id = message.get("id")
                        params = message.get("params", {})
                        
                        print(f"Parsed method: {method}, id: {request_id}", file=sys.stderr)
                        
                        if method == "initialize":
                            result = self.handle_initialize(request_id, params)
                            self.send_response(request_id, result)
                            print("Initialize response sent", file=sys.stderr)
                        
                        elif method == "initialized":
                            # Client has finished initialization
                            print("Client initialized successfully", file=sys.stderr)
                            # Send server capabilities notification
                            pass
                        
                        elif method == "textDocument/completion":
                            result = self.handle_completion(request_id, params)
                            self.send_response(request_id, result)
                        
                        elif method == "textDocument/hover":
                            result = self.handle_hover(request_id, params)
                            self.send_response(request_id, result)
                        
                        elif method == "textDocument/didOpen":
                            self.handle_did_open(params)
                        
                        elif method == "textDocument/didChange":
                            self.handle_did_change(params)
                        
                        elif method == "shutdown":
                            self.send_response(request_id, None)
                            print("Shutdown requested", file=sys.stderr)
                            break
                        
                        elif method == "exit":
                            print("Exit requested", file=sys.stderr)
                            break
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error: {e}", file=sys.stderr)
                        continue
                
                except KeyboardInterrupt:
                    print("Keyboard interrupt received", file=sys.stderr)
                    break
                except Exception as e:
                    print(f"Error in main loop: {e}", file=sys.stderr)
                    continue
        
        except Exception as e:
            print(f"Fatal error: {e}", file=sys.stderr)
        finally:
            print("MCL Language Server shutting down", file=sys.stderr)

# Create server instance
server = SimpleMCLLanguageServer()



def main():
    """Start the language server"""
    import sys
    
    # Enable verbose logging if requested
    if "--verbose" in sys.argv:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        print("Verbose logging enabled", file=sys.stderr)
    
    if "--tcp" in sys.argv:
        print("TCP mode not supported in simple server", file=sys.stderr)
        return 1
    
    # Run the server
    try:
        server.run()
        return 0
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1

if __name__ == "__main__":
    main()