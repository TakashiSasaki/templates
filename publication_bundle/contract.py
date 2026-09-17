"""Publication Bundle v3/v4 integrity contract; independent of either implementation."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 3
SCHEMA_VERSION_V4 = 4
SHA = re.compile(r'^[0-9a-f]{40}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')
MAX_FILES = 50000
MAX_BYTES = 1024 * 1024 * 1024
MODELS = ('documents.json', 'navigation.json', 'translation-availability.json',
          'translation-publication.json', 'reader-navigation-runtime.json',
          'glossary.json', 'guided-navigation.json', 'guided-locales.json',
          'provenance.json')
MODEL_SET = frozenset(MODELS)
PROVIDER_SETS = {
    3: frozenset({'composition', 'policy'}),
    4: frozenset({'modeling', 'composition', 'policy'}),
}
PROVIDER_ORDERS = {
    3: ('composition', 'policy'),
    4: ('modeling', 'composition', 'policy'),
}
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


def _normalize_expected_publication_paths(paths):
    if paths is None:
        raise BundleError('qualified publication output set is required')
    result = set()
    for value in paths:
        if isinstance(value, PurePosixPath):
            value = value.as_posix()
        path = safe_path(value)
        if len(path.parts) < 2 or path.parts[0] != 'publication':
            raise BundleError('qualified publication output must be under publication/: ' + str(value))
        result.add(path.as_posix())
    return frozenset(result)


def _validate_closed_inventory(files, expected_publication_paths=None):
    """Require the v3 inventory to be an exact semantic/output closure.

    The producer derives ``expected_publication_paths`` from its authoritative
    document, asset, and translation declarations.  ``bundle.json.files`` is
    then only the authenticated record of that already-qualified set; it does
    not authorize an arbitrary file merely because it was present during
    sealing.
    """
    for path in files:
        if path not in MODEL_SET and not path.startswith('publication/'):
            raise BundleError('Bundle contains undeclared non-publication payload: ' + path)
    if expected_publication_paths is None:
        return
    expected = MODEL_SET | set(expected_publication_paths)
    actual = set(files)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise BundleError(
            'publication output closure mismatch: '
            f'missing={missing} extra={extra}'
        )


def seal(root, *, producer, providers, configuration_digest, expected_publication_paths,
         schema_version=None):
    if (root / 'bundle.json').exists():
        raise BundleError('Bundle already sealed')
    expected_publication_paths = _normalize_expected_publication_paths(
        expected_publication_paths
    )
    files = inventory(root)
    _validate_closed_inventory(files, expected_publication_paths)
    if schema_version is None:
        schema_version = SCHEMA_VERSION
    if schema_version not in PROVIDER_SETS or set(providers) != PROVIDER_SETS[schema_version]:
        raise BundleError('provider set does not match Bundle schema')
    data = dict(schema_version=schema_version, producer=producer, providers=providers,
                configuration_digest=configuration_digest, files=files,
                content_digest=digest(canonical(files)))
    data['identity'] = digest(canonical(data))
    (root / 'bundle.json').write_bytes(canonical(data))
    validate(root, expected_producer=producer, expected_providers=providers,
             expected_publication_paths=expected_publication_paths)
    return data


def validate(root, *, expected_identity=None, expected_producer=None,
             expected_providers=None, expected_publication_paths=None):
    root = Path(root)
    if expected_publication_paths is not None:
        expected_publication_paths = _normalize_expected_publication_paths(
            expected_publication_paths
        )
    data = read_json(regular(root, 'bundle.json'))
    if (not isinstance(data, dict) or set(data) != FIELDS
            or type(data['schema_version']) is not int
            or data['schema_version'] not in PROVIDER_SETS):
        raise BundleError('unsupported Bundle schema or fields')
    schema_version = data['schema_version']
    producer, providers = data['producer'], data['providers']
    if (not isinstance(producer, dict) or set(producer) != {'authority', 'revision'}
            or producer['authority'] not in {'site-internal-integration', 'integration'}
            or not isinstance(producer['revision'], str) or not SHA.fullmatch(producer['revision'])):
        raise BundleError('invalid producer identity')
    if (not isinstance(providers, dict) or set(providers) != PROVIDER_SETS[schema_version]
            or any(not isinstance(v, str) or not SHA.fullmatch(v) for v in providers.values())):
        raise BundleError('invalid provider identities')
    for field in ('configuration_digest', 'content_digest', 'identity'):
        if not isinstance(data[field], str) or not DIGEST.fullmatch(data[field]):
            raise BundleError('invalid ' + field)
    unsigned = {k: v for k, v in data.items() if k != 'identity'}
    if digest(canonical(unsigned)) != data['identity']:
        raise BundleError('Bundle identity mismatch')
    if expected_identity is not None and data['identity'] != expected_identity:
        raise BundleError('unexpected Bundle identity')
    if expected_producer is not None and producer != expected_producer:
        raise BundleError('producer revision mismatch')
    if expected_providers is not None and providers != expected_providers:
        raise BundleError('provider revision mismatch')
    files = data['files']
    if not isinstance(files, dict) or not set(MODELS) <= files.keys():
        raise BundleError('incomplete Bundle models')
    _validate_closed_inventory(files, expected_publication_paths)
    for path, record in files.items():
        safe_path(path)
        if path == 'bundle.json' or not isinstance(record, dict) or set(record) != {'size', 'sha256'} or type(record['size']) is not int or record['size'] < 0 or not isinstance(record['sha256'], str) or not DIGEST.fullmatch(record['sha256']):
            raise BundleError('invalid file inventory')
    if inventory(root) != files or digest(canonical(files)) != data['content_digest']:
        raise BundleError('Bundle payload digest/inventory mismatch')
    provenance = read_json(regular(root, 'provenance.json'))
    if provenance != {'schema_version': 1, 'producer': producer, 'providers': providers}:
        raise BundleError('Bundle provenance mismatch')
    documents = read_json(regular(root, 'documents.json'))
    if not isinstance(documents, list):
        raise BundleError('documents must be an array')
    keys, destinations = set(), set()
    for doc in documents:
        if not isinstance(doc, dict) or not {'publication','document','destination','source','slot'} <= doc.keys():
            raise BundleError('invalid document record')
        if doc['publication'] not in {'site', *providers} or not isinstance(doc['document'], str):
            raise BundleError('invalid document authority')
        key = (doc['publication'], doc['document'])
        destination = safe_path(doc['destination']).as_posix()
        safe_path(doc['source'])
        if key in keys or destination in destinations:
            raise BundleError('duplicate document/destination')
        keys.add(key); destinations.add(destination)
        if type(doc['slot']) is not bool or doc['slot'] != (doc['publication'] == 'site'):
            raise BundleError('invalid Site slot')
        if not doc['slot']:
            regular(root, 'publication/' + destination)
    navigation = read_json(regular(root, 'navigation.json'))
    if not isinstance(navigation, dict) or not isinstance(navigation.get('navigation'), dict):
        raise BundleError('invalid navigation model')
    def walk(nodes):
        if not isinstance(nodes, list):raise BundleError('navigation nodes must be arrays')
        for node in nodes:
            if not isinstance(node, dict):raise BundleError('invalid navigation node')
            if 'children' in node:walk(node['children'])
            elif (node.get('publication'), node.get('document')) not in keys or node.get('destination') not in destinations:
                raise BundleError('navigation references absent document')
    for nodes in navigation['navigation'].values():walk(nodes)
    graph = read_json(regular(root, 'guided-navigation.json'))
    if not isinstance(graph, dict) or {p.get('name'):p.get('revision') for p in graph.get('providers', [])} != providers:
        raise BundleError('guided graph provenance mismatch')
    from publication_bundle.graph import load_graph, validate_provider_graph
    from publication_bundle.glossary import load_model, GlossaryViewerError
    try:
        glossary = load_model(root / 'glossary.json')
        for term in glossary['terms']:
            authority = term['provider']
            if term['source_revision'] != (producer['revision'] if authority == ('integration' if producer['authority']=='integration' else 'site') else providers.get(authority)):
                raise BundleError('glossary source revision mismatch')
        from publication_bundle.locales import load_overlays
        load_overlays(root / 'guided-locales.json', graph)
        from publication_bundle.navigation import validate_navigation
        validate_navigation(root, navigation, documents)
        accepted_graph = load_graph(root / 'guided-navigation.json', provider_order=PROVIDER_ORDERS[schema_version])
        for provider in accepted_graph['providers']:
            validate_provider_graph(provider, provider_order=PROVIDER_ORDERS[schema_version])
    except (ValueError, RuntimeError, KeyError, TypeError, UnicodeError) as exc:
        raise BundleError('invalid Bundle read model: ' + str(exc)) from exc
    from publication_bundle.translations import validate_translations
    validate_translations(root, read_json(root / 'translation-availability.json'),
                          read_json(root / 'translation-publication.json'), providers, documents)
    return data
