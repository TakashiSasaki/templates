#!/usr/bin/env python3
"""Compare a P5 Bundle with the recorded landed-Site provider payload inventory."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from integration.bootstrap import compare
from publication_bundle.contract import BundleError, read_json

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    reference=read_json(root/'bootstrap/site-bundle-reference.json')
    proof=read_json(root/'bootstrap/provenance.json')
    if reference['site_producer']!={'authority':'site-internal-integration','revision':proof['source_site_revision']} or reference['providers']!=proof['reviewed_providers']:
        raise BundleError('bootstrap reference/provenance mismatch')
    print(json.dumps(compare(args.bundle,reference),sort_keys=True))
