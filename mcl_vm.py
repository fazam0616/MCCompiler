#!/usr/bin/env python3
"""MCL Virtual Machine Runner Script

This script properly sets up the Python path and runs the MCL virtual machine.

Usage:
    python mcl_vm.py --file <file.asm> [--paused] [--headless] [--debug] [--scale N]

Flags:
    --paused      Start the simulator paused (resume with Space or the UI play button)
    --headless    Run without a graphical display
    --debug       Enable debug mode
    --scale N     Display scale factor (default: 2)
"""

import sys
import os
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'src'))

# Now import and run the VM
from vm.virtual_machine import main

if __name__ == '__main__':
    sys.exit(main())