#!/usr/bin/env python3
"""CLI adapter for the Bundle-only Site renderer."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from site_renderer.render import main
if __name__=='__main__':main()
