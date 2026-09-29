#!/usr/bin/env python3
"""Render the current worktree against a downloaded Bundle, without committing it.

An isolated temporary Git snapshot supplies honest provenance for the preview.
Only tracked and non-ignored files are copied; the user's worktree is untouched.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    bundle, output = args.bundle.resolve(strict=True), args.output.absolute()
    if output == ROOT or ROOT in output.parents or output in ROOT.parents:
        parser.error('preview output must be outside the source worktree')
    with tempfile.TemporaryDirectory(prefix='site-preview-source-') as temporary:
        snapshot = Path(temporary)
        files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT)
        for raw in set(files.split(b'\0')) - {b''}:
            source = ROOT / os.fsdecode(raw)
            if source.is_symlink():
                parser.error(f'preview input is a symlink: {source}')
            if not source.exists():  # An uncommitted deletion.
                continue
            target = snapshot / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            shutil.copymode(source, target)
        subprocess.run(['git', 'init', '-q', str(snapshot)], check=True)
        subprocess.run(['git', '-C', str(snapshot), 'add', '--all'], check=True)
        subprocess.run(['git', '-C', str(snapshot), '-c', 'user.name=Local preview',
                        '-c', 'user.email=preview@example.invalid', 'commit', '-qm', 'Disposable preview snapshot'], check=True)
        identity = json.loads((bundle / 'bundle.json').read_text())['identity']
        subprocess.run([sys.executable, str(snapshot / 'scripts/render_publication_bundle.py'),
                        '--site-root', str(snapshot), '--bundle', str(bundle),
                        '--bundle-identity', identity, '--output', str(output)], check=True)
    print(f'Preview: {output / "site"} (serve with python -m http.server --directory {output / "site"})')


if __name__ == '__main__':
    main()
