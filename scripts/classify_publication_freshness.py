#!/usr/bin/env python3
"""Read-only exact provider lock/snapshot relation; never advance locks."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration.freshness import main
if __name__=='__main__':raise SystemExit(main())
