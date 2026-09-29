"""Read successful Integration publications without editing Site source.

GitHub run/artifact identity authenticates transport. Bundle hashes authenticate
the payload. A selection is resolved once; later provider/branch movement is not
an invalidation of a complete artifact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

from ci_artifacts.transport import verified_tar
from publication_bundle.contract import BundleError, read_json
from site_renderer.bundle import validate

CHANNEL = read_json(Path(__file__).resolve().parents[1] / 'publication-channel.json')
REPOSITORY = CHANNEL['repository']
ARTIFACT = CHANNEL['artifact']
SOURCES = {'.github/workflows/'+name: (source['branch'], set(source['events']))
           for name, source in CHANNEL['workflows'].items()}


def api(path):
    return json.loads(subprocess.check_output(
        ['gh', 'api', f'repos/{REPOSITORY}/{path}'], stderr=subprocess.PIPE))


def pages(path, key):
    for page in range(1, 11):
        separator = '&' if '?' in path else '?'
        try:
            values = api(f'{path}{separator}per_page=100&page={page}')[key]
        except subprocess.CalledProcessError as exc:
            # A newly added workflow may not be registered before its first run.
            # Other channels can still provide a complete successful publication.
            if path.startswith('actions/workflows/') and b'(HTTP 404)' in (exc.stderr or b''):
                return
            raise
        yield from values
        if len(values) < 100:
            return
    # Older runs are outside the bounded automatic discovery window.
    # Operators can still select a retained run explicitly.
    return


def eligible(run):
    source = SOURCES.get(run.get('path'))
    return bool(source and run.get('head_branch') == source[0]
                and run.get('event') in source[1]
                and run.get('head_repository', {}).get('full_name') == REPOSITORY
                and run.get('status') == 'completed' and run.get('conclusion') == 'success')


def select(run_id=None):
    if run_id is not None:
        runs = [api(f'actions/runs/{run_id}')]
    else:
        runs = []
        for path, (branch, _) in SOURCES.items():
            runs.extend(pages(f'actions/workflows/{Path(path).name}/runs?branch={branch}&status=success', 'workflow_runs'))
        # Run IDs order publication attempts, not completion order. A late old
        # build must not replace a newer successful publication.
        runs.sort(key=lambda run: run['id'], reverse=True)
    for run in runs:
        if not eligible(run):
            continue
        artifacts = [artifact for artifact in pages(f"actions/runs/{run['id']}/artifacts", 'artifacts')
                     if artifact.get('name') == ARTIFACT and not artifact.get('expired')]
        if not artifacts:
            continue
        if len(artifacts) != 1:
            raise BundleError('publication run has ambiguous artifacts')
        artifact = artifacts[0]
        binding = artifact.get('workflow_run', {})
        if binding.get('id') != run['id'] or binding.get('head_sha') != run['head_sha']:
            raise BundleError('publication artifact is bound to another run')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', artifact.get('digest', '')):
            raise BundleError('publication artifact has no SHA-256 transport digest')
        return run, artifact
    raise BundleError('no available successful Integration publication; the current deployed Site is unchanged')


def acquire(output, run_id=None):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise BundleError('refusing to replace an existing publication')
    if any(parent.is_symlink() for parent in output.parents):
        raise BundleError('publication output traverses a symlink')
    run, artifact = select(run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.publication-', dir=output.parent) as temporary:
        temporary = Path(temporary)
        archive = temporary / 'download.zip'
        with archive.open('wb') as stream:
            subprocess.run(['gh', 'api', f"repos/{REPOSITORY}/actions/artifacts/{artifact['id']}/zip"],
                           stdout=stream, check=True)
        snapshot = temporary / 'bundle'
        snapshot.mkdir()
        with verified_tar(archive, artifact['digest'], member_name='publication.tar', parent=temporary) as material:
            material.extractall(snapshot, filter='data')
        manifest = validate(snapshot)
        if manifest['schema_version'] != 5:
            raise BundleError('publication channel requires Bundle 5')
        if run['head_branch'] == 'integration' and manifest['producer']['revision'] != run['head_sha']:
            raise BundleError('producer revision differs from publishing Integration run')
        # Recheck transport/run status after download. Never consume an artifact
        # from a cancelled, failed or subsequently rerun incomplete workflow.
        current = api(f"actions/runs/{run['id']}")
        if not eligible(current) or current.get('run_attempt') != run.get('run_attempt'):
            raise BundleError('publication run changed during acquisition')
        from site_renderer.render import rename_noreplace
        import os
        fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            rename_noreplace(fd, str(snapshot.relative_to(output.parent)), output.name)
        finally:
            os.close(fd)
    return {'run_id': run['id'], 'artifact_id': artifact['id'], 'archive_digest': artifact['digest'],
            'producer': manifest['producer'], 'bundle_identity': manifest['identity']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run', type=int)
    args = parser.parse_args()
    if args.run is not None and args.run <= 0:
        parser.error('--run must be a positive GitHub Actions run ID')
    try:
        print(json.dumps(acquire(args.output, args.run), indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Publication acquisition failed: {exc}\n')


if __name__ == '__main__':
    main()
