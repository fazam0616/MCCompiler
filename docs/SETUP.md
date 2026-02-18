# MCL Compiler Toolchain Setup Guide

## Prerequisites

- Python 3.8 or later
- pip (Python package manager)
- Visual Studio Code (for language support)
- Git (recommended)

## Installation

### 1. Clone/Download the Repository

```bash
# If using Git
git clone <your-repo-url>
cd MCCompiler

# Or download and extract the ZIP file
```

### 2. Install Python Dependencies

```bash
# Install required packages
pip install -r requirements.txt

# Or install individually
pip install pygame>=2.0.0
pip install pygls>=1.0.0
pip install lsprotocol>=2023.0.0a1
pip install click>=8.0.0
pip install rich>=12.0.0
pip install dataclasses-json>=0.5.0
```

### 3. Verify Installation

```bash
# Run the test suite
python tests/run_tests.py

# Test the compiler
python src/compiler/main.py examples/hello_world.mcl

# Test the virtual machine
python src/vm/virtual_machine.py --file examples/hello_world.asm
```

## VSCode Extension Setup

### Option 1: Install from VSIX (Recommended)

1. Package the extension:
   ```bash
   cd vscode_extension
   npm install -g vsce
   npm install
   vsce package
   ```

2. Install in VSCode:
   - Open VSCode
   - Press `Ctrl+Shift+P`
   - Type "Extensions: Install from VSIX"
   - Select the generated `.vsix` file

### Option 2: Development Mode

1. Open VSCode
2. Go to File → Open Folder
3. Select the `vscode_extension` directory
4. Press `F5` to launch Extension Development Host

## Language Server Setup

### Start Language Server

```bash
# Start the language server (TCP mode)
python src/language_server/main.py --transport tcp --port 2087

# Or use stdio mode for direct VSCode integration
python src/language_server/main.py --transport stdio
```

### VSCode Configuration

Add to your VSCode `settings.json`:

```json
{
    "mcl.languageServer.enabled": true,
    "mcl.languageServer.host": "localhost",
    "mcl.languageServer.port": 2087,
    "mcl.compiler.path": "/path/to/MCCompiler/src/compiler/main.py"
}
```

## Usage Examples

### Compile MCL to Assembly

```bash
# Basic compilation
python src/compiler/main.py examples/hello_world.mcl

# Specify output file
python src/compiler/main.py examples/hello_world.mcl -o output.asm

# Enable debug output
python src/compiler/main.py examples/hello_world.mcl --debug
```

### Run Programs in Virtual Machine

```bash
# Run assembly file
python src/vm/virtual_machine.py --file examples/hello_world.asm

# Run with graphics disabled (headless)
python src/vm/virtual_machine.py --file examples/hello_world.asm --headless

# Enable debug mode
python src/vm/virtual_machine.py --file examples/hello_world.asm --debug
```

### Debug Programs

```bash
# Interactive debugger
python src/debugger/main.py examples/hello_world.asm

# Debug adapter (for VSCode)
python src/debugger/debug_adapter.py
```

## Project Structure

```
MCCompiler/
├── src/
│   ├── compiler/          # MCL compiler
│   ├── vm/               # Virtual machine
│   ├── debugger/         # Debugging tools
│   └── language_server/  # LSP server
├── examples/             # Sample MCL programs
├── tests/               # Test suite
├── vscode_extension/    # VSCode extension
├── README.md
├── requirements.txt
└── pyproject.toml
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all dependencies are installed
   - Check Python path includes the `src` directory

2. **Graphics Issues**
   - Install pygame: `pip install pygame`
   - Use `--headless` mode if graphics aren't needed

3. **Language Server Not Working**
   - Check if server is running on correct port
   - Verify VSCode extension is installed
   - Check VSCode output panel for errors

4. **Permission Errors**
   - On Linux/Mac: `chmod +x src/*/main.py`
   - Run with `python` prefix instead of direct execution

### Getting Help

- Check the test output for specific error messages
- Review log files in the project directory
- Ensure all file paths use forward slashes (`/`) even on Windows
- Verify Python version compatibility (3.8+)

## Development

### Adding New Features

1. **Language Features**: Modify lexer, parser, and AST nodes
2. **Assembly Instructions**: Update CPU class and instruction set
3. **VM Features**: Extend virtual machine capabilities
4. **Debug Features**: Enhance debugger and debug adapter

### Testing

```bash
# Run all tests
python tests/run_tests.py

# Run specific test
python -m unittest tests.test_basic_compilation

# Add new test files in tests/ directory
```

### Contributing

1. Create feature branches for new development
2. Add tests for new functionality
3. Update documentation as needed
4. Test with example programs before committing