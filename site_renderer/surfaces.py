"""Site-owned presentation: consumer and maintainer surfaces over semantic data."""
from __future__ import annotations

import copy
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

from publication_bundle.contract import BundleError, read_json, safe_path
from publication_bundle.markdown import _rewrite_markdown
from publication_bundle.paths import public_path, audience_routes


def project(site_root, bundle):
    settings = read_json(site_root / 'surfaces.json')
    if settings.get('schema_version') != 1:
        raise BundleError('unsupported Site surface configuration')
    documents = read_json(bundle / 'documents.json')
    translations = copy.deepcopy(read_json(bundle / 'translation-publication.json'))
    coverage = copy.deepcopy(read_json(bundle / 'translation-availability.json'))
    relocations = {}
    for document in documents:
        patterns = settings['maintainer_documents'].get(document['publication'], [])
        audience = 'maintain' if any(fnmatchcase(document['document'], p) for p in patterns) else 'use'
        original = document['destination']
        document['destination'] = audience + '/' + original
        document['primary_audience'] = audience
        document['additional_audiences'] = []
        relocations[original] = document['destination']
    for entry in translations['translations']:
        old = entry['translation_destination']
        entry['canonical_destination'] = relocations[entry['canonical_destination']]
        entry['translation_destination'] = entry['language'] + '/' + entry['canonical_destination']
        relocations[old] = entry['translation_destination']
    for entry in coverage['records']:
        entry['canonical_destination'] = relocations[entry['canonical_destination']]

    catalog = read_json(site_root / 'docs/publication-catalog.json')
    for item in catalog['documents']:
        key = item['id']
        audience = 'use' if key in settings['consumer_guides'] else 'maintain'
        destination = settings['routes'].get(key, f'{audience}/site/{key}.md')
        safe_path(destination)
        if item.get('home'):
            destination = 'index.md'
        source = site_root / safe_path(item['source'])
        title = next((line[2:].strip() for line in source.read_text(encoding='utf-8').splitlines()
                      if line.startswith('# ')), key.replace('-', ' ').capitalize())
        documents.append(dict(publication='site', document=key, source=item['source'],
                              destination=destination, title=title, slot=True,
                              primary_audience=audience,
                              additional_audiences=['use'] if item.get('home') else []))
    destinations = [d['destination'] for d in documents]
    if len(set(destinations)) != len(destinations):
        raise BundleError('duplicate Site surface destination')
    nav = {audience: [] for audience in ('use', 'maintain')}
    for audience, tree in nav.items():
        pages = [d for d in documents if d['primary_audience'] == audience and d['destination'] != 'index.md']
        overview = next((d for d in pages if d['destination'] == audience + '/index.md'), None)
        if overview is None:
            raise BundleError('each Site surface requires its own overview')
        node = lambda d: {key: d[key] for key in ('title', 'publication', 'document', 'destination')}
        tree.append(node(overview))
        for name in ['site', *sorted({d['publication'] for d in pages} - {'site'})]:
            children = [node(d) for d in pages if d['publication'] == name and d != overview]
            if children:
                tree.append({'title': 'Guides' if name == 'site' else name.capitalize(), 'children': children})

    def runtime_nodes(nodes):
        return [({'title': n['title'], 'children': runtime_nodes(n['children'])} if 'children' in n else
                 {'title': n['title'], 'destination': n['destination'], 'href': public_path(n['destination'])})
                for n in nodes]

    runtime = {'schema_version': 1, 'audiences': ['use', 'maintain'],
        'documents': {d['destination']: {'destination': d['destination'],
            'key': d['publication'] + ':' + d['document'], 'title': d['title'],
            'primary': d['primary_audience'], 'audiences': [d['primary_audience'], *d['additional_audiences']],
            'is_landing': d['destination'] == 'index.md'} for d in documents},
        'routes': audience_routes(destinations), 'navigation': {a: runtime_nodes(nodes) for a, nodes in nav.items()},
        'overviews': {'use': '/use/', 'maintain': '/maintain/'}, 'landing_destination': 'index.md'}
    titles = {'Use templates', 'Maintain templates'}
    def collect(nodes):
        for n in nodes:
            titles.add(n['title'])
            collect(n.get('children', []))
    for nodes in nav.values():
        collect(nodes)
    labels = {'schema_version': 1, 'canonical_language': 'en', 'locales': [
        {'language': 'ja', 'labels': [{'id': f'label-{i}', 'canonical': title,
             'localized': {'Use templates': '利用する', 'Maintain templates': '整備する'}.get(title, title)}
             for i, title in enumerate(sorted(titles))]}]}
    return documents, {'schema_version': 1, 'navigation': nav, 'audience_runtime': runtime,
                       'locale_labels': labels}, relocations, translations, coverage


def copy_publication(bundle, docs, manifest, relocations):
    targets = {PurePosixPath(old): PurePosixPath(new) for old, new in relocations.items()}
    assets = []
    for name in manifest['files']:
        if not name.startswith('publication/'):
            continue
        original = name.removeprefix('publication/')
        destination = relocations.get(original, original)
        target = docs / safe_path(destination)
        if target.exists():
            raise BundleError('publication destination collision: ' + destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((bundle / name).read_bytes())
        if original not in relocations:
            assets.append((PurePosixPath(original), PurePosixPath(original), False))
    for original, destination in relocations.items():
        target = docs / destination
        text, _ = _rewrite_markdown(target.read_text(encoding='utf-8'),
            source_document=PurePosixPath(original), site_document=PurePosixPath(destination),
            document_targets=targets, asset_rules=assets, docs_root=docs, publication='site-presentation',
            site_source_paths=None)
        target.write_text(text, encoding='utf-8')
