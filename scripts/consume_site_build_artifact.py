#!/usr/bin/env python3
"""Consume a scheduled producer's exact artifact without discovery or polling."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.site_build_artifact import ArtifactError, api, validate_and_extract
from site_renderer.bundle import load_lock


def selected_input_matches(expected, locked):
    bundle=expected.get('publication_bundle',{})
    return (expected.get('schema_version')==3
        and bundle.get('producer')=={'authority':'integration','revision':locked['revision']}
        and bundle.get('schema_version')==locked['bundle_schema']
        and bundle.get('identity')==locked['bundle_identity']
        and bundle.get('content_digest')==locked['content_digest']
        and not any(k in expected for k in ('composition','policy','staging','staging_ids')))


def validate_binding(metadata: dict, expected: dict, *, artifact_id: int, archive_digest: str,
                     run_id: int, head: str, repository: str, locked: dict) -> None:
    if (metadata.get('id') != artifact_id or metadata.get('expired') is not False
            or metadata.get('digest') != archive_digest
            or metadata.get('workflow_run', {}).get('id') != run_id
            or metadata.get('workflow_run', {}).get('head_sha') != head):
        raise ArtifactError('scheduled artifact metadata binding mismatch')
    if (expected.get('site') != head or expected.get('repository') != repository
            or not selected_input_matches(expected, locked)
            or expected.get('staging') or expected.get('staging_ids')
):
        raise ArtifactError('scheduled artifact input binding mismatch')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', archive_digest):
        raise ArtifactError('scheduled artifact is missing immutable digest')


def main() -> None:
    expected = json.loads(os.environ['BUILD_INPUTS'])
    repository = os.environ['GITHUB_REPOSITORY']
    artifact_id = int(os.environ['BUILD_ARTIFACT_ID'])
    metadata = api(f'repos/{repository}/actions/artifacts/{artifact_id}')
    archive_digest = os.environ['BUILD_ARTIFACT_DIGEST']
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    validate_binding(metadata, expected, artifact_id=artifact_id, archive_digest=archive_digest,
                     run_id=int(os.environ['GITHUB_RUN_ID']), head=head, repository=repository,
                     locked=load_lock(Path('integration-source.json')))
    target = Path('build/site')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'artifact.zip'
        with archive.open('wb') as output:
            subprocess.run(['gh', 'api', f'repos/{repository}/actions/artifacts/{artifact_id}/zip'],
                           stdout=output, check=True)
        validate_and_extract(archive, expected, archive_digest, target)
    print(json.dumps({'artifact_id': artifact_id, 'digest': archive_digest, 'polling_seconds': 0}))


if __name__ == '__main__':
    main()
