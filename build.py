#!/usr/bin/env python3
"""Build script for MCL Compiler Toolchain.

This script helps build, test, and package the entire toolchain.
"""

import sys
import os
import subprocess
import argparse
import shutil
from pathlib import Path
from typing import List, Optional


def run_command(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    if cwd:
        print(f"  in directory: {cwd}")
    
    try:
        result = subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        if check:
            raise
        return e


def install_dependencies():
    """Install Python dependencies."""
    print("Installing Python dependencies...")
    
    requirements_file = Path(__file__).parent / 'requirements.txt'
    if requirements_file.exists():
        run_command([sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)])
    else:
        # Install individual packages
        packages = [
            'pygame>=2.0.0',
            'pygls>=1.0.0', 
            'lsprotocol>=2023.0.0a1',
            'click>=8.0.0',
            'rich>=12.0.0',
            'dataclasses-json>=0.5.0'
        ]
        for package in packages:
            run_command([sys.executable, '-m', 'pip', 'install', package])


def run_tests():
    """Run the test suite."""
    print("Running tests...")
    
    test_runner = Path(__file__).parent / 'tests' / 'run_tests.py'
    result = run_command([sys.executable, str(test_runner)], check=False)
    return result.returncode == 0


def build_vscode_extension():
    """Build the VSCode extension."""
    print("Building VSCode extension...")
    
    extension_dir = Path(__file__).parent / 'vscode_extension'
    
    # Check if npm is available
    try:
        run_command(['npm', '--version'])
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: npm not found. Skipping VSCode extension build.")
        return False
    
    # Install dependencies
    package_json = extension_dir / 'package.json'
    if package_json.exists():
        run_command(['npm', 'install'], cwd=extension_dir)
        
        # Try to install vsce if not available
        try:
            run_command(['vsce', '--version'])
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Installing vsce...")
            run_command(['npm', 'install', '-g', 'vsce'])
        
        # Package extension
        try:
            run_command(['vsce', 'package'], cwd=extension_dir)
            return True
        except subprocess.CalledProcessError:
            print("Warning: Failed to package VSCode extension")
            return False
    
    return False


def create_distribution():
    """Create distribution package."""
    print("Creating distribution package...")
    
    project_root = Path(__file__).parent
    dist_dir = project_root / 'dist'
    
    # Clean existing dist
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    
    dist_dir.mkdir()
    
    # Copy source files
    src_files = [
        'src/',
        'examples/',
        'tests/',
        'README.md',
        'SETUP.md',
        'requirements.txt',
        'pyproject.toml',
        'build.py'
    ]
    
    for item in src_files:
        src_path = project_root / item
        if src_path.exists():
            if src_path.is_file():
                shutil.copy2(src_path, dist_dir / item)
            else:
                shutil.copytree(src_path, dist_dir / item)
    
    # Copy VSCode extension if built
    extension_dir = project_root / 'vscode_extension'
    vsix_files = list(extension_dir.glob('*.vsix'))
    if vsix_files:
        ext_dist_dir = dist_dir / 'vscode_extension'
        ext_dist_dir.mkdir()
        for vsix in vsix_files:
            shutil.copy2(vsix, ext_dist_dir)
        
        # Also copy extension source
        for item in ['package.json', 'language-configuration.json', 'syntaxes/', 'themes/']:
            src_path = extension_dir / item
            if src_path.exists():
                if src_path.is_file():
                    shutil.copy2(src_path, ext_dist_dir / item)
                else:
                    shutil.copytree(src_path, ext_dist_dir / item)
    
    print(f"Distribution created in: {dist_dir}")
    return True


def clean():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")
    
    project_root = Path(__file__).parent
    
    # Directories to clean
    clean_dirs = [
        'dist/',
        'build/',
        '__pycache__/',
        '.pytest_cache/',
        'vscode_extension/node_modules/',
        'vscode_extension/out/'
    ]
    
    for clean_dir in clean_dirs:
        full_path = project_root / clean_dir
        if full_path.exists():
            print(f"Removing: {full_path}")
            shutil.rmtree(full_path)
    
    # Files to clean
    clean_patterns = [
        '**/*.pyc',
        '**/*.pyo',
        '**/__pycache__',
        'vscode_extension/*.vsix'
    ]
    
    for pattern in clean_patterns:
        for file_path in project_root.glob(pattern):
            if file_path.is_file():
                print(f"Removing: {file_path}")
                file_path.unlink()
            elif file_path.is_dir():
                print(f"Removing: {file_path}")
                shutil.rmtree(file_path)


def validate_examples():
    """Validate that example programs compile and run."""
    print("Validating example programs...")
    
    project_root = Path(__file__).parent
    examples_dir = project_root / 'examples'
    compiler_path = project_root / 'src' / 'compiler' / 'main.py'
    
    success = True
    
    for mcl_file in examples_dir.glob('*.mcl'):
        print(f"Validating {mcl_file.name}...")
        
        try:
            # Compile the example
            result = run_command([
                sys.executable, str(compiler_path),
                str(mcl_file), '--validate-only'
            ], check=False)
            
            if result.returncode != 0:
                print(f"  ❌ Compilation failed")
                success = False
            else:
                print(f"  ✅ Compilation successful")
        
        except Exception as e:
            print(f"  ❌ Error: {e}")
            success = False
    
    return success


def main():
    """Main build script entry point."""
    parser = argparse.ArgumentParser(description='Build MCL Compiler Toolchain')
    parser.add_argument('command', nargs='?', default='all',
                       choices=['all', 'deps', 'test', 'extension', 'dist', 'clean', 'validate'],
                       help='Build command to run')
    parser.add_argument('--skip-tests', action='store_true',
                       help='Skip running tests')
    parser.add_argument('--skip-extension', action='store_true', 
                       help='Skip building VSCode extension')
    
    args = parser.parse_args()
    
    print("MCL Compiler Toolchain Build Script")
    print("=" * 40)
    
    success = True
    
    try:
        if args.command in ['all', 'deps']:
            install_dependencies()
        
        if args.command in ['all', 'validate']:
            if not validate_examples():
                success = False
        
        if args.command in ['all', 'test'] and not args.skip_tests:
            if not run_tests():
                success = False
        
        if args.command in ['all', 'extension'] and not args.skip_extension:
            build_vscode_extension()
        
        if args.command in ['all', 'dist']:
            create_distribution()
        
        if args.command == 'clean':
            clean()
            return
    
    except KeyboardInterrupt:
        print("\nBuild interrupted by user")
        success = False
    except Exception as e:
        print(f"\nBuild failed with error: {e}")
        success = False
    
    print("\n" + "=" * 40)
    if success:
        print("Build completed successfully! ✅")
        if args.command == 'all':
            print("\nNext steps:")
            print("1. Install VSCode extension from vscode_extension/*.vsix")
            print("2. Start language server: python src/language_server/main.py")
            print("3. Try compiling: python src/compiler/main.py examples/hello_world.mcl")
    else:
        print("Build failed! ❌")
        sys.exit(1)


if __name__ == '__main__':
    main()