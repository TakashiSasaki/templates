"""Build the complete Site artifact from a Publication Bundle and Site-owned source."""
from __future__ import annotations
import argparse
import ctypes
import errno
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tempfile

from publication_bundle.contract import BundleError, read_json, regular, canonical, digest
from publication_bundle.markdown import _rewrite_markdown
from site_renderer.bundle import validate, validate_locked, load_lock
from site_renderer.git import checked_revision
from site_renderer.github import immutable_github_source_url
from site_renderer import guided, guided_locales
from site_renderer.config import render_nav
from site_renderer.local_content import fill, put


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run(site_root,script,*args):
    command=[sys.executable,str(regular(site_root,'scripts/'+script)),*map(str,args)]
    subprocess.run(command,check=True)


def zensical_executable():
    candidates = []
    resolved = shutil.which('zensical')
    if resolved:
        candidates.append(Path(resolved))
    candidates.append(Path(sys.executable).with_name('zensical'))
    candidates.append(Path(sysconfig.get_path('scripts', scheme='posix_user'))/'zensical')
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise BundleError('zensical executable is not available to the runner Python')


def checked_output(output, sources):
    output=Path(output).absolute()
    if any(path.is_symlink() for path in (output,*output.parents)):
        raise BundleError('render output traverses a symlink')
    resolved=output.resolve()
    for source in sources:
        source=Path(source).resolve()
        if resolved==source or source in resolved.parents or resolved in source.parents:
            raise BundleError('render output overlaps input')
    if resolved.exists():raise BundleError('refusing to replace existing render output')
    return resolved


def require_clean_site(site_root, revision=None):
    current=checked_revision(site_root)
    if revision is not None and current != revision:
        raise BundleError('Site revision changed during rendering')
    if subprocess.check_output(['git','-C',str(site_root),'status','--porcelain','--untracked-files=all']):
        raise BundleError('Site rendering requires clean committed inputs')
    return current


def prepare_output_parent(output, sources):
    """Walk/create directory components relative to pinned, no-follow parents."""
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
    protected={(stat.st_dev,stat.st_ino) for stat in (Path(source).stat() for source in sources)}
    fd=os.open(output.anchor,flags)
    try:
        for component in output.parent.parts[1:]:
            try:child=os.open(component,flags,dir_fd=fd)
            except FileNotFoundError:
                try:os.mkdir(component,dir_fd=fd)
                except FileExistsError:pass
                child=os.open(component,flags,dir_fd=fd)
            os.close(fd);fd=child
            stat=os.fstat(fd)
            if (stat.st_dev,stat.st_ino) in protected:
                raise BundleError('render output parent entered an input directory')
        stat=os.fstat(fd);identity=(stat.st_dev,stat.st_ino)
        checked_output(output,sources)
        current=output.parent.stat()
        if (current.st_dev,current.st_ino)!=identity:
            raise BundleError('render output parent changed during creation')
        return fd,identity
    except OSError as exc:
        os.close(fd)
        raise BundleError('unsafe render output parent: '+str(exc)) from exc
    except BaseException:
        os.close(fd)
        raise


def rename_noreplace(directory, source, target):
    """Linux atomic directory publication; never replace another actor's path."""
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,'renameat2',None)
    if rename is None:raise BundleError('atomic no-replace publication requires renameat2')
    rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    rename.restype=ctypes.c_int
    if rename(directory,os.fsencode(source),directory,os.fsencode(target),1):
        error=ctypes.get_errno()
        if error==errno.EEXIST:raise BundleError('refusing to replace concurrently created render output')
        raise OSError(error,os.strerror(error),target)


def publish_build(build, output, parent_identity, sources, site_revision, parent_directory=None):
    # All expensive work happens outside the destination. Pin the parent for
    # the final same-filesystem staging/rename so aliases cannot redirect it.
    require_clean_site(sources[1],site_revision)
    checked_output(output,sources)
    fd=os.dup(parent_directory) if parent_directory is not None else os.open(output.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    stage=None
    try:
        stat=os.fstat(fd)
        if (stat.st_dev,stat.st_ino)!=parent_identity:
            raise BundleError('render output parent changed during rendering')
        parent=Path('/proc/self/fd')/str(fd)
        # A descriptor pins identity, not containment: reject moved parents
        # before any staging write, including moves beneath protected inputs.
        effective=parent.resolve(strict=True)
        checked_output(effective/output.name,sources)
        if effective!=output.parent or output.parent.stat().st_ino!=stat.st_ino or output.parent.stat().st_dev!=stat.st_dev:
            raise BundleError('render output parent changed before staging')
        stage=Path(tempfile.mkdtemp(prefix='.site-publish-',dir=parent))
        shutil.copytree(build,stage,dirs_exist_ok=True)
        checked_output(output,sources)
        current=output.parent.stat()
        if (current.st_dev,current.st_ino)!=parent_identity:
            raise BundleError('render output parent changed before publication')
        require_clean_site(sources[1],site_revision)
        rename_noreplace(fd,stage.name,output.name)
        stage=None
    finally:
        if stage is not None:shutil.rmtree(stage)
        os.close(fd)


def snapshot_bundle(source, target, expected_identity):
    manifest=validate(source,expected_identity=expected_identity)
    target.mkdir()
    # Copy only bounded declared files, verify each read against the accepted
    # inventory, then validate the resulting private snapshot as a whole.
    for name,record in manifest['files'].items():
        with regular(source,name).open('rb') as stream:data=stream.read(record['size']+1)
        if len(data)!=record['size'] or digest(data)!=record['sha256']:
            raise BundleError('Bundle changed during snapshot copy')
        path=target/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (target/'bundle.json').write_bytes(canonical(manifest))
    return validate(target,expected_identity=expected_identity)


def consume_snapshot(**inputs):
    # Execute renderer code as well as source reads from the exact private Git
    # checkout. The caller's mutable checkout is no longer a runtime input.
    payload={key:str(value) if isinstance(value,Path) else value for key,value in inputs.items()}
    code="""import json,sys
from pathlib import Path
from site_renderer.render import render_snapshot
args=json.load(sys.stdin)
for key in ('bundle','site_root','output','original_bundle','original_site'):args[key]=Path(args[key])
args['parent_identity']=tuple(args['parent_identity'])
render_snapshot(**args)
"""
    env=dict(os.environ);env.pop('PYTHONPATH',None)
    subprocess.run([sys.executable,'-c',code],cwd=inputs['site_root'],env=env,input=json.dumps(payload),text=True,check=True,pass_fds=(inputs['parent_directory'],))
    return {'site_revision':inputs['site_revision'],'bundle_identity':inputs['identity']['identity'],'output':str(inputs['output'])}


def render(*,bundle,site_root,output,expected_identity,public_url='https://templates.moukaeritai.work/',deployment_timestamp=''):
    bundle,site_root=Path(bundle).resolve(),Path(site_root).resolve()
    output=checked_output(output,(bundle,site_root))
    site_revision=require_clean_site(site_root)
    selected=load_lock(regular(site_root,"integration-source.json"))
    if expected_identity!=selected["bundle_identity"]:raise BundleError("renderer identity differs from Site Integration lock")
    validate_locked(bundle,selected)
    with tempfile.TemporaryDirectory(prefix='site-input-snapshot-') as temporary:
        snapshot=Path(temporary)/'bundle'
        identity=snapshot_bundle(bundle,snapshot,expected_identity)
        source=Path(temporary)/'source'
        subprocess.run(['git','clone','--shared','--no-checkout',str(site_root),str(source)],check=True,capture_output=True)
        subprocess.run(['git','-C',str(source),'sparse-checkout','set','--no-cone','/*','!/integration/'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(source),'checkout','--detach',site_revision],check=True,capture_output=True)
        require_clean_site(source,site_revision)
        parent_directory,parent_identity=prepare_output_parent(output,(bundle,site_root))
        try:
            return consume_snapshot(bundle=snapshot,site_root=source,output=output,
                identity=identity,site_revision=site_revision,parent_identity=parent_identity,
                parent_directory=parent_directory,original_bundle=bundle,original_site=site_root,
                public_url=public_url,deployment_timestamp=deployment_timestamp)
        finally:os.close(parent_directory)


def render_snapshot(*,bundle,site_root,output,identity,site_revision,parent_identity,parent_directory,original_bundle,original_site,public_url,deployment_timestamp):
    with tempfile.TemporaryDirectory(prefix='site-render-') as temporary:
        build=Path(temporary)/'build';build.mkdir();docs=build/'docs';docs.mkdir()
        for name in identity['files']:
            if name.startswith('publication/'):
                put(regular(bundle,name),docs/name.removeprefix('publication/'))
        documents=read_json(bundle/'documents.json');nav=read_json(bundle/'navigation.json')
        translations=fill(site_root,docs,documents,nav,read_json(bundle/'translation-publication.json'),read_json(bundle/'translation-availability.json'),build,site_revision=site_revision)
        source_revisions={'site':site_revision,'integration':identity['producer']['revision'],**identity['providers']}
        for path in sorted(docs.rglob('*.md')):
            relative=path.relative_to(docs).as_posix()
            text,_=_rewrite_markdown(path.read_text(encoding='utf-8'),source_document=Path(relative),site_document=Path(relative),document_targets={},asset_rules=[],docs_root=docs,publication='absolute-source-links',site_source_paths=None,absolute_url_rewriter=lambda url: immutable_github_source_url(url,source_revisions))
            path.write_text(text,encoding='utf-8')
        # This script exposes the same pure Site-owned metadata function used by the old CLI.
        import importlib.util
        spec=importlib.util.spec_from_file_location('_site_translation_metadata',site_root/'scripts/translation_reader_metadata.py')
        metadata=importlib.util.module_from_spec(spec);spec.loader.exec_module(metadata)
        for translation in translations['translations']:
            metadata.exclude_translation_from_search(docs/translation['translation_destination'])
        from site_renderer.discovery import write as write_discovery
        write_discovery(site_root,docs,identity)
        template=regular(site_root,'zensical.template.toml').read_text(encoding='utf-8')
        if template.count('__GENERATED_NAV__')!=1:raise BundleError('Site template must have one navigation slot')
        navigation=[{'title':{'use':'Use templates','maintain':'Maintain templates'}.get(aud,aud),'children':nodes} for aud in nav['audience_runtime']['audiences'] for nodes in [nav['navigation'][aud]] if nodes]
        (build/'zensical.toml').write_text(template.replace('__GENERATED_NAV__',render_nav(navigation)),encoding='utf-8')
        run(site_root,'prepare_site_metadata.py','--config-file',build/'zensical.toml','--deployment-timestamp',deployment_timestamp,'--canonical-url',public_url)
        subprocess.run([zensical_executable(),'build','--config-file',str(build/'zensical.toml'),'--clean','--strict'],check=True)
        site=build/'site';write(site/'glossary/index.json',read_json(bundle/'glossary.json'))
        run(site_root,'generate_glossary_viewer.py','--input',site/'glossary/index.json','--output',site/'glossary/index.html')
        run(site_root,'finalize_site_metadata.py','--site-root',site,'--canonical-url',public_url)
        graph=read_json(bundle/'guided-navigation.json');repository=graph['repository']
        published={provider['name']: {} for provider in graph['providers']}
        for document in documents:
            if not document['slot']:
                published.setdefault(document['publication'], {})[document['source']] = document['destination']
        from site_renderer.progressive_discovery import write as write_progressive_discovery
        write_progressive_discovery(site_root,site,graph,documents)
        guided.generate_from_bundle(repository,graph,published,site)
        overlays=guided_locales.load_overlays(bundle/'guided-locales.json',graph)
        reader_translations=guided_locales.load_reader_translations(build/'translation-publication.json')
        guided_locales.generate_from_bundle(repository,graph,overlays,reader_translations,published,site,build/'guided-locale-publication.json')
        run(site_root,'finalize_site_metadata.py','--site-root',site/'guided','--canonical-url',public_url)
        run(site_root,'render_website_metadata.py','--repository',site_root,'--site-root',site)
        run(site_root,'finalize_translation_reader.py','--site-root',site,'--translation-map',build/'translation-publication.json','--canonical-url',public_url,'--availability',build/'translation-coverage.json','--availability',build/'site-translation-coverage.json','--coverage-inventory',build/'reader-coverage-inventory.json')
        run(site_root,'validate_translation_pairs.py','--site-root',site,'--translation-map',build/'translation-publication.json','--canonical-url',public_url)
        run(site_root,'finalize_guided_locales.py','--site-root',site,'--pair-map',build/'guided-locale-publication.json','--canonical-url',public_url)
        run(site_root,'finalize_glossary_annotations.py','--site-root',site,'--glossary',site/'glossary/index.json')
        run(site_root,'check_public_url_boundary.py','--site-root',site)
        selected_bundle={k:identity[k] for k in ('schema_version','identity','content_digest','producer','providers')}
        write(site/'build-provenance.json',{'schema_version':3,'repository':repository,'site_commit':site_revision,'integration':selected_bundle})
        write(site/'publication-bundle.json',selected_bundle)
        # Runtime/deployed-document freshness remains separate from translation status.
        from site_renderer.freshness import project_freshness_metadata
        project_freshness_metadata(site/'build-provenance.json',site_revision,{'integration':identity['producer']['revision']})
        run(site_root,'validate_site_links.py','--site-root',site,'--config-file',build/'zensical.toml')
        publish_build(build,output,parent_identity,(original_bundle,site_root,original_site),site_revision,parent_directory)
    return {'site_revision':site_revision,'bundle_identity':identity['identity'],'output':str(output)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--bundle-identity',required=True)
    parser.add_argument('--site-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--public-url',default='https://templates.moukaeritai.work/')
    parser.add_argument('--deployment-timestamp',default='')
    parser.add_argument('--github-output',type=Path)
    args=parser.parse_args()
    result=render(bundle=args.bundle,site_root=args.site_root,output=args.output,expected_identity=args.bundle_identity,public_url=args.public_url,deployment_timestamp=args.deployment_timestamp)
    if args.github_output:
        notice=('Deployment time: '+args.deployment_timestamp) if args.deployment_timestamp else 'Preview build (not deployed)'
        with args.github_output.open('a') as stream:stream.write('notice='+notice+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
