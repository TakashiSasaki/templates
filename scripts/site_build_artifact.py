#!/usr/bin/env python3
"""Exact-input Site build identity and immutable canonical PR artifact reuse.

A successful producer build qualifies assembly, unit tests, generated links and
provenance. Browser evidence stays with each consumer; it is never cached here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import zipfile

WORKFLOW = '.github/workflows/build-pages.yml'
MANIFEST = 'ci-build-inputs.json'


# Both direct scripts and package imports retain this public error alias.
import sys
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci_artifacts.transport import ArtifactError, verified_tar


class InputMismatch(ArtifactError):
    """Valid prior artifact, but a different build recipe/environment identity."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def revision(root: Path) -> str:
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()


def identity(*, repository: str, site: str, composition: str, policy: str,
             workflow: bytes, staging: str = '', staging_ids: str = '', deployment_timestamp: str = '',
             public_url: str = 'https://templates.moukaeritai.work/',
             runtime: str = '', qualification_suite: str = 'unit-tests', bundle: dict | None = None) -> dict:
    for value in (site, composition, policy):
        if not re.fullmatch(r'[0-9a-f]{40}', value):
            raise ArtifactError('build revisions must be full immutable SHAs')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ArtifactError('invalid repository')
    if qualification_suite not in {'unit-tests', 'integration-tests-with-core', 'bundle-renderer', 'bundle-renderer-with-core'}:
        raise ArtifactError('invalid build qualification suite')
    result = dict(schema_version=1, repository=repository, site=site,
                composition=composition, policy=policy,
                workflow_sha256=digest(workflow), staging=staging, staging_ids=staging_ids,
                deployment_timestamp=deployment_timestamp, public_url=public_url,
                runtime=runtime, qualification_suite=qualification_suite)
    if bundle is not None:
        result['schema_version'] = 2
        result['publication_bundle'] = bundle
    return result


def identity_key(inputs: dict) -> str:
    return digest(json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode())


def validate_manifest(manifest: dict, expected: dict) -> None:
    if (not isinstance(manifest, dict) or set(manifest) != {'inputs', 'identity'}
            or not isinstance(manifest['inputs'], dict)
            or set(manifest['inputs']) != set(expected)
            or manifest['identity'] != identity_key(manifest['inputs'])):
        raise ArtifactError('invalid artifact build input manifest')
    if manifest['inputs'] != expected or manifest['identity'] != identity_key(expected):
        raise InputMismatch('artifact build input identity mismatch')


def validate_provenance(provenance: dict, expected: dict) -> None:
    if not isinstance(provenance, dict) or type(provenance.get('schema_version')) is not int:
        raise ArtifactError('invalid artifact publication provenance schema')
    if provenance != dict(schema_version=2, repository=expected['repository'],
                          site_commit=expected['site'], publication_commits={
                              'composition': expected['composition'], 'policy': expected['policy']}):
        raise ArtifactError('artifact publication provenance mismatch')


def validate_and_extract(archive: Path, expected: dict, expected_digest: str,
                         target: Path) -> None:
    if target.exists() or target.is_symlink():
        raise ArtifactError('artifact destination already exists')
    with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
        root = Path(temporary)
        with verified_tar(archive, expected_digest, member_name='artifact.tar', parent=root) as pages:
            members = pages.getmembers()
            def document(name):
                matches = [m for m in members if PurePosixPath(m.name).as_posix() == name and m.isfile()]
                if len(matches) != 1:
                    raise ArtifactError(f'missing artifact {name}')
                return json.load(pages.extractfile(matches[0]))
            validate_manifest(document(MANIFEST), expected)
            validate_provenance(document('build-provenance.json'), expected)
            if not any(PurePosixPath(m.name).as_posix() == 'index.html' and m.isfile() for m in members):
                raise ArtifactError('artifact is missing index.html')
            pages.extractall(root / 'site', filter='data')
        (root / 'site').rename(target)


def api(path: str) -> dict:
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def list_all(path: str, key: str) -> list[dict]:
    result = []
    separator = '&' if '?' in path else '?'
    for page in range(1, 101):
        items = api(f'{path}{separator}per_page=100&page={page}')[key]
        result.extend(items)
        if len(items) < 100:
            return result
    raise ArtifactError('GitHub pagination limit exceeded')


def select_run(runs: list[dict], *, repository: str, head: str, pr: int,
               current_run: int) -> dict | None:
    candidates = [run for run in runs if
                  run['id'] != current_run and run['path'] == WORKFLOW
                  and run['head_sha'] == head and run['event'] == 'pull_request'
                  and run['head_repository']['full_name'] == repository
                  and any(p['number'] == pr for p in run['pull_requests'])]
    return max(candidates, key=lambda r: (r['run_number'], r['run_attempt']), default=None)


def qualified_artifact(run: dict, jobs: list[dict], artifacts: list[dict],
                       expected: dict) -> dict | None:
    builds = [job for job in jobs if job['name'] in {'build', 'build / build'}]
    if len(builds) != 1:
        if run['status'] == 'completed':
            raise ArtifactError('canonical run has no unique build job')
        return None
    build = builds[0]
    if build['status'] != 'completed':
        return None
    if build['conclusion'] != 'success':
        raise ArtifactError('canonical build did not succeed')
    matches = [a for a in artifacts if a['name'] == 'github-pages' and not a['expired']]
    if len(matches) != 1:
        raise ArtifactError('canonical build has no unique unexpired Pages artifact')
    artifact = matches[0]
    binding = artifact.get('workflow_run', {})
    if binding.get('id') != run['id'] or binding.get('head_sha') != expected['site']:
        raise ArtifactError('artifact is bound to a different run or Site revision')
    if artifact['created_at'] < build['started_at'] or artifact['created_at'] > build['completed_at']:
        raise ArtifactError('artifact is not from the successful build attempt')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', artifact.get('digest', '')):
        raise ArtifactError('artifact has no immutable digest')
    return artifact


def reuse(expected: dict, target: Path, *, pr: int, current_run: int,
          timeout: int = 1200, wait: bool = True) -> dict:
    repository = expected['repository']
    deadline = time.monotonic() + timeout
    while True:
        runs = list_all(f'repos/{repository}/actions/workflows/build-pages.yml/runs?event=pull_request&head_sha={expected["site"]}', 'workflow_runs')
        run = select_run(runs, repository=repository, head=expected['site'], pr=pr, current_run=current_run)
        # A canonical producer can reuse an earlier qualified same-head build.
        # If none exists (including a previous docs-only skip), it must build.
        while run:
            jobs = list_all(f'repos/{repository}/actions/runs/{run["id"]}/jobs?filter=latest', 'jobs')
            builds = [job for job in jobs if job['name'] in {'build', 'build / build'}]
            # Unrelated label events intentionally create isolated same-head runs
            # whose build job is skipped. They are not producer failures and must
            # not hide an older applicable producer while consumers are waiting.
            if (len(builds) == 1 and builds[0]['status'] == 'completed'
                    and builds[0]['conclusion'] == 'skipped'):
                runs = [r for r in runs if r['id'] != run['id']]
                run = select_run(runs, repository=repository, head=expected['site'], pr=pr, current_run=current_run)
                continue
            if wait or any(j['name'] in {'build', 'build / build'} and j['status'] == 'completed' and j['conclusion'] == 'success' for j in jobs):
                break
            runs = [r for r in runs if r['id'] != run['id']]
            run = select_run(runs, repository=repository, head=expected['site'], pr=pr, current_run=current_run)
        if run:
            artifacts = list_all(f'repos/{repository}/actions/runs/{run["id"]}/artifacts', 'artifacts')
            if not wait and not any(a['name'] == 'github-pages' and not a['expired'] for a in artifacts):
                return {}
            artifact = qualified_artifact(run, jobs, artifacts, expected)
            if artifact:
                with tempfile.TemporaryDirectory() as temp:
                    archive = Path(temp) / 'pages.zip'
                    with archive.open('wb') as output:
                        subprocess.run(['gh', 'api', f'repos/{repository}/actions/artifacts/{artifact["id"]}/zip'], stdout=output, check=True)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        validate_and_extract(archive, expected, artifact['digest'], target)
                    except InputMismatch:
                        if wait:
                            raise
                        # A changed base workflow or runner image is a different
                        # identity: the canonical producer must build it afresh.
                        return {}
                return dict(producer_run=run['id'], artifact_id=artifact['id'], digest=artifact['digest'])
        if not wait:
            return {}
        if time.monotonic() >= deadline:
            raise ArtifactError('canonical exact-head build discovery timed out; no reuse or duplicate build authorized')
        print('Waiting for canonical exact-head Site build', flush=True)
        time.sleep(10)


def reuse_applicable(expected: dict, locked: dict, *, requested: bool, event: str) -> bool:
    return (requested and event == 'pull_request'
            and expected['composition'] == locked['composition']
            and expected['policy'] == locked['policy']
            and not expected['staging'] and not expected['staging_ids'] and not expected['deployment_timestamp'])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-root', type=Path, default=Path('site-source'))
    parser.add_argument('--workflow-file', type=Path, default=Path('workflow-source') / WORKFLOW)
    parser.add_argument('--target', type=Path, default=Path('build/site'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--identity-file', type=Path, default=Path('build-inputs.json'))
    args = parser.parse_args()
    runtime = '|'.join([platform.python_version(), os.environ.get('RUNNER_OS', ''), os.environ.get('RUNNER_ARCH', ''), os.environ.get('ImageOS', ''), os.environ.get('ImageVersion', '')])
    from publication_bundle.contract import validate as validate_bundle
    bundle = validate_bundle(Path(os.environ['PUBLICATION_BUNDLE_ROOT'])) if os.environ.get('PUBLICATION_BUNDLE_ROOT') else None
    expected = identity(repository=os.environ['GITHUB_REPOSITORY'], site=revision(args.site_root),
                        composition=bundle['providers']['composition'] if bundle else revision(Path('composition-source')), policy=bundle['providers']['policy'] if bundle else revision(Path('policy-source')),
                        bundle={k:bundle[k] for k in ('schema_version','producer','providers','identity','content_digest')} if bundle else None,
                        workflow=args.workflow_file.read_bytes(), staging=os.environ.get('STAGING_ID', ''),
                        staging_ids=os.environ.get('STAGING_IDS', ''),
                        deployment_timestamp=os.environ.get('DEPLOYMENT_TIMESTAMP', ''),
                        public_url=os.environ['PUBLIC_SITE_URL'], runtime=runtime,
                        qualification_suite=(
                            ('bundle-renderer-with-core' if bundle else 'integration-tests-with-core')
                            if os.environ.get('CORE_TESTS_SCHEDULED') == 'true'
                            else ('bundle-renderer' if bundle else 'unit-tests')
                        ))
    args.identity_file.write_text(json.dumps({'inputs': expected, 'identity': identity_key(expected)}, sort_keys=True) + '\n')
    # Only ordinary PR builds have a canonical producer. Provider overrides,
    # staged mappings and deployment timestamps must be compared before reuse.
    from resolve_publication_sources import resolve_sources
    locked = resolve_sources(args.site_root / 'publication-sources.json', {})
    eligible = reuse_applicable(expected, locked,
                                requested=os.environ.get('REUSE_PR_BUILD') == 'true',
                                event=os.environ.get('GITHUB_EVENT_NAME', ''))
    canonical = os.environ.get('IS_CANONICAL_BUILD') == 'true' and os.environ.get('GITHUB_EVENT_NAME') == 'pull_request'
    evidence = reuse(expected, args.target, pr=int(os.environ['PR_NUMBER']), current_run=int(os.environ['GITHUB_RUN_ID']), wait=False) if eligible or canonical else {}
    reused = bool(evidence)
    with args.output.open('a') as output:
        output.write(f'reused={str(reused).lower()}\nidentity={identity_key(expected)}\n')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as output:
            output.write('### Exact-input Site build\n\n' + json.dumps(dict(identity=identity_key(expected), reused=reused, inputs=expected, **evidence), sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
