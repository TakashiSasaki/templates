#!/usr/bin/env python3
"""Fetch a successful Integration publication for a Site build or local preview."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from site_renderer.channel import main
if __name__ == '__main__':
    main()
