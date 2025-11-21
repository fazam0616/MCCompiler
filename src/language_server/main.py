"""MCL Language Server Main Entry Point

Command-line interface for the MCL language server.
"""

import sys
import os
import argparse
import asyncio
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.language_server.server import mcl_server
except ImportError:
    # Fallback for different import contexts
    try:
        from .server import mcl_server
    except ImportError:
        # Direct execution context
        from server import mcl_server


def main() -> int:
    """Main entry point for the language server."""
    parser = argparse.ArgumentParser(
        description="MCL Language Server - Provides LSP support for MCL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcl-server                              # Start language server on stdio
  mcl-server --tcp                        # Start language server on TCP
  mcl-server --tcp --port 2087            # Start on specific TCP port
  mcl-server --websocket --port 8080      # Start WebSocket server
"""
    )
    
    parser.add_argument(
        "--tcp",
        action="store_true",
        help="Use TCP transport instead of stdio"
    )
    
    parser.add_argument(
        "--websocket",
        action="store_true",
        help="Use WebSocket transport"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=2087,
        help="Port number for TCP/WebSocket (default: 2087)"
    )
    
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host address for TCP/WebSocket (default: localhost)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="MCL Language Server v0.1.0"
    )
    
    args = parser.parse_args()
    
    try:
        if args.verbose:
            import logging
            logging.basicConfig(level=logging.DEBUG)
        
        if args.websocket:
            print(f"Starting MCL Language Server on WebSocket {args.host}:{args.port}")
            mcl_server.start_ws(args.host, args.port)
        elif args.tcp:
            print(f"Starting MCL Language Server on TCP {args.host}:{args.port}")
            mcl_server.start_tcp(args.host, args.port)
        else:
            print("Starting MCL Language Server on stdio", file=sys.stderr)
            mcl_server.start_io()
        
        return 0
        
    except KeyboardInterrupt:
        print("\nServer interrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())