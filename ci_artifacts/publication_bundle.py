"""Exact scheduled Bundle transport using the shared Pages archive safeguards."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from ci_artifacts.transport import ArtifactError, verified_tar, artifact_matches_successful_build_attempt
from site_renderer.bundle import validate


def binding(metadata, run, jobs, *, artifact_id, archive_digest, run_id, attempt,
            producer, workflow_head, repository, identity, artifact_name):
    if (run.get('id') != run_id or run.get('run_attempt') != attempt
            or run.get('head_sha') != workflow_head
            or run.get('head_repository',{}).get('full_name') != repository):
        raise ArtifactError('Bundle workflow run/head/attempt binding mismatch')
    if (metadata.get('id') != artifact_id or metadata.get('expired') is not False
            or metadata.get('digest') != archive_digest
            or metadata.get('workflow_run',{}).get('id') != run_id
            or metadata.get('workflow_run',{}).get('head_sha') != workflow_head):
        raise ArtifactError('Bundle artifact metadata binding mismatch')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',archive_digest):
        raise ArtifactError('Bundle artifact is missing immutable digest')
    prefix=f'publication-bundle-{identity}-{attempt}-'
    if not artifact_name.startswith(prefix) or metadata.get('name') != artifact_name:
        raise ArtifactError('Bundle artifact producer binding mismatch')
    namespace=artifact_name[len(prefix):]
    if not re.fullmatch(r'[a-z][a-z0-9-]*',namespace):
        raise ArtifactError('invalid Bundle invocation namespace')
    label=f'Qualify Integration candidate ({namespace})'
    # Artifacts have no run_attempt field: bind to the successful uploading job
    # of the exact attempt, using the same timestamp-window check as Pages reuse.
    matches=[j for j in jobs if j.get('run_attempt') == attempt
             and j.get('status') == 'completed' and j.get('conclusion') == 'success'
             and (j.get('name') == label
                  or j.get('name','').endswith(' / '+label))
             and artifact_matches_successful_build_attempt(metadata,j)]
    if len(matches) != 1:
        raise ArtifactError('Bundle artifact has no unique successful producing attempt')


def pack(bundle, target):
    manifest=validate(bundle)
    if target.exists():raise ArtifactError('refusing to replace Bundle archive')
    with tarfile.open(target,'w',format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(['bundle.json',*manifest['files']]):
            data=(bundle/name).read_bytes(); entry=tarfile.TarInfo(name)
            entry.size=len(data); entry.mode=0o644
            import io
            archive.addfile(entry,io.BytesIO(data))


def extract(archive,target,*,archive_digest,identity,producer,providers,validator=validate,producer_authority="integration"):
    if target.exists() or target.is_symlink():raise ArtifactError('Bundle destination already exists')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        root=Path(tmp)/'bundle'
        with verified_tar(archive,archive_digest,member_name='bundle.tar',parent=Path(tmp)) as material:
            material.extractall(root,filter='data')
        manifest=validator(root,expected_identity=identity,expected_producer={'authority':producer_authority,'revision':producer},expected_providers=providers)
        root.rename(target)
    return manifest


def api(path):
    return json.loads(subprocess.check_output(['gh','api',path],text=True))

