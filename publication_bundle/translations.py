"""Availability and derivative-output contracts; never infer provider freshness."""
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
    summary={'current':0,'stale':0,'missing':0};seen=set();per_language={l:dict(summary) for l in coverage['languages']}
    for r in coverage['records']:
        if not isinstance(r,dict):raise BundleError('invalid translation availability record')
        fields={'publication','document','language','canonical_source','canonical_destination','status'}
        if r.get('status') in {'current','stale'}:fields|={'translation_source','canonical_blob_sha','current_blob_sha'}
        if set(r)!=fields or r.get('status') not in summary:raise BundleError('invalid translation availability fields/status')
        key=(r['publication'],r['document']);doc=keys.get(key);identity=(*key,r['language'])
        if doc is None or r['language'] not in per_language or identity in seen or r['canonical_source']!=doc['source'] or r['canonical_destination']!=doc['destination']:raise BundleError('translation availability closure mismatch')
        seen.add(identity)
        canonical=source(r['publication'],r['canonical_source'])
        if r['status']!='missing':
            source(r['publication'],r['translation_source'])
            if r['current_blob_sha']!=canonical['object_id']:raise BundleError('canonical translation identity does not match provider source')
            if any(not isinstance(r[f],str) or not SHA.fullmatch(r[f]) for f in ('canonical_blob_sha','current_blob_sha')):raise BundleError('invalid canonical translation identity')
            if (r['canonical_blob_sha']==r['current_blob_sha']) != (r['status']=='current'):raise BundleError('inconsistent translation freshness evidence')
        summary[r['status']]+=1;per_language[r['language']][r['status']]+=1
    if seen!={(*key,l) for key in keys for l in coverage['languages']} or coverage['summary']!=summary or coverage['by_language']!=per_language:raise BundleError('incomplete translation availability')
    if not isinstance(publication,dict) or set(publication)!={'schema_version','canonical_language','translations'} or publication['schema_version']!=1 or publication['canonical_language']!='en' or not isinstance(publication['translations'],list):raise BundleError('invalid translation publication map')
    expected={(r['publication'],r['language'],r['canonical_destination']) for r in coverage['records'] if r['status']=='current'};actual=set();destinations=set()
    for r in publication['translations']:
        if not isinstance(r,dict) or set(r)!={'publication','language','canonical_destination','translation_destination'}:raise BundleError('invalid derivative record')
        key=(r['publication'],r['language'],r['canonical_destination'])
        if key in actual or key not in expected or r['translation_destination'] in destinations:raise BundleError('duplicate/unqualified derivative')
        actual.add(key);destinations.add(r['translation_destination']);regular(root,'publication/'+safe_path(r['translation_destination']).as_posix())
    if expected!=actual:raise BundleError('missing current derivative')
