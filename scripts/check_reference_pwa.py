#!/usr/bin/env python3
"""Run existing real-worker positive and negative proofs on the Pages artifact."""
import json
from pathlib import Path
from check_pwa_freshness import run_check

if __name__ == "__main__":
    print(json.dumps(run_check(Path("build/site"), None)))
