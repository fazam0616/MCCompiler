#!/usr/bin/env python3
"""MCL Debugger Runner Script

This script properly sets up the Python path and runs the MCL debugger.
"""

import sys
import os
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'src'))

# Now import and run the debugger
from debugger.main import main

if __name__ == '__main__':
    main()