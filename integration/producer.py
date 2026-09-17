"""Generate a deterministic Publication Bundle without Site rendering/runtime code."""
from __future__ import annotations
import argparse
import base64
import copy
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile

from publication_bundle.contract import BundleError, canonical, digest, seal, regular
from publication_bundle.markdown import _rewrite_markdown
from integration.publication_model import load_catalog, parse_manifest, copy_asset, resolve, read_json
from integration.publish_translations import publish_translations
from integration.translation_fragment_reconciliation import reconcile_translation_fragments
from integration.translation_link_selection import rewrite_available_localized_links
from integration.translation_coverage import build_reader_coverage
from integration.reader_navigation_locales import load_overlays, build_runtime_map
from integration.glossary import integrate_glossaries
from integration.git import checked_revision
from integration import generate_index_navigation as navigation
from integration import generate_index_navigation_base as navigation_base
from integration import generate_index_navigation_locales as locales
from integration.audience import AudienceContextResolver
from integration.staging import stage_models

BASE_PROVIDERS = ('composition', 'policy')
MODELING_PROVIDERS = ('modeling', 'composition', 'policy')
CONFIGURATION_FILES = ('site-manifest.json', 'reader-navigation-locales.json',
                       'publication-staging.json', 'integration/site-slots.json',
                       'docs/publication-catalog.json', 'docs/glossary.yml')


def wire(value):
    if is_dataclass(value):return wire(asdict(value))
    if isinstance(value, bytes):return {'base64':base64.b64encode(value).decode('ascii')}
    if isinstance(value, PurePosixPath):return value.as_posix()
    if isinstance(value, dict):return {str(k):wire(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):return [wire(v) for v in value]
    return value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(wire(value)))


def _add_publication_asset_outputs(bundle_root, destination, source_is_directory, outputs):
    """Record the exact files emitted by an authoritative asset declaration."""
    target = bundle_root / 'publication' / destination
    if not source_is_directory:
        outputs.add((PurePosixPath('publication') / destination).as_posix())
        return
    for path in sorted(target.rglob('*')):
        if path.is_file():
            outputs.add(path.relative_to(bundle_root).as_posix())


def require_revision(root, revision):
    if checked_revision(root) != revision:
        raise BundleError('checkout does not match exact revision')
    dirty = subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'])
    if dirty:
        raise BundleError('tracked source modifications do not match exact revision')


def provider_order(provider_roots):
    names = set(provider_roots)
    if names == set(BASE_PROVIDERS):
        return BASE_PROVIDERS
    if names == set(MODELING_PROVIDERS):
        return MODELING_PROVIDERS
    raise BundleError('exact provider tuple must be Composition + Policy or Modeling + Composition + Policy')


def add_generic_modeling_pages(data, modeling_documents):
    """Project the bounded Modeling catalog through existing generic navigation."""
    result = copy.deepcopy(data)
    documents = result.get('documents')
    navigation_data = result.get('navigation')
    if not isinstance(documents, list) or not isinstance(navigation_data, dict):
        raise BundleError('Site manifest must expose audience navigation for Modeling projection')
    if any(item.get('publication') == 'modeling' for item in documents if isinstance(item, dict)):
        return result
    pages = []
    for document_id, document in sorted(modeling_documents.items()):
        destination = 'modeling/index.md' if document_id == 'catalog' else f'modeling/resources/{document_id}.md'
        pages.append({
            'publication': 'modeling',
            'document': document_id,
            'title': 'Modeling discovery catalog' if document_id == 'catalog' else document_id,
            'destination': destination,
            'primary_audience': 'use',
            'additional_audiences': ['maintain'],
        })
    documents.extend(pages)
    for audience in ('use', 'maintain'):
        tree = navigation_data.get(audience)
        if not isinstance(tree, list):
            raise BundleError(f'Site manifest navigation[{audience!r}] must be an array')
        tree.append({
            'title': 'Modeling',
            'children': [
                {
                    'title': 'Discovery catalog' if page['document'] == 'catalog' else page['title'],
                    'publication': page['publication'],
                    'document': page['document'],
                    'destination': page['destination'],
                }
                for page in pages
            ],
        })
    return result


def add_generic_modeling_locale_labels(data, modeling_documents):
    """Provide explicit same-language labels for generic Modeling navigation.

    Modeling owns its content, while Integration owns the assembled navigation
    contract.  These labels are a mechanical projection, not a translation or
    an adoption of Modeling semantics.
    """
    result = copy.deepcopy(data)
    locales = result.get('locales')
    if not isinstance(locales, list) or not locales:
        raise BundleError('reader navigation locales must contain a non-empty locales array')
    titles = ['Modeling'] + [
        'Discovery catalog' if document_id == 'catalog' else document_id
        for document_id in sorted(modeling_documents)
    ]
    for locale in locales:
        if not isinstance(locale, dict) or not isinstance(locale.get('labels'), list):
            raise BundleError('reader navigation locale labels must be arrays')
        existing_titles = {
            label.get('canonical') for label in locale['labels']
            if isinstance(label, dict)
        }
        existing_ids = {
            label.get('id') for label in locale['labels']
            if isinstance(label, dict)
        }
        for title in titles:
            if title in existing_titles:
                continue
            identifier = 'modeling-' + ''.join(
                character.lower() if character.isalnum() else '-'
                for character in title
            ).strip('-')
            while identifier in existing_ids:
                identifier += '-page'
            locale['labels'].append({
                'id': identifier,
                'canonical': title,
                'localized': title,
            })
            existing_titles.add(title)
            existing_ids.add(identifier)
    return result


def produce(*, root, provider_roots, provider_revisions, producer_revision, output, repository='TakashiSasaki/templates', staging_ids=()):
    root, output = Path(root), Path(output)
    providers = provider_order(provider_roots)
    if set(provider_revisions) != set(providers):
        raise BundleError('provider roots and revisions must describe the same exact tuple')
    # Preserve the protocol-defined tuple order in every identity object.  A
    # set-equivalent mapping with a different insertion order is not the same
    # wire representation for the guided-navigation contract.
    provider_roots = {name: provider_roots[name] for name in providers}
    provider_revisions = {name: provider_revisions[name] for name in providers}
    require_revision(root, producer_revision)
    for name in providers:require_revision(provider_roots[name], provider_revisions[name])
    if root.resolve() != Path(__file__).resolve().parents[1]:
        raise BundleError('producer code and configuration must use the same exact checkout')
    configuration = {p:digest(regular(root,p).read_bytes()) for p in CONFIGURATION_FILES}
    configuration['staging_ids'] = list(staging_ids)
    if staging_ids:
        manifest_data, overlay_data = stage_models(root,list(staging_ids))
    else:
        manifest_data = read_json(root/'site-manifest.json','publication destinations')
        overlay_data = read_json(root/'reader-navigation-locales.json','navigation locales')
    slots = read_json(root/'integration/site-slots.json','Site content slots')
    slot_documents = {d['id']:d for d in slots['documents']}
    publications = {}
    for name in providers:
        provider_root = Path(provider_roots[name])
        docs, assets = load_catalog(name,provider_root)
        publications[name] = (provider_root,docs,assets)
    if 'modeling' in providers:
        manifest_data = add_generic_modeling_pages(manifest_data, publications['modeling'][1])
        overlay_data = add_generic_modeling_locale_labels(overlay_data, publications['modeling'][1])
    manifest = parse_manifest(manifest_data)
    if manifest.schema_version != 3:
        raise BundleError('Publication Bundle requires the active audience manifest schema 3')
    declared = {(p['publication'],p['document']) for p in manifest.documents}
    expected = {('site',key) for key in slot_documents} | {(name,key) for name,(_,docs,_) in publications.items() for key in docs}
    if declared != expected:
        raise BundleError(f'publication closure mismatch: missing={sorted(expected-declared)} extra={sorted(declared-expected)}')
    resolved_output=output.resolve()
    for source_root in (root,*provider_roots.values()):
        source=Path(source_root).resolve()
        if resolved_output==source or resolved_output in source.parents or source in resolved_output.parents:
            raise BundleError('Bundle output must not overlap any source checkout')
    if output.exists() or output.is_symlink():raise BundleError('refusing to replace existing Bundle')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.publication-bundle-') as temp:
        bundle=Path(temp)/'bundle';bundle.mkdir();docs_root=bundle/'publication';docs_root.mkdir()
        documents=[]
        included=[]
        qualified_publication_paths=set()
        asset_rules={name:[] for name in providers}
        for page in manifest.documents:
            name=page['publication'];is_slot=name=='site'
            source=(slot_documents if is_slot else publications[name][1])[page['document']]['source']
            record={**page,'source':str(source),'slot':is_slot}
            if not is_slot:
                source=PurePosixPath(source)
                path=resolve(publications[name][0],source,f'{name}:{source}')
                if not path.exists() and publications[name][1][page['document']]['optional']:continue
                if not path.is_file():raise BundleError('declared publication document is not a file')
                target=docs_root/page['destination'];target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(path.read_bytes())
                included.append(page)
                qualified_publication_paths.add(
                    (PurePosixPath('publication') / page['destination']).as_posix()
                )
            documents.append(record)
        for name,(provider_root,_,assets) in publications.items():
            for asset in assets:
                path=resolve(provider_root,asset['source'],name+' asset')
                if not path.exists() and asset['optional']:continue
                destination=PurePosixPath(name)/asset['destination']
                copy_asset(path,docs_root/destination,name+' asset')
                _add_publication_asset_outputs(
                    bundle,
                    destination,
                    path.is_dir(),
                    qualified_publication_paths,
                )
                asset_rules[name].append((asset['source'],destination,path.is_dir()))
        published={name:{doc['source']:str(doc['destination']) for doc in documents if doc['publication']==name} for name in providers}
        for doc in documents:
            name=doc['publication']
            if name=='site':continue
            target=docs_root/doc['destination']
            text,_=_rewrite_markdown(target.read_text(encoding='utf-8'),source_document=PurePosixPath(doc['source']),site_document=doc['destination'],document_targets={PurePosixPath(k):PurePosixPath(v) for k,v in published[name].items()},asset_rules=asset_rules[name],docs_root=docs_root,publication=name,site_source_paths=None)
            target.write_text(text,encoding='utf-8')
        translations=publish_translations(publications,included,docs_root)
        reconcile_translation_fragments(publications,included,translations,docs_root)
        rewrite_available_localized_links(translations,docs_root)
        qualified_publication_paths.update(
            (PurePosixPath('publication') / record.translation_destination).as_posix()
            for record in translations
        )
        write(bundle/'documents.json',documents)
        # Filter only genuinely absent optional provider documents. Site slots stay required.
        included_keys={(d['publication'],d['document']) for d in documents}
        def filter_nav(nodes):
            result=[]
            for node in nodes:
                if 'children' in node:
                    children=filter_nav(node['children'])
                    if children:result.append({**node,'children':children})
                elif (node['publication'],node['document']) in included_keys:result.append(node)
            return result
        nav={aud:filter_nav(nodes) for aud,nodes in manifest.navigation.items()}
        write(bundle/'navigation.json',{'schema_version':1,'navigation':nav,'audience_runtime':AudienceContextResolver(manifest,documents=documents).export_runtime_map(),'locale_labels':overlay_data})
        overlay_path=Path(temp)/'locales.json';write(overlay_path,overlay_data)
        overlays=load_overlays(overlay_path,manifest.navigation)
        write(bundle/'reader-navigation-runtime.json',build_runtime_map(overlays,translations))
        write(bundle/'translation-publication.json',{'schema_version':1,'canonical_language':'en','translations':[{'publication':r.publication,'language':r.language,'canonical_destination':str(r.canonical_destination),'translation_destination':str(r.translation_destination)} for r in translations]})
        write(bundle/'translation-availability.json',build_reader_coverage(publications,included))
        # Cross-authority concepts now have their own Integration source authority.
        write(bundle/'glossary.json',integrate_glossaries({'integration':root,**provider_roots},{'integration':producer_revision,**provider_revisions},repository))
        navigation.PROVIDER_ORDER=providers;navigation_base.PROVIDER_ORDER=providers;locales.PROVIDER_ORDER=providers
        graph=navigation.generate_graph(repository,{name:provider_roots[name] for name in providers})
        write(bundle/'guided-navigation.json',graph)
        write(bundle/'guided-locales.json',locales.generate_locale_overlays(graph,provider_roots))
        producer={'authority':'integration','revision':producer_revision}
        write(bundle/'provenance.json',{'schema_version':1,'producer':producer,'providers':provider_revisions})
        for name in providers:require_revision(provider_roots[name],provider_revisions[name])
        require_revision(root,producer_revision)
        if {p:digest(regular(root,p).read_bytes()) for p in CONFIGURATION_FILES} != {p:v for p,v in configuration.items() if p!='staging_ids'}:
            raise BundleError('configuration changed during generation')
        result=seal(
            bundle,
            producer=producer,
            providers=provider_revisions,
            configuration_digest=digest(canonical(configuration)),
            expected_publication_paths=qualified_publication_paths,
            schema_version=4 if 'modeling' in providers else 3,
        )
        bundle.rename(output)
    return result


def main(producer=produce):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--integration-root',type=Path,required=True)
    p.add_argument('--producer-revision',required=True)
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
        result=producer(root=args.integration_root,producer_revision=args.producer_revision,provider_roots=provider_roots,provider_revisions=provider_revisions,staging_ids=args.staging_ids.split(',') if args.staging_ids else [],output=args.output)
    except (ValueError,RuntimeError,OSError) as exc:p.error(str(exc))
    if args.github_output:
        with args.github_output.open('a') as stream:
            stream.write('bundle_identity='+result['identity']+'\n')
            stream.write('bundle_content_digest='+result['content_digest']+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},sort_keys=True))

if __name__=='__main__':main()
