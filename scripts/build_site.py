#!/usr/bin/env python3
"""Build and verify one Site artifact from one already acquired publication."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from site_renderer.bundle import validate
from site_renderer.render import render
from scripts.check_audience_artifact import check_artifact
from scripts.check_bundle_reader import check as check_bundle_reader
from scripts.check_site_artifact import check as check_site_artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = validate(args.bundle)
    render(bundle=args.bundle, site_root=Path(__file__).resolve().parents[1],
           output=args.output, expected_identity=manifest['identity'],
           deployment_timestamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'))
    site = args.output / 'site'
    check_bundle_reader(site, args.bundle)
    check_artifact(site, args.bundle)
    print(check_site_artifact(site, args.bundle))


if __name__ == '__main__':
    main()
