"""Publication Bundle v1 integrity contract; independent of either implementation."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1
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


def seal(root, *, producer, providers, configuration_digest):
    if (root / 'bundle.json').exists():
        raise BundleError('Bundle already sealed')
    files = inventory(root)
    data = dict(schema_version=SCHEMA_VERSION, producer=producer, providers=providers,
                configuration_digest=configuration_digest, files=files,
                content_digest=digest(canonical(files)))
    data['identity'] = digest(canonical(data))
    (root / 'bundle.json').write_bytes(canonical(data))
    validate(root, expected_producer=producer, expected_providers=providers)
    return data


def validate(root, *, expected_identity=None, expected_producer=None, expected_providers=None):
    root = Path(root)
    data = read_json(regular(root, 'bundle.json'))
    if not isinstance(data, dict) or set(data) != FIELDS or type(data['schema_version']) is not int or data['schema_version'] != SCHEMA_VERSION:
        raise BundleError('unsupported Bundle schema or fields')
    producer, providers = data['producer'], data['providers']
    if (not isinstance(producer, dict) or set(producer) != {'authority', 'revision'}
            or producer['authority'] not in {'site-internal-integration', 'integration'}
            or not isinstance(producer['revision'], str) or not SHA.fullmatch(producer['revision'])):
        raise BundleError('invalid producer identity')
    if (not isinstance(providers, dict) or set(providers) != {'composition', 'policy'}
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
    repos = read_json(regular(root, 'provider-repositories.json'))
    if not isinstance(repos, dict) or set(repos) != set(providers):
        raise BundleError('incomplete provider source models')
    for name, model in repos.items():
        if not isinstance(model, dict) or model.get('revision') != providers[name]:
            raise BundleError('repository model revision mismatch')
    graph = read_json(regular(root, 'guided-navigation.json'))
    if not isinstance(graph, dict) or {p.get('name'):p.get('revision') for p in graph.get('providers', [])} != providers:
        raise BundleError('guided graph provenance mismatch')
    from publication_bundle.source_models import validate_sources
    from publication_bundle.graph import load_graph, IndexNavigationViewerError
    from publication_bundle.glossary import load_model, GlossaryViewerError
    try:
        glossary = load_model(root / 'glossary.json')
        for term in glossary['terms']:
            authority = term['provider']
            if term['source_revision'] != (producer['revision'] if authority == 'site' else providers.get(authority)):
                raise BundleError('glossary source revision mismatch')
        from publication_bundle.locales import load_overlays
        load_overlays(root / 'guided-locales.json', graph)
        from publication_bundle.navigation import validate_navigation
        validate_navigation(root, navigation, documents)
        load_graph(root / 'guided-navigation.json')
        repository = graph.get('repository')
        for name, model in repos.items():
            validate_sources(name, model, repository)
            wanted = {d['source']: d['destination'] for d in documents if d['publication'] == name}
            if model['published'] != wanted:
                raise BundleError('source/publication destination mismatch')
    except (ValueError, RuntimeError, KeyError, TypeError, UnicodeError) as exc:
        raise BundleError('invalid Bundle read model: ' + str(exc)) from exc
    from publication_bundle.translations import validate_translations
    validate_translations(root, read_json(root / 'translation-availability.json'),
                          read_json(root / 'translation-publication.json'), providers, documents, repos)
    return data
