#!/usr/bin/env python3
"""Site's immutable Integration release acquisition entrypoint."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from site_renderer.acquire import main
if __name__=='__main__':main()
