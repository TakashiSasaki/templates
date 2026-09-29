#!/usr/bin/env python3
"""Run Integration-local validation; publication is a separate downstream operation."""
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=root, check=True)
