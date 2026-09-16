"""Site consumption of reviewed Bundle v2: integrity and render-input structure only.

Integration qualifies provider declarations and semantics. Site authenticates the
selected immutable artifact, never parses provider catalogs/manifests or Git blobs.
"""
from pathlib import Path
from publication_bundle.contract import (BundleError, SHA, DIGEST, MODELS, FIELDS,
    canonical, digest, read_json, safe_path, regular, inventory)


def load_lock(path):
    lock=read_json(path)
    if (not isinstance(lock,dict) or set(lock)!={'schema_version','repository','revision','bundle_schema','bundle_identity','content_digest'}
            or type(lock['schema_version']) is not int or lock['schema_version']!=1
            or type(lock['bundle_schema']) is not int or lock['bundle_schema']!=2
            or lock['repository']!='TakashiSasaki/templates'
            or not isinstance(lock['revision'],str) or not SHA.fullmatch(lock['revision'])
            or any(not isinstance(lock[k],str) or not DIGEST.fullmatch(lock[k]) for k in ('bundle_identity','content_digest'))):
        raise BundleError('invalid immutable Integration release lock')
    return lock


def validate_locked(root, lock):
    result=validate(root,expected_identity=lock['bundle_identity'],expected_producer={'authority':'integration','revision':lock['revision']})
    if result['schema_version']!=lock['bundle_schema'] or result['content_digest']!=lock['content_digest']:
        raise BundleError('Bundle differs from selected Integration contract/content')
    return result


def validate(root, *, expected_identity=None, expected_producer=None, expected_providers=None):
    root = Path(root)
    data = read_json(regular(root, 'bundle.json'))
    if not isinstance(data, dict) or set(data) != FIELDS or type(data['schema_version']) is not int or data['schema_version'] != 2:
        raise BundleError('unsupported Bundle schema or fields')
    producer, providers = data['producer'], data['providers']
    if (not isinstance(producer, dict) or set(producer) != {'authority', 'revision'}
            or producer['authority'] != 'integration'
            or not isinstance(producer['revision'], str) or not SHA.fullmatch(producer['revision'])):
        raise BundleError('invalid producer identity')
    if (not isinstance(providers, dict) or not providers
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
    validate_translation_state(root, documents, providers)
    return data


def validate_translation_state(root, documents, providers):
    coverage=read_json(regular(root,'translation-availability.json'))
    publication=read_json(regular(root,'translation-publication.json'))
    if (not isinstance(coverage,dict) or coverage.get('schema_version')!=1
            or coverage.get('canonical_language')!='en' or coverage.get('surface')!='reader'
            or not isinstance(coverage.get('records'),list)
            or not isinstance(coverage.get('languages'),list)
            or len(set(coverage['languages']))!=len(coverage['languages'])):
        raise BundleError('invalid Integration translation state')
    if (not isinstance(publication,dict) or publication.get('schema_version')!=1
            or publication.get('canonical_language')!='en' or not isinstance(publication.get('translations'),list)):
        raise BundleError('invalid Integration translation publication')
    pages={(d['publication'],d['document']):d for d in documents if not d['slot']}
    expected={};seen=set();counts=dict(current=0,stale=0,missing=0);languages={lang:dict(counts) for lang in coverage['languages']}
    for r in coverage['records']:
        if not isinstance(r,dict) or not {'publication','document','language','canonical_source','canonical_destination','status'}<=r.keys():
            raise BundleError('incomplete Integration translation record')
        key=(r['publication'],r['document']);doc=pages.get(key);lang=r['language'];status=r['status']
        if (doc is None or lang not in languages or status not in counts or (*key,lang) in seen
                or r['canonical_source']!=doc['source'] or r['canonical_destination']!=doc['destination']):
            raise BundleError('misbound Integration translation record')
        safe_path(lang);seen.add((*key,lang));counts[status]+=1;languages[lang][status]+=1
        if status!='missing':
            if not {'translation_source','canonical_blob_sha','current_blob_sha'}<=r.keys():raise BundleError('missing translation evidence')
            safe_path(r['translation_source'])
            if any(not isinstance(r[k],str) or not SHA.fullmatch(r[k]) for k in ('canonical_blob_sha','current_blob_sha')):raise BundleError('invalid translation evidence')
            expected[(r['publication'],lang,r['canonical_destination'])]=r
        elif {'translation_source','canonical_blob_sha','current_blob_sha'}&r.keys():raise BundleError('missing translation has declared evidence')
    if counts!=coverage.get('summary') or languages!=coverage.get('by_language'):raise BundleError('inconsistent translation summary')
    if seen!={(p,d,lang) for p,d in pages for lang in languages}:raise BundleError('incomplete translation coverage projection')
    actual=set();destinations=set()
    for r in publication['translations']:
        if not isinstance(r,dict) or set(r)!={'publication','language','canonical_destination','translation_destination'}:raise BundleError('invalid translation route')
        key=(r['publication'],r['language'],r['canonical_destination'])
        target=safe_path(r['translation_destination']).as_posix()
        if key not in expected or key in actual or target in destinations or target in {d['destination'] for d in documents}:raise BundleError('misbound/duplicate translation route')
        actual.add(key);destinations.add(target);regular(root,'publication/'+target)
    if actual!=set(expected):raise BundleError('incomplete current/stale derivative publication')
