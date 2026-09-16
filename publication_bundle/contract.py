"""Publication Bundle v2 wire-integrity primitives for the Site consumer."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 2
SHA = re.compile(r'^[0-9a-f]{40}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')
MAX_FILES = 50000
MAX_BYTES = 1024 * 1024 * 1024
MODELS = ('documents.json', 'navigation.json', 'translation-availability.json',
          'translation-publication.json', 'reader-navigation-runtime.json',
          'glossary.json', 'guided-navigation.json', 'guided-locales.json',
          'provider-repositories.json', 'provenance.json')
FIELDS = {'schema_version', 'producer', 'providers', 'configuration_digest',
          'files', 'content_digest', 'identity'}


class BundleError(ValueError):
    """Malformed, incomplete, unsafe or incorrectly bound publication input."""


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BundleError('duplicate JSON member: ' + key)
            result[key] = value
        return result
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(BundleError('nonfinite JSON')))
    except (OSError, UnicodeError, ValueError) as exc:
        raise BundleError(f'invalid JSON at {path}: {exc}') from exc


def safe_path(value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise BundleError('invalid Bundle path')
    p = PurePosixPath(value)
    if p.is_absolute() or p.as_posix() != value or any(x in {'.', '..', '.git'} for x in p.parts):
        raise BundleError('unsafe Bundle path: ' + value)
    return p


def regular(root, relative):
    p = safe_path(relative)
    if any(p.is_symlink() for p in (root,*root.parents)) or not root.is_dir():
        raise BundleError('Bundle root must be a directory without symlinks')
    current = root
    for part in p.parts:
        current /= part
        if current.is_symlink():
            raise BundleError('Bundle path traverses a symlink')
    if not current.is_file():
        raise BundleError('missing declared Bundle file: ' + relative)
    return current


def inventory(root):
    result = {}
    total = 0
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise BundleError('Bundle contains a symlink')
        if p.is_dir():
            continue
        if not p.is_file():
            raise BundleError('Bundle contains a special file')
        relative = p.relative_to(root).as_posix()
        safe_path(relative)
        if relative == 'bundle.json':
            continue
        size = p.stat().st_size
        total += size
        if total > MAX_BYTES or len(result) >= MAX_FILES:
            raise BundleError('Bundle resource limit exceeded')
        result[relative] = {'size': size, 'sha256': digest(p.read_bytes())}
    return result

