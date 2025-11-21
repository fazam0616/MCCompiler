"""MCL Debugger Main Entry Point

Command-line interface for the MCL debugger.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from .interactive_debugger import start_interactive_debugger
from .debug_adapter import start_debug_adapter


def main() -> int:
    """Main entry point for the debugger."""
    parser = argparse.ArgumentParser(
        description="MCL Debugger - Debug MCL assembly programs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcl-debug program.asm                    # Start interactive debugger
  mcl-debug --adapter                      # Start debug adapter for VSCode
  mcl-debug --interactive program.asm     # Start interactive debugger with program
"""
    )
    
    parser.add_argument(
        "program",
        nargs="?",
        type=Path,
        help="Assembly program to debug (.asm)"
    )
    
    parser.add_argument(
        "--adapter",
        action="store_true",
        help="Start debug adapter for VSCode integration"
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start interactive debugger (default)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="MCL Debugger v0.1.0"
    )
    
    args = parser.parse_args()
    
    try:
        if args.adapter:
            # Start debug adapter for VSCode
            start_debug_adapter()
        else:
            # Start interactive debugger (default)
            program_file = str(args.program) if args.program else None
            start_interactive_debugger(program_file)
        
        return 0
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())