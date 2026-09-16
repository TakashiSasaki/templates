"""Small rendering-contract fixture; no provider semantic producer is executed."""
from pathlib import Path
from publication_bundle.contract import canonical,digest,inventory
from tests.test_publication_bundle import fixture as legacy_fixture,PROVIDERS
PRODUCER={'authority':'integration','revision':'a'*40}
def fixture(root):
    legacy_fixture(root)
    (root/'provenance.json').write_bytes(canonical({'schema_version':1,'producer':PRODUCER,'providers':PROVIDERS}))
    return root

def finish(root):
    files=inventory(root)
    data={'schema_version':2,'producer':PRODUCER,'providers':PROVIDERS,'configuration_digest':'d'*64,'files':files,'content_digest':digest(canonical(files))}
    data['identity']=digest(canonical(data));(root/'bundle.json').write_bytes(canonical(data));return data

def lock(manifest):
    return {'schema_version':1,'repository':'TakashiSasaki/templates','revision':manifest['producer']['revision'],'bundle_schema':2,'bundle_identity':manifest['identity'],'content_digest':manifest['content_digest']}
