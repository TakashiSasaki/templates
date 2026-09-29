#!/usr/bin/env python3
"""Resolve configured branches once and produce a self-contained publication.

No consumer checkout, adoption PR, controller revision or credentials are needed.
Use --source NAME=CHECKOUT to exercise committed local candidates without pushing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integration.materialize_publication_assets import materialize_publication
from integration.qualification import qualify
from publication_bundle.contract import BundleError, read_json, SHA, valid_providers

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=None):
    return subprocess.check_output(['git', *map(str, args)], cwd=cwd, text=True, stderr=subprocess.PIPE).strip()


def load_sources(path):
    data = read_json(path)
    if data.get('schema_version') != 3 or not re.fullmatch(r'[\w.-]+/[\w.-]+', data.get('repository', '')):
        raise BundleError('publication-sources.json requires schema 3 and owner/repository')
    sources = data.get('publications')
    if not isinstance(sources, dict) or not valid_providers({key: '0'*40 for key in sources}, 5):
        raise BundleError('publication sources must name independent provider authorities')
    for name, source in sources.items():
        if not isinstance(source, dict) or set(source) != {'ref'} or not isinstance(source['ref'], str):
            raise BundleError(f'{name} must select one branch ref')
        git('check-ref-format', 'refs/heads/' + source['ref'])
    return data


def resolve_sources(config, overrides):
    unknown = set(overrides) - set(config['publications'])
    if unknown:
        raise BundleError('unconfigured providers: ' + ', '.join(sorted(unknown)))
    remote = 'https://github.com/' + config['repository'] + '.git'
    branches = {name: item['ref'] for name, item in config['publications'].items() if name not in overrides}
    refs = {}
    if branches:
        output = git('ls-remote', '--heads', remote, *('refs/heads/' + ref for ref in branches.values()))
        refs = {ref: sha for sha, ref in (line.split() for line in output.splitlines())}
    result = {}
    for name in sorted(config['publications']):
        if name in overrides:
            source = str(Path(overrides[name]).resolve(strict=True))
            revision = git('rev-parse', 'HEAD', cwd=source)
        else:
            source = remote
            revision = refs.get('refs/heads/' + branches[name], '')
        if not SHA.fullmatch(revision):
            raise BundleError(f'cannot resolve {name} to a commit')
        result[name] = (source, revision)
    return result


def verify_independence(checkouts):
    roots = {}
    for name, checkout in checkouts.items():
        roots[name] = set(git('rev-list', '--max-parents=0', 'HEAD', cwd=checkout).splitlines())
    for name, ancestors in roots.items():
        for other, other_ancestors in roots.items():
            if name < other and ancestors & other_ancestors:
                raise BundleError(f'authority histories overlap: {name}, {other}')


def publish(output, overrides):
    config = load_sources(ROOT / 'publication-sources.json')
    sources = resolve_sources(config, overrides)
    with tempfile.TemporaryDirectory(prefix='integration-inputs-') as temporary:
        checkouts = {}
        for name, (source, revision) in sources.items():
            checkout = Path(temporary) / name
            git('clone', '--quiet', '--no-checkout', source, checkout)
            git('checkout', '--quiet', '--detach', revision, cwd=checkout)
            checkouts[name] = checkout
        verify_independence({'integration': ROOT, **checkouts})
        for name, checkout in checkouts.items():
            materialize_publication(checkout, name)
        return qualify(root=ROOT, provider_roots=checkouts,
                       provider_revisions={name: revision for name, (_, revision) in sources.items()},
                       producer_revision=git('rev-parse', 'HEAD', cwd=ROOT),
                       repository=config['repository'], output=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', action='append', default=[], metavar='NAME=CHECKOUT')
    args = parser.parse_args()
    overrides = {}
    for value in args.source:
        name, separator, checkout = value.partition('=')
        if not separator or not checkout or name in overrides:
            parser.error('--source requires a unique NAME=CHECKOUT')
        overrides[name] = checkout
    try:
        result = publish(args.output, overrides)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Publication failed: {exc}\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
