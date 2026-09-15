"""Disposable local evidence, bound to source bytes, runtime and artifact bytes.

Never consumed by remote CI or review acceptance. The caller holds the entry lock
for the full operation; failed or interrupted stages cannot publish success.
"""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import time

SCHEMA = 1


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def key(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def file_identity(path: Path) -> dict:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise ValueError(f'capsule input must not be a symlink: {path}')
    if not stat.S_ISREG(mode):
        raise ValueError(f'capsule input must be a regular file: {path}')
    return {'sha256': digest(path.read_bytes()), 'executable': bool(mode & 0o111)}


def source_identity(root: Path) -> dict:
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args])
    paths = set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')) - {b''}
    # Provider materialization can create ignored but semantically relevant inputs.
    for directory in ('generated', 'artifacts'):
        if (root / directory).is_dir():
            paths.update(os.fsencode(p.relative_to(root)) for p in (root / directory).rglob('*') if not p.is_dir())
    catalog_path = root / 'docs' / 'publication-catalog.json'
    if catalog_path.is_file():
        # Publication catalogs are the generic authority for provider inputs.
        # Include declared ignored inputs wherever the provider places them;
        # this does not interpret any provider-specific generator semantics.
        from scripts.publication_contract import (
            PublicationContractError,
            load_publication_catalog,
            read_json_object,
            resolve_without_symlinks,
        )
        version = read_json_object(catalog_path, 'publication catalog').get('schema_version')
        if version == 3:
            catalog = load_publication_catalog(root, validate_sources=False)
        elif version == 4:
            from scripts.publication_contract_v4 import parse_publication_catalog_v4
            catalog = parse_publication_catalog_v4(catalog_path)
        else:
            raise PublicationContractError('publication catalog schema must be 3 or 4')
        declared = [document.source for document in catalog.documents]
        declared.extend(asset.source for asset in catalog.assets)
        if catalog.glossary_source is not None:
            declared.append(catalog.glossary_source)
        for relative in declared:
            path = resolve_without_symlinks(root, relative, 'capsule publication input')
            if path.is_dir():
                paths.update(
                    os.fsencode(item.relative_to(root))
                    for item in path.rglob('*')
                    if not item.is_dir()
                )
            else:
                paths.add(os.fsencode(relative))
    files = {}
    for raw in sorted(paths):
        relative = os.fsdecode(raw)
        path = root / relative
        files[relative] = file_identity(path) if path.exists() or path.is_symlink() else None
    return {'revision': git('rev-parse', 'HEAD').decode().strip(), 'files': key(files)}


def input_identity(roots: dict[str, Path]) -> dict:
    names = [line.split('==')[0] for line in (roots['site'] / 'requirements-build.lock').read_text().splitlines()
             if '==' in line and not line.startswith('#')]
    return {'schema_version': SCHEMA,
            'sources': {name: source_identity(root) for name, root in sorted(roots.items())},
            'runtime': {'python': platform.python_version(), 'implementation': platform.python_implementation(),
                        'platform': platform.platform(),
                        'packages': sorted([name, importlib.metadata.version(name)] for name in names)}}


def artifact_digest(root: Path) -> str:
    if not (root / 'index.html').is_file():
        raise ValueError('capsule artifact is missing index.html')
    return key({p.relative_to(root).as_posix(): file_identity(p)
                for p in sorted(root.rglob('*')) if not p.is_dir() or p.is_symlink()})


class Capsule:
    def __init__(self, root: Path, inputs: dict):
        self.inputs = inputs
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f'capsule root must be a regular directory: {root}')
        self.root = root / key(inputs)
        try:
            self.root.mkdir()
        except FileExistsError:
            pass
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError(f'capsule entry must be a regular directory: {self.root}')
        self.record = self.root / 'result.json'
        self.artifact = self.root / 'build/site'

    @contextmanager
    def locked(self):
        with (self.root / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield self

    def read(self) -> dict:
        if not self.record.exists():
            return {'schema_version': SCHEMA, 'inputs': self.inputs, 'stages': {}}
        data = json.loads(self.record.read_text())
        if data.get('schema_version') != SCHEMA or data.get('inputs') != self.inputs:
            raise ValueError('stale or mismatched capsule identity')
        return data

    def write(self, data: dict) -> None:
        temporary = self.record.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')
        temporary.replace(self.record)

    def verify_artifact(self) -> None:
        expected = self.read()['stages'].get('build', {}).get('artifact_digest')
        if expected is None or artifact_digest(self.artifact) != expected:
            raise ValueError('missing, stale or modified capsule artifact')

    def stage(self, name: str, operation, *, artifact: bool = False, reuse: bool = True):
        data = self.read()
        if artifact:
            self.verify_artifact()
        previous = data['stages'].get(name, {})
        if reuse and previous.get('result') == 'success':
            if name == 'build':
                self.verify_artifact()
            print(f'LOCAL_CAPSULE stage={name} reuse=hit wait_seconds=0', flush=True)
            return
        data['stages'][name] = {'result': 'running', 'attempt': previous.get('attempt', 0) + 1}
        self.write(data)
        start = time.monotonic()
        try:
            operation()
            if name == 'build':
                data['stages'][name]['artifact_digest'] = artifact_digest(self.artifact)
            elif artifact:
                self.verify_artifact()
            data['stages'][name]['result'] = 'success'
        except BaseException:
            data['stages'][name]['result'] = 'failure'
            raise
        finally:
            data['stages'][name]['seconds'] = time.monotonic() - start
            self.write(data)
