"""Validate provider inventory and bounded source content, without Git access."""
import base64
import hashlib
from publication_bundle.contract import BundleError, SHA
from publication_bundle.repository import (MAX_TEXT_BYTES, MAX_TOTAL_TEXT_BYTES,
    MAX_PREVIEW_BYTES, MAX_TOTAL_PREVIEW_BYTES, MAX_CANDIDATE_BYTES, decode_browser_text, decode_preview_text,
    preview_relative_url, viewer_relative_url, source_url, github_url)


def raw_path(value):
    if not isinstance(value,dict) or set(value)!={'base64'} or not isinstance(value['base64'],str):
        raise BundleError('invalid encoded repository path')
    try:raw=base64.b64decode(value['base64'],validate=True)
    except ValueError as exc:raise BundleError('invalid path base64') from exc
    if base64.b64encode(raw).decode()!=value['base64'] or not raw or b'\0' in raw:
        raise BundleError('invalid repository path identity')
    return raw


def blob_sha(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def validate_sources(name,model,repository):
    expected={'revision','entries','browser','previews','published','nonviewable_blobs'}
    if set(model)!=expected or not all(isinstance(model[k],list) for k in ('entries','browser','previews')) or not isinstance(model['published'],dict):
        raise BundleError('invalid repository source model')
    if not isinstance(model['nonviewable_blobs'],dict):raise BundleError('invalid non-viewable blob evidence')
    evidence=model['nonviewable_blobs'];used_evidence=set();source_bytes=0
    entries={}
    for e in model['entries']:
        if not isinstance(e,dict) or set(e)!={'name','path','mode','kind','object_id'}:raise BundleError('invalid tree entry')
        path=raw_path(e['path'])
        if raw_path(e['name'])!=path.rsplit(b'/',1)[-1] or path in entries:raise BundleError('duplicate/inconsistent tree path')
        if e['mode'] not in {'040000','100644','100755','120000','160000'} or e['kind']!={'040000':'tree','160000':'commit'}.get(e['mode'],'blob') or not isinstance(e['object_id'],str) or not SHA.fullmatch(e['object_id']):raise BundleError('invalid tree identity')
        entries[path]=e
    regular={p:e for p,e in entries.items() if e['mode'] in {'100644','100755'}}
    expected_previews=set();candidate_bytes=0
    seen=set();total=0
    for record in model['browser']:
        if not isinstance(record,dict) or set(record)!={'path','object_id','size','viewer_url','source_url','viewable','reason','text'}:raise BundleError('invalid browser record')
        p=raw_path(record['path']);e=regular.get(p)
        if e is None or p in seen or record['object_id']!=e['object_id']:raise BundleError('browser inventory mismatch')
        seen.add(p)
        if type(record['size']) is not int or record['size']<0 or type(record['viewable']) is not bool:raise BundleError('invalid source size/status')
        if record['viewer_url']!=viewer_relative_url(name,model['revision'],p) or record['source_url']!=source_url(repository,model['revision'],p):raise BundleError('source URL identity mismatch')
        if record['viewable']:
            if not isinstance(record['text'],str):raise BundleError('missing viewable source text')
            raw=record['text'].encode('utf-8')
        else:
            encoded=evidence.get(record['object_id'])
            if not isinstance(encoded,str) or len(encoded)>4*((MAX_TOTAL_TEXT_BYTES+2)//3):raise BundleError('missing/oversized non-viewable blob evidence')
            try:raw=base64.b64decode(encoded,validate=True)
            except ValueError as exc:raise BundleError('invalid non-viewable blob evidence') from exc
            if base64.b64encode(raw).decode()!=encoded:raise BundleError('noncanonical blob evidence')
            used_evidence.add(record['object_id'])
        source_bytes+=len(raw)
        if source_bytes>MAX_TOTAL_TEXT_BYTES:raise BundleError('oversized authenticated source corpus')
        if len(raw)!=record['size'] or blob_sha(raw)!=record['object_id']:raise BundleError('source blob identity mismatch')
        text,reason=decode_browser_text(raw)
        if (record['text'],record['reason'],record['viewable'])!=(text,reason,text is not None):raise BundleError('source decoding status mismatch')
        if len(raw)<=MAX_PREVIEW_BYTES:candidate_bytes+=len(raw)
        if len(raw)<=MAX_TEXT_BYTES:total+=len(raw)
        if decode_preview_text(raw) is not None:expected_previews.add(p)
    if used_evidence!=set(evidence):raise BundleError('unexpected non-viewable blob evidence')
    if seen!=set(regular) or total>MAX_TOTAL_TEXT_BYTES:raise BundleError('incomplete/oversized browser corpus')
    seen=set();total=0
    for r in model['previews']:
        if not isinstance(r,dict) or set(r)!={'path','object_id','text','relative_url','source_url'}:raise BundleError('invalid preview record')
        p=raw_path(r['path']);e=regular.get(p)
        if e is None or p in seen or e['object_id']!=r['object_id'] or not isinstance(r['text'],str):raise BundleError('preview inventory mismatch')
        seen.add(p);raw=r['text'].encode('utf-8');total+=len(raw)
        if len(raw)>MAX_PREVIEW_BYTES or blob_sha(raw)!=r['object_id'] or decode_preview_text(raw)!=r['text']:raise BundleError('preview blob identity mismatch')
        if r['relative_url']!=preview_relative_url(name,model['revision'],p) or r['source_url']!=github_url(repository,model['revision'],'blob',p):raise BundleError('preview URL mismatch')
    if seen!=expected_previews:raise BundleError('incomplete/unexpected eligible preview set')
    if candidate_bytes>MAX_CANDIDATE_BYTES:raise BundleError('oversized preview candidates')
    if total>MAX_TOTAL_PREVIEW_BYTES:raise BundleError('oversized preview corpus')
