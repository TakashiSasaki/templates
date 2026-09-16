#!/usr/bin/env python3
"""Site-local validation; publication inputs are a locked Integration Bundle."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
NODE_EXPLAINABILITY_TESTS = (
    "tests/composition-playground.test.mjs",
    "tests/composition-playground-final-remediation.test.mjs",
    "tests/composition-playground-hash-copy-review.test.mjs",
    "tests/composition-playground-final-three-review.test.mjs",
    "tests/composition-playground-latest-review.test.mjs",
    "tests/composition-playground-root-reachability.test.mjs",
    "tests/composition-playground-latest-five-review.test.mjs",
    "tests/composition-playground-explain.test.mjs",
    "tests/composition-playground-topology.test.mjs",
)
PROFILES={'fast':('core',),'full':('core','browser','bundle-reader'),'ready':('core','browser','bundle-reader')}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('profile',choices=PROFILES)
    p.add_argument('--check',action='append',choices=['core','browser','node-explainability','bundle-reader'])
    p.add_argument('--expected-head');p.add_argument('--bundle',type=Path);p.add_argument('--site-root',type=Path)
    a=p.parse_args();head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    if a.expected_head and a.expected_head!=head:p.error('exact Site head mismatch')
    for check in a.check or PROFILES[a.profile]:
        if check=='node-explainability':commands=[['node','--test',test] for test in NODE_EXPLAINABILITY_TESTS]
        elif check=='bundle-reader':
            if a.bundle is None or a.site_root is None:p.error('Bundle reader validation requires --bundle and --site-root')
            commands=[[sys.executable,'scripts/check_bundle_reader.py','--bundle',str(a.bundle),'--site-root',str(a.site_root)]]
        else:commands=[[sys.executable,'scripts/run_core_tests.py','--suite',check]]
        for command in commands:subprocess.run(command,cwd=ROOT,check=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
