"""One-time P5 provider payload comparison; not a steady-state provider lock."""
from publication_bundle.contract import BundleError, canonical, digest, read_json, validate


def compare(bundle, reference):
    manifest=validate(bundle)
    if manifest['producer']['authority']!='integration':raise BundleError('bootstrap candidate is not Integration-produced')
    if manifest['providers']!=reference['providers']:raise BundleError('bootstrap provider revisions differ')
    expected=reference['equivalent_files']
    actual={p:r for p,r in manifest['files'].items() if p not in {'glossary.json','provenance.json'}}
    if actual!=expected:raise BundleError('bootstrap provider publication/read-model payload drift')
    glossary=read_json(bundle/'glossary.json')
    provider_terms=[t for t in glossary['terms'] if t['provider'] in manifest['providers']]
    if digest(canonical(provider_terms))!=reference['provider_glossary_sha256']:
        raise BundleError('bootstrap provider glossary drift')
    own_terms=[t for t in glossary['terms'] if t['provider']=='integration']
    if sorted(t['id'] for t in own_terms)!=reference['integration_glossary_ids']:
        raise BundleError('bootstrap Integration glossary inventory drift')
    return {'schema_version':1,'site_bundle_identity':reference['site_bundle_identity'],
            'integration_bundle_identity':manifest['identity'],'providers':manifest['providers'],
            'equivalent_file_count':len(actual),'equivalent_files_digest':digest(canonical(actual)),
            'provider_glossary_sha256':reference['provider_glossary_sha256'],
            'permitted_differences':reference['permitted_differences']}
