"""Generate a deterministic Publication Bundle without Site rendering/runtime code."""
from __future__ import annotations
import argparse
import base64
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
from integration.repository import checked_revision, read_entries, build_preview_records, collect_records, object_sizes, object_contents
from publication_bundle.repository import MAX_TOTAL_TEXT_BYTES
from integration import generate_index_navigation as navigation
from integration import generate_index_navigation_base as navigation_base
from integration import generate_index_navigation_locales as locales
from integration.audience import AudienceContextResolver
from integration.staging import stage_models

PROVIDERS = ('composition', 'policy')
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


def require_revision(root, revision):
    if checked_revision(root) != revision:
        raise BundleError('checkout does not match exact revision')
    dirty = subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'])
    if dirty:
        raise BundleError('tracked source modifications do not match exact revision')


def produce(*, root, provider_roots, provider_revisions, producer_revision, output, repository='TakashiSasaki/templates', staging_ids=()):
    root, output = Path(root), Path(output)
    if set(provider_roots) != set(PROVIDERS) or set(provider_revisions) != set(PROVIDERS):
        raise BundleError('exact Composition and Policy inputs required')
    require_revision(root, producer_revision)
    for name in PROVIDERS:require_revision(provider_roots[name], provider_revisions[name])
    if root.resolve() != Path(__file__).resolve().parents[1]:
        raise BundleError('producer code and configuration must use the same exact checkout')
    configuration = {p:digest(regular(root,p).read_bytes()) for p in CONFIGURATION_FILES}
    configuration['staging_ids'] = list(staging_ids)
    if staging_ids:
        manifest_data, overlay_data = stage_models(root,list(staging_ids))
    else:
        manifest_data = read_json(root/'site-manifest.json','publication destinations')
        overlay_data = read_json(root/'reader-navigation-locales.json','navigation locales')
    manifest = parse_manifest(manifest_data)
    if manifest.schema_version != 3:
        raise BundleError('Bundle v1 requires the active audience manifest schema 3')
    slots = read_json(root/'integration/site-slots.json','Site content slots')
    slot_documents = {d['id']:d for d in slots['documents']}
    publications = {}
    for name in PROVIDERS:
        provider_root = Path(provider_roots[name])
        docs, assets = load_catalog(name,provider_root)
        publications[name] = (provider_root,docs,assets)
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
        asset_rules={name:[] for name in PROVIDERS}
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
            documents.append(record)
        for name,(provider_root,_,assets) in publications.items():
            for asset in assets:
                path=resolve(provider_root,asset['source'],name+' asset')
                if not path.exists() and asset['optional']:continue
                destination=PurePosixPath(name)/asset['destination']
                copy_asset(path,docs_root/destination,name+' asset')
                asset_rules[name].append((asset['source'],destination,path.is_dir()))
        published={name:{doc['source']:str(doc['destination']) for doc in documents if doc['publication']==name} for name in PROVIDERS}
        for doc in documents:
            name=doc['publication']
            if name=='site':continue
            target=docs_root/doc['destination']
            text,_=_rewrite_markdown(target.read_text(encoding='utf-8'),source_document=PurePosixPath(doc['source']),site_document=doc['destination'],document_targets={PurePosixPath(k):PurePosixPath(v) for k,v in published[name].items()},asset_rules=asset_rules[name],docs_root=docs_root,publication=name,site_source_paths=None)
            target.write_text(text,encoding='utf-8')
        translations=publish_translations(publications,included,docs_root)
        reconcile_translation_fragments(publications,included,translations,docs_root)
        rewrite_available_localized_links(translations,docs_root)
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
        navigation.PROVIDER_ORDER=PROVIDERS;navigation_base.PROVIDER_ORDER=PROVIDERS;locales.PROVIDER_ORDER=PROVIDERS
        graph=navigation.generate_graph(repository,{name:provider_roots[name] for name in PROVIDERS})
        write(bundle/'guided-navigation.json',graph)
        write(bundle/'guided-locales.json',locales.generate_locale_overlays(graph,provider_roots))
        models={}
        for name in PROVIDERS:
            provider_root=provider_roots[name];revision=provider_revisions[name]
            entries=read_entries(provider_root)
            sizes=object_sizes(provider_root,(e.object_id for e in entries if e.mode in {'100644','100755'}))
            if sum(sizes[e.object_id] for e in entries if e.mode in {'100644','100755'})>MAX_TOTAL_TEXT_BYTES:
                raise BundleError('oversized authenticated source corpus')
            _,browser=collect_records(name,repository,revision,provider_root)
            models[name]={'revision':revision,'entries':[dict(name=e.name,path=e.path,mode=e.mode,kind=e.kind,object_id=e.object_id) for e in entries], 'browser':list(browser.values()),'nonviewable_blobs':{oid:base64.b64encode(raw).decode('ascii') for oid,raw in object_contents(provider_root,(r.object_id for r in browser.values() if not r.viewable)).items()},'previews':build_preview_records(name,repository,revision,provider_root),'published':published[name]}
        write(bundle/'provider-repositories.json',models)
        producer={'authority':'integration','revision':producer_revision}
        write(bundle/'provenance.json',{'schema_version':1,'producer':producer,'providers':provider_revisions})
        for name in PROVIDERS:require_revision(provider_roots[name],provider_revisions[name])
        require_revision(root,producer_revision)
        if {p:digest(regular(root,p).read_bytes()) for p in CONFIGURATION_FILES} != {p:v for p,v in configuration.items() if p!='staging_ids'}:
            raise BundleError('configuration changed during generation')
        result=seal(bundle,producer=producer,providers=provider_revisions,configuration_digest=digest(canonical(configuration)))
        bundle.rename(output)
    return result


def main(producer=produce):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--integration-root',type=Path,required=True)
    p.add_argument('--producer-revision',required=True)
    p.add_argument('--composition-root',type=Path,required=True)
    p.add_argument('--composition-revision',required=True)
    p.add_argument('--policy-root',type=Path,required=True)
    p.add_argument('--policy-revision',required=True)
    p.add_argument('--staging-ids',default='')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--github-output',type=Path)
    args=p.parse_args()
    try:
        result=producer(root=args.integration_root,producer_revision=args.producer_revision,provider_roots={'composition':args.composition_root,'policy':args.policy_root},provider_revisions={'composition':args.composition_revision,'policy':args.policy_revision},staging_ids=args.staging_ids.split(',') if args.staging_ids else [],output=args.output)
    except (ValueError,RuntimeError,OSError) as exc:p.error(str(exc))
    if args.github_output:
        with args.github_output.open('a') as stream:
            stream.write('bundle_identity='+result['identity']+'\n')
            stream.write('bundle_content_digest='+result['content_digest']+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},sort_keys=True))

if __name__=='__main__':main()
