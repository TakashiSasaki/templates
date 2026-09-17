#!/usr/bin/env python3
"""Cheap source/environment rejection before semantic and full qualification."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


VERSION_RE = re.compile(r'\b(\d+\.\d+\.\d+\.\d+)\b')


def command_version(command: str | Path) -> str:
    result = subprocess.run(
        [str(command), '--version'],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f'{command} --version failed with exit {result.returncode}'
            + (f': {detail}' if detail else '')
        )
    match = VERSION_RE.search(result.stdout or result.stderr)
    if match is None:
        raise RuntimeError(
            f'could not parse a four-part version from: '
            f'{(result.stdout or result.stderr).strip()!r}'
        )
    return match.group(1)


def version_build(version: str) -> str:
    if VERSION_RE.fullmatch(version) is None:
        raise RuntimeError(f'invalid four-part version: {version!r}')
    return version.rsplit('.', 1)[0]


def check_source(root: Path = ROOT) -> None:
    # Existing contamination is a separate condition from preventing new bytecode.
    for directory in ('components', 'catalog', 'recipes', 'schemas', 'scripts', 'tests'):
        for path in (root / directory).rglob('*'):
            if path.name == '__pycache__' or path.suffix in {'.pyc', '.pyo'}:
                raise RuntimeError(f'pre-existing generated source contamination: {path}')
    for ignored in (False, True):
        args = ['git', '-C', str(root), 'ls-files', '--others', '--exclude-standard', '-z']
        if ignored:
            args.append('--ignored')
        undeclared = subprocess.check_output([*args, '--', 'components', 'catalog', 'recipes', 'schemas'])
        if undeclared:
            raise RuntimeError('undeclared source material: ' + os.fsdecode(undeclared.split(b'\0')[0]))
    from composer_core import load_source_state
    load_source_state()  # canonical schema, tracked authority, closure and graph validator


def check_browser(driver: Path) -> None:
    if not driver.is_absolute() or not driver.is_file():
        raise RuntimeError('CHROMEWEBDRIVER must name an existing absolute regular file')
    chrome = command_version('google-chrome')
    actual = command_version(driver)
    if version_build(chrome) != version_build(actual):
        raise RuntimeError(f'browser/driver build mismatch: chrome={chrome}, driver={actual}')
    os.environ['CHROMEWEBDRIVER'] = str(driver)
    sys.path.insert(0, str(ROOT / 'tests/fixtures/webapp_browser'))
    from browser_probe import _WebDriverSession
    # One minimal launch; phase 0 does not retry semantic failures.
    with _WebDriverSession() as browser:
        browser.navigate('data:text/html,<title>composition-phase-zero</title>')
        if browser.execute('return document.title') != 'composition-phase-zero':
            raise RuntimeError('minimal browser launch did not reach its document')
    print(f'COMPOSITION_BROWSER_PREFLIGHT chrome={chrome} driver={actual}', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path)
    args = parser.parse_args()
    if not (3, 11) <= sys.version_info[:2] <= (3, 14):
        raise RuntimeError('CPython 3.11–3.14 required')
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
    check_source()
    if args.driver:
        check_browser(args.driver)
    print('COMPOSITION_PHASE_ZERO_PASS', flush=True)


if __name__ == '__main__':
    main()
