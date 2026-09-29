"""Produce semantic publication data, without Site routes, slots or presentation."""
from __future__ import annotations
import argparse
import base64
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

from publication_bundle.contract import BundleError, canonical, digest, seal, valid_providers
from publication_bundle.markdown import _rewrite_markdown
from integration.publication_model import load_catalog, copy_asset, resolve
from integration.publish_translations import publish_translations
from integration.translation_fragment_reconciliation import reconcile_translation_fragments
from integration.translation_link_selection import rewrite_available_localized_links
from integration.translation_coverage import build_reader_coverage
from integration.glossary import integrate_glossaries
from integration.git import checked_revision
from integration import generate_index_navigation as navigation
from integration import generate_index_navigation_base as navigation_base
from integration import generate_index_navigation_locales as locales

CONFIGURATION_FILES = ('publication-sources.json', 'docs/publication-catalog.json', 'docs/glossary.yml')


def wire(value):
    if is_dataclass(value): return wire(asdict(value))
    if isinstance(value, bytes): return {'base64': base64.b64encode(value).decode('ascii')}
    if isinstance(value, PurePosixPath): return value.as_posix()
    if isinstance(value, dict): return {str(k): wire(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [wire(v) for v in value]
    return value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(wire(value)))


def require_revision(root, revision):
    if checked_revision(root) != revision:
        raise BundleError('checkout does not match exact revision')
    if subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no']):
        raise BundleError('tracked source modifications do not match exact revision')


def provider_order(provider_roots):
    if not valid_providers({name: '0'*40 for name in provider_roots}, 5):
        raise BundleError('providers must be nonempty, distinct authority names')
    return tuple(sorted(provider_roots))


def produce(*, root, provider_roots, provider_revisions, producer_revision, output,
            repository='TakashiSasaki/templates', staging_ids=(), code_revision=None):
    root, output = Path(root), Path(output)
    providers = provider_order(provider_roots)
    if set(provider_revisions) != set(providers):
        raise BundleError('provider roots and revisions must describe the same tuple')
    if staging_ids or (code_revision is not None and code_revision != producer_revision):
        raise BundleError('publication has no staging or separate controller identity')
    require_revision(root, producer_revision)
    if root.resolve() != Path(__file__).resolve().parents[1]:
        raise BundleError('producer code and configuration must use the same checkout')
    configuration = {name: digest((root/name).read_bytes()) for name in CONFIGURATION_FILES}
    publications = {}
    for name in providers:
        source = Path(provider_roots[name])
        require_revision(source, provider_revisions[name])
        documents, assets = load_catalog(name, source)
        publications[name] = source, documents, assets
    for source_root in (root, *provider_roots.values()):
        source, destination = Path(source_root).resolve(), output.resolve()
        if source == destination or source in destination.parents or destination in source.parents:
            raise BundleError('Bundle output must not overlap any source checkout')
    if output.exists() or output.is_symlink():
        raise BundleError('refusing to replace existing Bundle')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.publication-') as temporary:
        bundle = Path(temporary)/'bundle'; bundle.mkdir()
        docs_root = bundle/'publication'; docs_root.mkdir()
        documents, included, qualified = [], [], set()
        asset_rules = {name: [] for name in providers}
        for name, (provider_root, catalog, assets) in publications.items():
            for key, item in sorted(catalog.items()):
                source = item['source']
                path = resolve(provider_root, source, f'{name}:{source}')
                if item['optional'] and not path.exists():
                    continue
                if not path.is_file():
                    raise BundleError('declared publication document is not a file')
                destination = PurePosixPath(name) / ('index.md' if item['home'] else key + '.md')
                title = next((line[2:].strip() for line in path.read_text(encoding='utf-8').splitlines()
                              if line.startswith('# ')), key.replace('-', ' ').capitalize())
                record = dict(publication=name, document=key, source=str(source), destination=str(destination),
                              title=title, slot=False)
                target = docs_root/destination; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
                documents.append(record); included.append({**record, 'destination': destination})
                qualified.add('publication/' + str(destination))
            for asset in assets:
                path = resolve(provider_root, asset['source'], name + ' asset')
                if asset['optional'] and not path.exists():
                    continue
                destination = PurePosixPath(name)/asset['destination']
                copy_asset(path, docs_root/destination, name + ' asset')
                targets = (docs_root/destination).rglob('*') if path.is_dir() else [docs_root/destination]
                qualified.update(p.relative_to(bundle).as_posix() for p in targets if p.is_file())
                asset_rules[name].append((asset['source'], destination, path.is_dir()))
        published = {name: {PurePosixPath(d['source']): PurePosixPath(d['destination'])
                     for d in documents if d['publication'] == name} for name in providers}
        for document in documents:
            name = document['publication']; target = docs_root/document['destination']
            text, _ = _rewrite_markdown(target.read_text(encoding='utf-8'),
                source_document=PurePosixPath(document['source']), site_document=PurePosixPath(document['destination']),
                document_targets=published[name], asset_rules=asset_rules[name], docs_root=docs_root,
                publication=name, site_source_paths=None)
            target.write_text(text, encoding='utf-8')
        translations = publish_translations(publications, included, docs_root)
        reconcile_translation_fragments(publications, included, translations, docs_root)
        rewrite_available_localized_links(translations, docs_root)
        qualified.update('publication/' + str(record.translation_destination) for record in translations)
        write(bundle/'documents.json', documents)
        write(bundle/'translation-publication.json', {'schema_version': 1, 'canonical_language': 'en',
            'translations': [{'publication': r.publication, 'language': r.language,
                'canonical_destination': str(r.canonical_destination), 'translation_destination': str(r.translation_destination)}
                for r in translations]})
        write(bundle/'translation-availability.json', build_reader_coverage(publications, included))
        write(bundle/'glossary.json', integrate_glossaries({'integration': root, **provider_roots},
              {'integration': producer_revision, **provider_revisions}, repository))
        indexed = tuple(name for name in providers if (Path(provider_roots[name])/'index.md').is_file())
        navigation.PROVIDER_ORDER=indexed; navigation_base.PROVIDER_ORDER=indexed; locales.PROVIDER_ORDER=indexed
        indexed_roots = {name: provider_roots[name] for name in indexed}
        graph = navigation.generate_graph(repository, indexed_roots)
        write(bundle/'guided-navigation.json', graph)
        write(bundle/'guided-locales.json', locales.generate_locale_overlays(graph, indexed_roots))
        producer = {'authority': 'integration', 'revision': producer_revision}
        revisions = {name: provider_revisions[name] for name in providers}
        write(bundle/'provenance.json', {'schema_version': 1, 'producer': producer, 'providers': revisions})
        for name in providers: require_revision(provider_roots[name], provider_revisions[name])
        require_revision(root, producer_revision)
        result = seal(bundle, producer=producer, providers=revisions, configuration_digest=digest(canonical(configuration)),
                      expected_publication_paths=qualified, schema_version=5)
        bundle.rename(output)
    return result


def main(producer=produce):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--integration-root',type=Path,required=True)
    p.add_argument('--producer-revision',required=True)
    p.add_argument('--code-revision', help='Exact revision of the trusted code checkout when it differs from the producer identity')
    p.add_argument('--composition-root',type=Path,required=True)
    p.add_argument('--composition-revision',required=True)
    p.add_argument('--modeling-root',type=Path)
    p.add_argument('--modeling-revision')
    p.add_argument('--policy-root',type=Path,required=True)
    p.add_argument('--policy-revision',required=True)
    p.add_argument('--staging-ids',default='')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--github-output',type=Path)
    args=p.parse_args()
    try:
        provider_roots={'composition':args.composition_root,'policy':args.policy_root}
        provider_revisions={'composition':args.composition_revision,'policy':args.policy_revision}
        if (args.modeling_root is None) != (args.modeling_revision is None):
            p.error('--modeling-root and --modeling-revision must be supplied together')
        if args.modeling_root is not None:
            provider_roots['modeling']=args.modeling_root
            provider_revisions['modeling']=args.modeling_revision
        result=producer(root=args.integration_root,producer_revision=args.producer_revision,code_revision=args.code_revision,provider_roots=provider_roots,provider_revisions=provider_revisions,staging_ids=args.staging_ids.split(',') if args.staging_ids else [],output=args.output)
    except (ValueError,RuntimeError,OSError) as exc:p.error(str(exc))
    if args.github_output:
        with args.github_output.open('a') as stream:
            stream.write('bundle_schema='+str(result['schema_version'])+'\n')
            stream.write('bundle_identity='+result['identity']+'\n')
            stream.write('bundle_content_digest='+result['content_digest']+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},sort_keys=True))

if __name__=='__main__':main()
