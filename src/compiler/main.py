"""MCL Compiler Main Entry Point

Command-line interface for the MCL compiler.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

# Add project root and src/ to path for local imports
_project_root = str(Path(__file__).parent.parent.parent)
_src_dir = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

try:
    from .lexer import tokenize, LexerError
    from .parser import parse, ParseError
    from .assembly_generator import generate_assembly, CodeGenerationError
except ImportError:
    from compiler.lexer import tokenize, LexerError
    from compiler.parser import parse, ParseError  
    from compiler.assembly_generator import generate_assembly, CodeGenerationError


def compile_file(input_path: Path, output_path: Optional[Path] = None, 
                optimize: bool = False, debug: bool = False) -> bool:
    """Compile an MCL file to assembly.
    
    Args:
        input_path: Path to input .mcl file
        output_path: Path to output .asm file (optional)
        optimize: Enable optimizations
        debug: Enable debug output
    
    Returns:
        True if compilation succeeded, False otherwise
    """
    try:
        # Read input file
        if not input_path.exists():
            print(f"Error: Input file '{input_path}' not found", file=sys.stderr)
            return False
        
        with open(input_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        if debug:
            print(f"Compiling: {input_path}")
        
        # Lexical analysis
        if debug:
            print("Lexical analysis...")
        
        tokens = tokenize(source_code)
        
        if debug:
            print(f"Generated {len(tokens)} tokens")
            for token in tokens[:10]:  # Show first 10 tokens
                print(f"  {token}")
            if len(tokens) > 10:
                print(f"  ... and {len(tokens) - 10} more tokens")
        
        # Parsing
        if debug:
            print("Parsing...")
        
        ast = parse(tokens)
        
        if debug:
            print(f"Generated AST with {len(ast.declarations)} declarations")
        
        # Code generation
        if debug:
            print("Generating assembly...")
        
        assembly_code = generate_assembly(ast)
        
        if debug:
            print("Assembly generation complete")
        
        # Determine output path
        if output_path is None:
            output_path = input_path.with_suffix('.asm')
        
        # Write output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(assembly_code)
        
        print(f"Compilation successful: {input_path} -> {output_path}")
        
        if debug:
            print("\nGenerated Assembly:")
            print("-" * 40)
            print(assembly_code)
            print("-" * 40)
        
        return True
        
    except LexerError as e:
        print(f"Lexer Error: {e}", file=sys.stderr)
        return False
    
    except ParseError as e:
        print(f"Parse Error: {e}", file=sys.stderr)
        return False
    
    except CodeGenerationError as e:
        print(f"Code Generation Error: {e}", file=sys.stderr)
        return False
    
    except Exception as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()
        return False


def main() -> int:
    """Main entry point for the compiler."""
    parser = argparse.ArgumentParser(
        description="MCL Compiler - Compile MCL source to assembly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcl-compile program.mcl                    # Compile to program.asm
  mcl-compile program.mcl -o output.asm     # Specify output file
  mcl-compile program.mcl --debug           # Enable debug output
  mcl-compile program.mcl --optimize        # Enable optimizations
"""
    )
    
    parser.add_argument(
        "input", 
        type=Path,
        help="Input MCL source file (.mcl)"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output assembly file (.asm)"
    )
    
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Enable optimizations (not yet implemented)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="MCL Compiler v0.1.0"
    )
    
    args = parser.parse_args()
    
    # Validate input file extension
    if args.input.suffix.lower() != '.mcl':
        print(f"Warning: Input file '{args.input}' does not have .mcl extension", 
              file=sys.stderr)
    
    # Compile the file
    success = compile_file(
        args.input,
        args.output,
        optimize=args.optimize,
        debug=args.debug
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())