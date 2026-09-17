"""Project machine discovery from Site roles and the selected Integration Bundle."""
import copy
from pathlib import Path
from publication_bundle.contract import read_json,canonical,BundleError
from site_renderer.github import github_tree_url


def project(template,bundle):
    result=copy.deepcopy(template)
    if result.get('schema_version')!=6 or set(result['authorities'])!={'composition','policy','integration','site'}:
        raise BundleError('invalid four-authority discovery template')
    result['integration_source']={k:bundle[k] for k in ('schema_version','identity','content_digest','producer','providers')}
    for name,revision in bundle['providers'].items():
        if name not in result['authorities']:raise BundleError('unknown discovery authority')
        result['authorities'][name]['publication_revision']=revision
        result['authorities'][name]['canonical_repository_url']=github_tree_url(result['repository'], revision)
    result['authorities']['integration']['revision']=bundle['producer']['revision']
    return result


def write(site_root,docs_root,bundle):
    output=project(read_json(site_root/'agent.json'),bundle)
    (docs_root/'agent.json').write_bytes(canonical(output))
    (docs_root/'schemas').mkdir(exist_ok=True)
    (docs_root/'schemas/agent-bootstrap.schema.json').write_bytes((site_root/'schemas/agent-bootstrap.schema.json').read_bytes())
    from scripts.render_reference_consumer import project as reference
    (docs_root/'reference-consumer.json').write_bytes(canonical(reference(site_root)))
