"""Build the complete Site artifact from Publication Bundle v1 and Site-owned source."""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from publication_bundle.contract import BundleError, validate, read_json, regular
from publication_bundle.repository import TreeEntry, FileRecord, PreviewRecord, build_tree, configured_base_path
from publication_bundle.source_models import raw_path
from publication_bundle.source_reader import checked_revision, collect_records
from site_renderer import repository_trees as trees, previews, repository_browser as browser, guided, guided_locales
from site_renderer.config import render_nav
from site_renderer.local_content import fill, put


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def record(cls,value):
    return cls(**{k:raw_path(v) if k in {'name','path'} else v for k,v in value.items()})


def run(site_root,script,*args):
    command=[sys.executable,str(regular(site_root,'scripts/'+script)),*map(str,args)]
    subprocess.run(command,check=True)


def render(*,bundle,site_root,output,expected_identity,public_url='https://templates.moukaeritai.work/',deployment_timestamp=''):
    bundle,site_root,output=Path(bundle).absolute(),Path(site_root).absolute(),Path(output).absolute()
    identity=validate(bundle,expected_identity=expected_identity)
    if output.exists() or output.is_symlink():raise BundleError('refusing to replace existing render output')
    for source in (bundle,site_root):
        if output==source or source in output.parents or output in source.parents:raise BundleError('render output overlaps input')
    output.parent.mkdir(parents=True,exist_ok=True)
    site_revision=checked_revision(site_root)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.site-render-') as temporary:
        build=Path(temporary)/'build';build.mkdir();docs=build/'docs';docs.mkdir()
        for name in identity['files']:
            if name.startswith('publication/'):
                put(regular(bundle,name),docs/name.removeprefix('publication/'))
        documents=read_json(bundle/'documents.json');nav=read_json(bundle/'navigation.json')
        translations=fill(site_root,docs,documents,nav,read_json(bundle/'translation-publication.json'),read_json(bundle/'translation-availability.json'),build)
        # This script exposes the same pure Site-owned metadata function used by the old CLI.
        import importlib.util
        spec=importlib.util.spec_from_file_location('_site_translation_metadata',site_root/'scripts/translation_reader_metadata.py')
        metadata=importlib.util.module_from_spec(spec);spec.loader.exec_module(metadata)
        for translation in translations['translations']:
            metadata.exclude_translation_from_search(docs/translation['translation_destination'])
        template=regular(site_root,'zensical.template.toml').read_text(encoding='utf-8')
        if template.count('__GENERATED_NAV__')!=1:raise BundleError('Site template must have one navigation slot')
        navigation=[{'title':{'use':'Use templates','maintain':'Maintain templates'}.get(aud,aud),'children':nodes} for aud in nav['audience_runtime']['audiences'] for nodes in [nav['navigation'][aud]] if nodes]
        (build/'zensical.toml').write_text(template.replace('__GENERATED_NAV__',render_nav(navigation)),encoding='utf-8')
        models=read_json(bundle/'provider-repositories.json');repository=read_json(bundle/'guided-navigation.json')['repository']
        base_path=configured_base_path(build/'zensical.toml');summaries={}
        for name,model in models.items():
            entries=[record(TreeEntry,e) for e in model['entries']]
            tree=build_tree(entries);published={k.encode():v for k,v in model['published'].items()}
            rendered,counts=trees.render_tree(name,repository,model['revision'],tree,f'repository-trees/{name}.md',base_path,published)
            trees.replace_marker(docs/f'repository-trees/{name}.md',f'<!-- GENERATED_REPOSITORY_TREE:{name} -->',rendered)
            summaries[name]=(model['revision'],counts)
            source_previews=[record(PreviewRecord,r) for r in model['previews']]
            previews.inject_preview_links(name,repository,model['revision'],base_path,build,published,source_previews)
            previews.write_preview_pages(build,source_previews,name,model['revision'])
        table=['| Publication | Rendered revision | Directories | Files | Published documents |','|---|---|---:|---:|---:|']
        for name,(revision,counts) in summaries.items():
            table.append(f"| [{name.title()}]({name}.md) | `{revision}` | {counts['directories']} | {counts['files']+counts['symlinks']+counts['gitlinks']} | {counts['published_documents']} |")
        trees.replace_marker(docs/'repository-trees/index.md','<!-- GENERATED_REPOSITORY_TREE_INDEX -->','\n'.join(table)+'\n')
        run(site_root,'prepare_site_metadata.py','--config-file',build/'zensical.toml','--deployment-timestamp',deployment_timestamp,'--canonical-url',public_url)
        subprocess.run([str(Path(sys.executable).with_name('zensical')),'build','--config-file',str(build/'zensical.toml'),'--clean','--strict'],check=True)
        site=build/'site';write(site/'glossary/index.json',read_json(bundle/'glossary.json'))
        run(site_root,'generate_glossary_viewer.py','--input',site/'glossary/index.json','--output',site/'glossary/index.html')
        run(site_root,'finalize_site_metadata.py','--site-root',site,'--canonical-url',public_url)
        browser_root=browser.prepare_browser_root(site);browser.write_root_index(browser_root);browser.write_browser_controller(browser_root)
        site_tree,site_records=collect_records('site',repository,site_revision,site_root)
        sources={'site':(site_revision,site_tree,site_records)}
        for name,model in models.items():
            sources[name]=(model['revision'],build_tree([record(TreeEntry,e) for e in model['entries']]),{raw_path(r['path']):record(FileRecord,r) for r in model['browser']})
        for name,(revision,tree,records) in sources.items():
            branch_root=browser_root/name;(branch_root/'content').mkdir(parents=True)
            (branch_root/'index.html').write_text(browser.render_browser_page(name,revision,tree,records),encoding='utf-8')
            for r in records.values():browser.write_verified_file_page(branch_root/r.viewer_url,name,revision,r)
        graph=read_json(bundle/'guided-navigation.json');published={name:model['published'] for name,model in models.items()}
        guided.generate_from_bundle(repository,graph,published,site)
        overlays=guided_locales.load_overlays(bundle/'guided-locales.json',graph)
        reader_translations=guided_locales.load_reader_translations(build/'translation-publication.json')
        guided_locales.generate_from_bundle(repository,graph,overlays,reader_translations,published,site,build/'guided-locale-publication.json')
        run(site_root,'finalize_site_metadata.py','--site-root',site/'guided','--canonical-url',public_url)
        run(site_root,'render_website_metadata.py','--repository',site_root,'--site-root',site)
        run(site_root,'finalize_translation_reader.py','--site-root',site,'--translation-map',build/'translation-publication.json','--canonical-url',public_url)
        run(site_root,'validate_translation_pairs.py','--site-root',site,'--translation-map',build/'translation-publication.json','--canonical-url',public_url)
        run(site_root,'finalize_guided_locales.py','--site-root',site,'--pair-map',build/'guided-locale-publication.json','--canonical-url',public_url)
        run(site_root,'finalize_glossary_annotations.py','--site-root',site,'--glossary',site/'glossary/index.json')
        run(site_root,'check_public_url_boundary.py','--site-root',site)
        provenance_args=[]
        for name,revision in identity['providers'].items():provenance_args+=['--publication-commit',name+'='+revision]
        run(site_root,'write_publication_provenance.py','--site-root',site,'--repository',repository,'--site-commit',site_revision,*provenance_args)
        write(site/'publication-bundle.json',{'schema_version':1,'identity':identity['identity'],'producer':identity['producer'],'providers':identity['providers']})
        run(site_root,'validate_site_links.py','--site-root',site,'--config-file',build/'zensical.toml')
        build.rename(output)
    return {'site_revision':site_revision,'bundle_identity':identity['identity'],'output':str(output)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--bundle-identity',required=True)
    parser.add_argument('--site-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--public-url',default='https://templates.moukaeritai.work/')
    parser.add_argument('--deployment-timestamp',default='')
    args=parser.parse_args()
    print(json.dumps(render(bundle=args.bundle,site_root=args.site_root,output=args.output,expected_identity=args.bundle_identity,public_url=args.public_url,deployment_timestamp=args.deployment_timestamp)))

if __name__=='__main__':main()
