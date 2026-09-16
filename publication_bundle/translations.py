"""Validate availability against immutable provider-owned translation declarations."""
import base64
from pathlib import PurePosixPath
from publication_bundle.authority_content.translation_manifest import parse_translation_manifest, TranslationManifestError
from publication_bundle.authority_content.translation_coverage import derive_reader_coverage, TranslationCoverageError
from publication_bundle.contract import BundleError, SHA, safe_path, regular


def validate_translations(root, coverage, publication, providers, documents, repositories):
    keys={(d['publication'],d['document']):d for d in documents if not d['slot']}
    if not isinstance(coverage,dict) or set(coverage)!={'schema_version','canonical_language','surface','languages','summary','by_language','records'} or coverage['schema_version']!=1 or coverage['canonical_language']!='en' or coverage['surface']!='reader':raise BundleError('invalid translation availability model')
    if not isinstance(coverage['languages'],list) or len(set(coverage['languages']))!=len(coverage['languages']) or not all(isinstance(x,str) and x for x in coverage['languages']) or not isinstance(coverage['records'],list):raise BundleError('invalid translation languages/records')
    from publication_bundle.source_models import raw_path
    sources={name:{raw_path(e['path']):e for e in model['entries'] if e['mode'] in {'100644','100755'}} for name,model in repositories.items()}
    def source(provider,path):
        path=safe_path(path).as_posix().encode('utf-8')
        entry=sources.get(provider,{}).get(path)
        if entry is None:raise BundleError('translation source missing from owning provider: '+provider+':'+path.decode())
        return entry
    manifests = {}
    for provider, model in repositories.items():
        entries = {raw_path(e['path']): e for e in model['entries']}
        browser = {raw_path(r['path']): r for r in model['browser']}

        def bound_source(path):
            # Inspect ancestors too: a regular leaf must not hide a symlink,
            # submodule or other non-directory parent in a malformed inventory.
            parts = path.parts
            for count in range(1, len(parts)):
                ancestor = entries.get('/'.join(parts[:count]).encode())
                if ancestor is not None and ancestor['mode'] != '040000':
                    raise BundleError('translation source must not traverse non-directory owning provider path')
            return source(provider, path.as_posix())['object_id']

        path = PurePosixPath('translations/manifest.json')
        # Match the provider contract's optional-manifest semantics. An existing
        # unsafe manifest or ancestor is never treated as absent.
        ancestor = entries.get(b'translations')
        if ancestor is not None and ancestor['mode'] != '040000':
            raise BundleError('translation manifest must not traverse non-directory')
        if b'translations/manifest.json' not in entries:
            continue
        bound_source(path)
        record = browser[b'translations/manifest.json']
        raw = (record['text'].encode('utf-8') if record['viewable'] else
               base64.b64decode(model['nonviewable_blobs'][record['object_id']], validate=True))
        try:
            manifests[provider] = parse_translation_manifest(
                raw.decode('utf-8'), provider + ' translation manifest', source_blob=bound_source)
        except (UnicodeError, TranslationManifestError) as exc:
            raise BundleError(str(exc)) from exc
    publications = {provider: (None, {}, []) for provider in providers}
    pages = []
    for (provider, document), doc in keys.items():
        publications[provider][1][document] = {'source': PurePosixPath(doc['source'])}
        pages.append({**doc, 'destination': PurePosixPath(doc['destination'])})
    try:
        expected_coverage = derive_reader_coverage(manifests, publications, pages)
    except TranslationCoverageError as exc:
        raise BundleError(str(exc)) from exc
    if coverage != expected_coverage:
        raise BundleError('translation availability differs from provider manifest/source identity closure')
    if not isinstance(publication,dict) or set(publication)!={'schema_version','canonical_language','translations'} or publication['schema_version']!=1 or publication['canonical_language']!='en' or not isinstance(publication['translations'],list):raise BundleError('invalid translation publication map')
    expected={(r['publication'],r['language'],r['canonical_destination']) for r in coverage['records'] if r['status']=='current'};actual=set();destinations=set()
    for r in publication['translations']:
        if not isinstance(r,dict) or set(r)!={'publication','language','canonical_destination','translation_destination'}:raise BundleError('invalid derivative record')
        key=(r['publication'],r['language'],r['canonical_destination'])
        if key in actual or key not in expected or r['translation_destination'] in destinations:raise BundleError('duplicate/unqualified derivative')
        actual.add(key);destinations.add(r['translation_destination']);regular(root,'publication/'+safe_path(r['translation_destination']).as_posix())
    if expected!=actual:raise BundleError('missing current derivative')
