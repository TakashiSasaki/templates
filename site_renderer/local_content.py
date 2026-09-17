"""Fill declared slots from Site's own content, never from provider checkouts."""
from pathlib import Path, PurePosixPath
import json
from urllib.parse import unquote
from publication_bundle.contract import BundleError, regular, safe_path
from publication_bundle.paths import public_path
from publication_bundle.markdown import _rewrite_markdown
from site_renderer.git import tracked_paths
from site_renderer.owned_content.publish_translations import publish_translations
from site_renderer.owned_content.translation_fragment_reconciliation import reconcile_translation_fragments
from site_renderer.owned_content.translation_link_selection import rewrite_current_localized_links
from site_renderer.owned_content.translation_coverage import build_reader_coverage
from site_renderer.owned_content.reader_navigation_locales import build_runtime_map, load_overlays
from site_renderer.github import github_blob_url


def put(source, target):
    if target.exists() or target.is_symlink():raise BundleError('Site content destination collision: '+str(target))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(source.read_bytes())


def copy_assets(source,target):
    if source.is_symlink() or not source.is_dir():raise BundleError('invalid Site asset root')
    for path in sorted(source.rglob('*')):
        if path.is_symlink():raise BundleError('Site assets contain a symlink')
        if path.is_dir():continue
        if not path.is_file():raise BundleError('Site assets contain a special file')
        put(path,target/path.relative_to(source))


def fill(site_root,docs_root,documents,nav,provider_translations,coverage,output,*,site_revision=None):
    slots=[d for d in documents if d['slot']]
    local_docs={d['document']:{'source':PurePosixPath(d['source']),'optional':False,'home':d['destination']=='index.md'} for d in slots}
    pages=[{**d,'destination':PurePosixPath(d['destination'])} for d in slots]
    for d in slots:put(regular(site_root,d['source']),docs_root/safe_path(d['destination']))
    copy_assets(site_root/'assets',docs_root)
    published={PurePosixPath(d['source']):PurePosixPath(d['destination']) for d in slots}
    source_paths=tracked_paths(site_root)
    def site_source_url(source, suffix):
        query, marker, fragment = suffix.partition("#")
        url = github_blob_url(
            'TakashiSasaki/templates',
            site_revision,
            source,
            fragment=unquote(fragment) if marker else None,
        )
        if query:
            if marker:
                base, hash_marker, hash_value = url.partition("#")
                url = base + query + hash_marker + hash_value
            else:
                url += query
        return url

    for d in slots:
        path=docs_root/d['destination']
        text,_=_rewrite_markdown(path.read_text(encoding='utf-8'),source_document=PurePosixPath(d['source']),site_document=PurePosixPath(d['destination']),document_targets=published,asset_rules=[],docs_root=docs_root,publication='site',site_source_paths=source_paths,site_source_url=site_source_url)
        path.write_text(text,encoding='utf-8')
    local={'site':(site_root,local_docs,[])}
    records=publish_translations(local,pages,docs_root)
    reconcile_translation_fragments(local,pages,records,docs_root)
    # Provider statuses are carried through unchanged; only Site-owned source is compiled here.
    local_coverage=build_reader_coverage(local,pages)
    combined=provider_translations['translations']+[{'publication':'site','language':r.language,'canonical_destination':str(r.canonical_destination),'translation_destination':str(r.translation_destination)} for r in records]
    translations={**provider_translations,'translations':combined}
    write=lambda path,data:path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    write(output/'translation-publication.json',translations)
    write(output/'translation-coverage.json',coverage)
    write(output/'site-translation-coverage.json',local_coverage)
    # Independent inventory comes from canonical reader documents and each
    # authority's language model, never from the availability record subset.
    write(output/'reader-coverage-inventory.json', {'schema_version': 1, 'coverage': [
        {'publication': d['publication'], 'canonical_destination': d['destination'], 'language': language}
        for d in documents
        for language in (local_coverage if d['slot'] else coverage)['languages']
    ]})
    # Existing label projection is shared; no provider source or manifest enters this stage.
    label_path=output/'reader-navigation-locales.json';write(label_path,nav['locale_labels'])
    labels=load_overlays(label_path,nav['navigation'])
    # build_runtime_map consumes only identity fields on each record.
    from types import SimpleNamespace
    runtime_records=[SimpleNamespace(**{**r,'canonical_destination':PurePosixPath(r['canonical_destination']),'translation_destination':PurePosixPath(r['translation_destination'])}) for r in combined]
    # Bundle publication records already certify available current/stale derivatives. Combine them
    # with Site-owned records for cross-authority reader-link projection.
    rewrite_current_localized_links(runtime_records,docs_root)
    write(docs_root/'reader-navigation-runtime.json',build_runtime_map(labels,runtime_records))
    audience=nav['audience_runtime']
    for r in combined:
        canonical=r['canonical_destination'];route=public_path(r['translation_destination'])
        if canonical in audience['documents']:
            audience['routes'][route]=canonical;audience['routes'][route+'index.html']=canonical
            for aud,overview in audience['overviews'].items():
                if audience['routes'].get(overview)==canonical:audience.setdefault('localized_overviews',{}).setdefault(r['language'],{})[aud]=route
    write(docs_root/'audience-runtime.json',audience)
    return translations
