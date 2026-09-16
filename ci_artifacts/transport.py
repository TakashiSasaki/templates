"""Bounded transport shared by Pages and Publication Bundle artifacts."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import zipfile


class ArtifactError(ValueError):
    pass


def parse_api_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ArtifactError(f'base artifact {field} timestamp is missing or malformed')
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ArtifactError(f'base artifact {field} timestamp is missing or malformed') from exc
    if instant.tzinfo is None:
        raise ArtifactError(f'base artifact {field} timestamp is missing or malformed')
    return instant.astimezone(timezone.utc)


def artifact_matches_successful_build_attempt(artifact: dict, build: dict) -> bool:
    started = parse_api_timestamp(build.get('started_at'), field='build started_at')
    completed = parse_api_timestamp(build.get('completed_at'), field='build completed_at')
    created = parse_api_timestamp(artifact.get('created_at'), field='created_at')
    if completed < started:
        raise ArtifactError('base artifact build attempt timestamps are out of order')
    return started <= created <= completed


@contextmanager
def verified_tar(archive: Path, expected_digest: str, *, member_name: str, parent: Path):
    """Verify immutable API digest, then bound and validate the entire archive."""
    with archive.open('rb') as source:
        actual = 'sha256:' + hashlib.file_digest(source, 'sha256').hexdigest()
    if expected_digest != actual:
        raise ArtifactError('artifact archive digest mismatch')
    maximum = 2 * 1024**3
    with tempfile.TemporaryDirectory(dir=parent) as tmp:
        path = Path(tmp) / 'artifact.tar'
        with zipfile.ZipFile(archive) as bundle:
            if bundle.namelist() != [member_name]:
                raise ArtifactError(f'expected exactly one {member_name}')
            info = bundle.getinfo(member_name)
            if info.file_size > maximum:
                raise ArtifactError('artifact archive exceeds size limit')
            with bundle.open(info) as source, path.open('wb') as output:
                shutil.copyfileobj(source, output)
        with tarfile.open(path) as material:
            seen = set()
            total = 0
            # Iteration bounds member enumeration as well as extracted bytes.
            for member in material:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or '\\' in member.name:
                    raise ArtifactError('unsafe artifact path')
                if not member.isfile() and not member.isdir():
                    raise ArtifactError('artifact links and special files are forbidden')
                key = path.as_posix()
                if key in seen:
                    raise ArtifactError('duplicate artifact path')
                seen.add(key)
                total += member.size
                if len(seen) > 50000 or total > maximum:
                    raise ArtifactError('artifact contents exceed limit')
            yield material
