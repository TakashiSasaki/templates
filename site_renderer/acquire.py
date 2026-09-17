"""Acquire an exact reviewed Integration Bundle through the existing transport."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from ci_artifacts.publication_bundle import binding, extract, api
from ci_artifacts.transport import ArtifactError
from site_renderer.bundle import load_lock, validate, validate_locked, read_json


PROMOTION_WORKFLOW = '.github/workflows/integration-promotion-notify.yml'
PROMOTION_WORKFLOW_FILE = 'integration-promotion-notify.yml'
PROMOTION_NAME = 'Notify Site after Integration adoption'
PROMOTION_EVENT = 'pull_request'
BASE_RECEIPT_FIELDS = frozenset({
    'repository', 'producer', 'identity', 'run_id', 'attempt',
    'workflow_head', 'artifact_id', 'archive_digest', 'artifact_name',
})
TRUSTED_RECEIPT_FIELDS = frozenset({
    'artifact_id', 'archive_digest', 'artifact_name', 'content_digest',
    'run_id', 'attempt', 'workflow_head', 'workflow_name', 'workflow_event',
    'workflow_path', 'integration_revision', 'bundle_identity',
    'bundle_content_digest', 'policy_revision', 'controller_revision',
})


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


def _trusted_receipt(lock, bundle_receipt, receipt_artifact, run, *,
                     expected_policy_revision=None,
                     expected_controller_revision=None):
    """Bind a promoted Bundle to the independently verified Integration receipt."""
    from scripts.acquire_trusted_integration_receipt import acquire

    with tempfile.TemporaryDirectory() as directory:
        report_path = Path(directory) / 'verified-report.json'
        report = acquire(
            repository=lock['repository'],
            receipt_artifact_id=receipt_artifact['id'],
            receipt_artifact_digest=receipt_artifact['digest'],
            receipt_artifact_name=receipt_artifact['name'],
            bundle_artifact_id=bundle_receipt['artifact_id'],
            bundle_artifact_digest=bundle_receipt['archive_digest'],
            bundle_artifact_name=bundle_receipt['artifact_name'],
            run_id=run['id'],
            attempt=run['run_attempt'],
            workflow_head=run['head_sha'],
            workflow_name=run['name'],
            workflow_event=run['event'],
            workflow_path=PROMOTION_WORKFLOW,
            bundle_identity=lock['bundle_identity'],
            bundle_content_digest=lock['content_digest'],
            integration_revision=lock['revision'],
            expected_policy_revision=expected_policy_revision,
            expected_controller_revision=expected_controller_revision,
            output=report_path,
        )
        content_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    trusted = {
        'artifact_id': receipt_artifact['id'],
        'archive_digest': receipt_artifact['digest'],
        'artifact_name': receipt_artifact['name'],
        'content_digest': content_digest,
        'run_id': run['id'],
        'attempt': run['run_attempt'],
        'workflow_head': run['head_sha'],
        'workflow_name': run['name'],
        'workflow_event': run['event'],
        'workflow_path': PROMOTION_WORKFLOW,
        'integration_revision': lock['revision'],
        'bundle_identity': lock['bundle_identity'],
        'bundle_content_digest': lock['content_digest'],
        'policy_revision': report['trusted']['policy_revision'],
        'controller_revision': report['trusted']['controller_revision'],
    }
    return {**bundle_receipt, 'trusted_receipt': trusted}


def locate_trusted(lock, *, expected_policy_revision=None,
                   expected_controller_revision=None):
    """Find one exact, successful promoted release for a committed Site lock."""
    prefix=f"repos/{lock['repository']}/actions"
    runs=paginated(
        f"{prefix}/workflows/{PROMOTION_WORKFLOW_FILE}/runs?head_sha={lock['revision']}&status=success",
        'workflow_runs',
    )
    for run in sorted(runs, key=lambda value: value.get('id', 0), reverse=True):
        if (run.get('head_sha') != lock['revision']
                or run.get('head_repository', {}).get('full_name') != lock['repository']
                or run.get('name') != PROMOTION_NAME
                or run.get('event') != PROMOTION_EVENT
                or run.get('path') != PROMOTION_WORKFLOW
                or run.get('status') != 'completed'
                or run.get('conclusion') != 'success'
                or not isinstance(run.get('id'), int)
                or not isinstance(run.get('run_attempt'), int)
                or run['run_attempt'] <= 0):
            continue
        identity=lock['bundle_identity']
        bundle_name=f'publication-bundle-{identity}-{run["run_attempt"]}-promoted'
        receipt_name=f'publication-verification-{identity}-{run["run_attempt"]}-promoted'
        artifacts=paginated(f"{prefix}/runs/{run['id']}/artifacts", 'artifacts')
        bundles=[artifact for artifact in artifacts
                 if artifact.get('name') == bundle_name and artifact.get('expired') is False]
        receipts=[artifact for artifact in artifacts
                  if artifact.get('name') == receipt_name and artifact.get('expired') is False]
        if not bundles and not receipts:
            # A completed release whose retention window elapsed is an absent
            # artifact, not evidence to be regenerated in the trusted lane.
            continue
        if len(bundles) != 1 or len(receipts) != 1:
            raise ArtifactError('promoted Integration release has an ambiguous or incomplete artifact pair')
        bundle_receipt=receipt(lock, bundles[0], run)
        verify_receipt(lock, bundle_receipt)
        return _trusted_receipt(
            lock, bundle_receipt, receipts[0], run,
            expected_policy_revision=expected_policy_revision,
            expected_controller_revision=expected_controller_revision,
        )
    return None


def locate(lock, *, require_trusted_release=False, expected_policy_revision=None,
           expected_controller_revision=None):
    if require_trusted_release:
        return locate_trusted(
            lock,
            expected_policy_revision=expected_policy_revision,
            expected_controller_revision=expected_controller_revision,
        )
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
    if (not isinstance(value,dict)
            or frozenset(value) not in {BASE_RECEIPT_FIELDS, BASE_RECEIPT_FIELDS | {'trusted_receipt'}}):
        raise ArtifactError('invalid Integration artifact receipt')
    if (value['repository'],value['producer'],value['identity'])!=(lock['repository'],lock['revision'],lock['bundle_identity']):raise ArtifactError('receipt differs from Site Integration selection')
    prefix=f"repos/{lock['repository']}/actions"
    metadata=api(f"{prefix}/artifacts/{value['artifact_id']}")
    run=api(f"{prefix}/runs/{value['run_id']}/attempts/{value['attempt']}")
    jobs=paginated(f"{prefix}/runs/{value['run_id']}/attempts/{value['attempt']}/jobs",'jobs')
    artifact_name=value['artifact_name']
    marker=f"publication-bundle-{value['identity']}-{value['attempt']}-"
    if not artifact_name.startswith(marker):
        raise ArtifactError('Integration artifact namespace is not bound to its identity')
    namespace=artifact_name[len(marker):]
    workflows={
        # The committed Site lock predates the explicit-dispatch promotion
        # lane.  Keep its same-repository pull_request qualification artifact
        # readable while retaining exact workflow/run/head/artifact binding.
        'integration': (
            ("Validate Integration authority", "workflow_dispatch", ".github/workflows/validate-integration.yml"),
            ("Validate Integration authority", "pull_request", ".github/workflows/validate-integration.yml"),
        ),
        'promoted': (("Notify Site after Integration adoption", "pull_request", ".github/workflows/integration-promotion-notify.yml"),),
        'candidate': (("Qualify Integration candidate", "workflow_dispatch", ".github/workflows/integration-qualification.yml"),),
        # A Site build may regenerate an absent Bundle in its read-only
        # fallback lane.  The top-level workflow, rather than the nested
        # reusable workflow, is the identity returned by the GitHub API.
        'site-adoption': (
            ("Build documentation artifact", None, ".github/workflows/build-pages.yml"),
            ("Deploy documentation from site", "workflow_dispatch", ".github/workflows/deploy-pages.yml"),
        ),
    }
    if namespace not in workflows:
        raise ArtifactError('Integration artifact namespace is not approved for Site acquisition')
    for workflow_name, workflow_event, workflow_path in workflows[namespace]:
        if run.get('name') != workflow_name or (workflow_event is not None and run.get('event') != workflow_event) or run.get('path') != workflow_path:
            continue
        binding(
            metadata, run, jobs,
            workflow_name=workflow_name,
            workflow_event=workflow_event,
            workflow_path=workflow_path,
            **{key: value[key] for key in BASE_RECEIPT_FIELDS},
        )
        if 'trusted_receipt' in value:
            trusted=value['trusted_receipt']
            if not isinstance(trusted, dict) or set(trusted) != TRUSTED_RECEIPT_FIELDS:
                raise ArtifactError('invalid trusted Integration receipt')
            for field in ('integration_revision', 'controller_revision', 'policy_revision', 'workflow_head'):
                if not isinstance(trusted[field], str) or re.fullmatch(r'[0-9a-f]{40}', trusted[field]) is None:
                    raise ArtifactError('trusted Integration receipt has an invalid revision')
            for field in ('content_digest', 'bundle_identity', 'bundle_content_digest'):
                if not isinstance(trusted[field], str) or re.fullmatch(r'[0-9a-f]{64}', trusted[field]) is None:
                    raise ArtifactError('trusted Integration receipt has an invalid content identity')
            if (trusted['integration_revision'] != lock['revision']
                    or trusted['bundle_identity'] != lock['bundle_identity']
                    or trusted['bundle_content_digest'] != lock['content_digest']
                    or trusted['workflow_path'] != PROMOTION_WORKFLOW
                    or trusted['workflow_name'] != PROMOTION_NAME
                    or trusted['workflow_event'] != PROMOTION_EVENT):
                raise ArtifactError('trusted Integration receipt is not bound to this release')
        return prefix
    raise ArtifactError('Integration artifact was produced by an unapproved workflow identity')


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
    parser.add_argument('--require-trusted-release', action='store_true')
    parser.add_argument('--expected-policy-revision')
    parser.add_argument('--expected-controller-revision')
    args=parser.parse_args();lock=load_lock(args.lock)
    if args.operation=='locate':
        value=locate(
            lock,
            require_trusted_release=args.require_trusted_release,
            expected_policy_revision=args.expected_policy_revision,
            expected_controller_revision=args.expected_controller_revision,
        )
        if args.require_trusted_release and value is None:
            parser.error('no exact unexpired trusted promoted Integration release is available')
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
