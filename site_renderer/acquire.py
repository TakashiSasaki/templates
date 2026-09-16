"""Acquire an exact reviewed Integration Bundle through the existing transport."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from ci_artifacts.publication_bundle import binding, extract, api
from ci_artifacts.transport import ArtifactError
from site_renderer.bundle import load_lock, validate, validate_locked, read_json


def paginated(path,key):
    result=[];separator='&' if '?' in path else '?'
    for page in range(1,101):
        batch=api(f'{path}{separator}per_page=100&page={page}')[key];result+=batch
        if len(batch)<100:return result
    raise ArtifactError('Integration artifact pagination limit exceeded')


def receipt(lock,artifact,run):
    return {'repository':lock['repository'],'producer':lock['revision'],
        'identity':lock['bundle_identity'],'run_id':run['id'],'attempt':run['run_attempt'],
        'workflow_head':run['head_sha'],'artifact_id':artifact['id'],
        'archive_digest':artifact['digest'],'artifact_name':artifact['name']}


def locate(lock):
    prefix=f"repos/{lock['repository']}/actions"
    runs=paginated(f"{prefix}/workflows/validate-integration.yml/runs?head_sha={lock['revision']}&status=success",'workflow_runs')
    for run in sorted(runs,key=lambda r:r['id'],reverse=True):
        if run['head_sha']!=lock['revision'] or run['conclusion']!='success':raise ArtifactError('misbound Integration release run')
        artifacts=paginated(f"{prefix}/runs/{run['id']}/artifacts",'artifacts')
        matching=[a for a in artifacts if a['name'].startswith('publication-bundle-') and not a['expired']]
        if not matching:continue
        if len(matching)!=1:raise ArtifactError('ambiguous Integration release artifact')
        found=receipt(lock,matching[0],run)
        verify_receipt(lock,found)
        return found
    # Absence/expiry allows the separately pinned Integration workflow to regenerate.
    # Binding/corruption exceptions are never converted to absence.
    return None


def verify_receipt(lock,value):
    fields={'repository','producer','identity','run_id','attempt','workflow_head','artifact_id','archive_digest','artifact_name'}
    if not isinstance(value,dict) or set(value)!=fields:raise ArtifactError('invalid Integration artifact receipt')
    if (value['repository'],value['producer'],value['identity'])!=(lock['repository'],lock['revision'],lock['bundle_identity']):raise ArtifactError('receipt differs from Site Integration selection')
    prefix=f"repos/{lock['repository']}/actions"
    metadata=api(f"{prefix}/artifacts/{value['artifact_id']}")
    run=api(f"{prefix}/runs/{value['run_id']}/attempts/{value['attempt']}")
    jobs=paginated(f"{prefix}/runs/{value['run_id']}/attempts/{value['attempt']}/jobs",'jobs')
    binding(metadata,run,jobs,**value)
    return prefix


def consume(lock,value,output):
    prefix=verify_receipt(lock,value)
    def accepted(root,**expected):
        result=validate(root,**expected);validate_locked(root,lock);return result
    with tempfile.TemporaryDirectory() as tmp:
        archive=Path(tmp)/'bundle.zip'
        with archive.open('wb') as stream:subprocess.run(['gh','api',f"{prefix}/artifacts/{value['artifact_id']}/zip"],stdout=stream,check=True)
        return extract(archive,output,archive_digest=value['archive_digest'],identity=lock['bundle_identity'],producer=lock['revision'],providers=None,validator=accepted,producer_authority='integration')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=['locate','consume','receipt'])
    parser.add_argument('--lock',type=Path,default=Path('integration-source.json'));parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path);parser.add_argument('--github-output',type=Path)
    for field in ('artifact-id','run-id','attempt'):parser.add_argument('--'+field,type=int)
    args=parser.parse_args();lock=load_lock(args.lock)
    if args.operation=='locate':value=locate(lock)
    elif args.operation=='receipt':
        prefix=f"repos/{lock['repository']}/actions";artifact=api(f'{prefix}/artifacts/{args.artifact_id}');run=api(f'{prefix}/runs/{args.run_id}/attempts/{args.attempt}')
        value=receipt(lock,artifact,run);verify_receipt(lock,value)
    else:
        if args.output is None:parser.error('consume requires --output')
        result=consume(lock,read_json(args.receipt),args.output)
        print(json.dumps({k:result[k] for k in ('schema_version','producer','providers','identity','content_digest')}));return
    args.receipt.write_text(json.dumps(value,sort_keys=True)+'\n')
    if args.github_output:
        with args.github_output.open('a') as stream:
            stream.write('available='+str(value is not None).lower()+'\n')
            stream.write('integration_revision='+lock['revision']+'\n')
            stream.write('receipt='+json.dumps(value,separators=(',',':'))+'\n')
