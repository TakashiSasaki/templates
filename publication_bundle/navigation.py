"""Consistency of reader navigation and its machine projections."""
from pathlib import PurePosixPath
from types import SimpleNamespace
from publication_bundle.contract import BundleError, read_json
from publication_bundle.paths import public_path
from publication_bundle.authority_content.reader_navigation_locales import load_overlays, build_runtime_map


def validate_navigation(root, model, documents):
    if set(model) != {'schema_version','navigation','locale_labels','audience_runtime'} or type(model['schema_version']) is not int or model['schema_version'] != 1:
        raise BundleError('invalid semantic navigation fields')
    audience=model['audience_runtime']
    fields={'schema_version','audiences','documents','routes','navigation','overviews','landing_destination'}
    if not isinstance(audience,dict) or set(audience)!=fields or type(audience['schema_version']) is not int or audience['schema_version']!=1:
        raise BundleError('invalid audience projection fields')
    audiences=audience['audiences']
    if not isinstance(audiences,list) or not audiences or any(not isinstance(a,str) for a in audiences) or len(set(audiences))!=len(audiences) or set(audiences)!=set(model['navigation']):
        raise BundleError('audience projection/navigation mismatch')
    destinations={d['destination']:d for d in documents}
    if set(audience['documents'])!=set(destinations):raise BundleError('audience document closure mismatch')
    for destination,record in audience['documents'].items():
        document=destinations[destination]
        if record['destination']!=destination or record['key']!=document['publication']+':'+document['document'] or record['primary'] not in record['audiences'] or not set(record['audiences'])<=set(audiences):
            raise BundleError('audience document identity mismatch')
    for route,destination in audience['routes'].items():
        if destination not in destinations:raise BundleError('audience route references absent document')
        public=public_path(destination)
        aliases={destination,'/'+destination,public,public+'index.html',public.rstrip('/'),public.rstrip('/')+'.html'}
        if PurePosixPath(destination).name=='index.md':aliases|={public.lstrip('/'),public.strip('/')}
        if destination=='index.md':aliases|={'','index.html','/index.html'}
        if route not in aliases:raise BundleError('audience route identity mismatch')
    def project(nodes):
        return [({'title':n['title'],'children':project(n['children'])} if 'children' in n else
                 {'title':n['title'],'destination':n['destination'],'href':public_path(n['destination'])}) for n in nodes]
    if audience['navigation']!={a:project(nodes) for a,nodes in model['navigation'].items()}:
        raise BundleError('audience navigation differs from semantic model')
    if audience['landing_destination'] not in destinations or set(audience['overviews'])!=set(audiences) or any(route not in audience['routes'] for route in audience['overviews'].values()):
        raise BundleError('invalid audience landing/overview routes')
    # The labels are a public model. Reusing its validator reads no provider source.
    from tempfile import TemporaryDirectory
    from pathlib import Path
    from publication_bundle.contract import canonical
    with TemporaryDirectory() as tmp:
        path=Path(tmp)/'labels.json';path.write_bytes(canonical(model['locale_labels']))
        labels=load_overlays(path,model['navigation'])
    records=read_json(root/'translation-publication.json')['translations']
    records=[SimpleNamespace(**{**r,'canonical_destination':PurePosixPath(r['canonical_destination']),'translation_destination':PurePosixPath(r['translation_destination'])}) for r in records]
    if build_runtime_map(labels,records)!=read_json(root/'reader-navigation-runtime.json'):
        raise BundleError('reader navigation runtime differs from semantic projection')
