#!/usr/bin/env python3
"""Run local Site unit tests without provider checkouts or network access."""
from pathlib import Path
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=root, check=True)
    subprocess.run(['node', '--test', *map(str, sorted((root/'tests').glob('*.test.mjs')))], cwd=root, check=True)
