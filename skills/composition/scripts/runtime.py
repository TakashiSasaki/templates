from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import runtime_checkout as _impl

# Preserve the existing runner helper surface while replacing only consumer source
# acquisition and Composer execution. Doctor/cache migration can then move in a
# separate, observable step without duplicating runtime-environment semantics.
for _name, _value in vars(_impl).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

ARCHIVE_LIMIT = 64 * 1024 * 1024
EXTRACTED_LIMIT = 128 * 1024 * 1024
MEMBER_LIMIT = 20000
SOURCE_CONTEXT_ENV = "COMPOSITION_SOURCE_CONTEXT"
SNAPSHOT_SCHEMA = 1
REQUIRED_SNAPSHOT_PATHS = frozenset(
    {
        "requirements-runtime.lock",
        "scripts/compose.py",
        "scripts/composer_core.py",
        "scripts/composer_core_impl.py",
        "scripts/composer_managed.py",
        "scripts/composer_managed_impl.py",
        "scripts/composer_source.py",
        "scripts/verify_runtime_environment.py",
    }
)


class Response(Protocol):
    headers: object

    def __enter__(self) -> Response: ...

    def __exit__(self, *args: object) -> None: ...

    def read(self, amount: int = -1) -> bytes: ...


class Opener(Protocol):
    def __call__(
        self,
        request: urllib.request.Request,
        *,
        timeout: int,
    ) -> Response: ...


def source_archive_url(revision: str) -> str:
    if _impl.FULL_SHA.fullmatch(revision) is None:
        raise _impl.RunnerError(
            "Composition source archive revision must be a full lowercase SHA"
        )
    return f"https://codeload.github.com/{_impl.CANONICAL_REPOSITORY}/tar.gz/{revision}"


def download_source_archive(
    revision: str,
    *,
    opener: Opener | None = None,
) -> bytes:
    request = urllib.request.Request(
        source_archive_url(revision),
        headers={"User-Agent": "composition-runner/2"},
    )
    open_url = urllib.request.urlopen if opener is None else opener
    try:
        with open_url(request, timeout=30) as response:
            raw_length = getattr(response.headers, "get", lambda _key: None)(
                "Content-Length"
            )
            if raw_length is not None:
                try:
                    length = int(raw_length)
                except (TypeError, ValueError) as exc:
                    raise _impl.RunnerError(
                        "Composition source archive returned invalid Content-Length"
                    ) from exc
                if length < 0 or length > ARCHIVE_LIMIT:
                    raise _impl.RunnerError(
                        "Composition source archive exceeds the download size limit"
                    )
            data = response.read(ARCHIVE_LIMIT + 1)
    except urllib.error.HTTPError as exc:
        raise _impl.RunnerError(
            f"cannot download immutable Composition source archive: HTTP {exc.code}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise _impl.RunnerError(
            f"cannot download immutable Composition source archive: {exc}"
        ) from exc
    if len(data) > ARCHIVE_LIMIT:
        raise _impl.RunnerError(
            "Composition source archive exceeds the download size limit"
        )
    if not data:
        raise _impl.RunnerError("Composition source archive download was empty")
    return data


def _safe_archive_relative(
    member: tarfile.TarInfo,
    archive_root: str | None,
) -> tuple[str, PurePosixPath | None]:
    path = PurePosixPath(member.name)
    parts = path.parts
    if path.is_absolute() or not parts:
        raise _impl.RunnerError(
            f"unsafe path in Composition source archive: {member.name}"
        )
    root = parts[0]
    if root in {"", ".", ".."} or "\\" in root or ":" in root:
        raise _impl.RunnerError(
            f"unsafe root in Composition source archive: {member.name}"
        )
    if archive_root is not None and root != archive_root:
        raise _impl.RunnerError(
            "Composition source archive contains multiple top-level roots"
        )
    relative_parts = parts[1:]
    if not relative_parts:
        return root, None
    if any(
        part in {"", ".", ".."} or "\\" in part or ":" in part
        for part in relative_parts
    ):
        raise _impl.RunnerError(
            f"unsafe path in Composition source archive: {member.name}"
        )
    return root, PurePosixPath(*relative_parts)


def _validate_archive_structure(
    selected: dict[PurePosixPath, tarfile.TarInfo],
) -> None:
    entries = sorted(selected)
    for index, left in enumerate(entries):
        left_member = selected[left]
        for right in entries[index + 1 :]:
            if len(left.parts) >= len(right.parts):
                continue
            if left.parts == right.parts[: len(left.parts)] and not left_member.isdir():
                raise _impl.RunnerError(
                    "Composition source archive file/directory paths conflict: "
                    f"{left}, {right}"
                )


def extract_source_snapshot(
    data: bytes,
    destination: Path,
    revision: str,
) -> dict[str, str]:
    if _impl.FULL_SHA.fullmatch(revision) is None:
        raise _impl.RunnerError(
            "Composition source snapshot revision must be a full lowercase SHA"
        )
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    selected: dict[PurePosixPath, tarfile.TarInfo] = {}
    portable: dict[str, PurePosixPath] = {}
    archive_root: str | None = None
    total_size = 0

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > MEMBER_LIMIT:
                raise _impl.RunnerError(
                    "Composition source archive exceeds the member-count limit"
                )
            for member in members:
                root, relative = _safe_archive_relative(member, archive_root)
                archive_root = root
                if relative is None:
                    if not member.isdir():
                        raise _impl.RunnerError(
                            "Composition source archive root must be a directory"
                        )
                    continue
                if member.issym() or member.islnk():
                    raise _impl.RunnerError(
                        "symbolic and hard links are not allowed in Composition "
                        f"source archives: {member.name}"
                    )
                if not member.isdir() and not member.isfile():
                    raise _impl.RunnerError(
                        "unsupported member type in Composition source archive: "
                        f"{member.name}"
                    )
                if relative in selected:
                    raise _impl.RunnerError(
                        f"duplicate path in Composition source archive: {relative}"
                    )
                portable_key = relative.as_posix().casefold()
                previous = portable.get(portable_key)
                if previous is not None and previous != relative:
                    raise _impl.RunnerError(
                        "portable path collision in Composition source archive: "
                        f"{previous}, {relative}"
                    )
                portable[portable_key] = relative
                if member.isfile():
                    if member.size < 0:
                        raise _impl.RunnerError(
                            f"invalid file size in Composition source archive: {member.name}"
                        )
                    total_size += member.size
                    if total_size > EXTRACTED_LIMIT:
                        raise _impl.RunnerError(
                            "Composition source archive exceeds the extracted-size limit"
                        )
                selected[relative] = member

            _validate_archive_structure(selected)
            inventory: dict[str, str] = {}
            for relative, member in sorted(
                selected.items(),
                key=lambda item: item[0].as_posix(),
            ):
                target = destination.joinpath(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise _impl.RunnerError(
                        f"cannot read Composition source member: {member.name}"
                    )
                digest = hashlib.sha256()
                remaining = member.size
                with source, target.open("xb") as output:
                    while remaining:
                        chunk = source.read(min(64 * 1024, remaining))
                        if not chunk:
                            raise _impl.RunnerError(
                                "Composition source archive member ended early: "
                                f"{member.name}"
                            )
                        output.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                inventory[relative.as_posix()] = digest.hexdigest()
    except tarfile.TarError as exc:
        raise _impl.RunnerError(
            f"cannot read Composition source archive: {exc}"
        ) from exc

    missing = sorted(REQUIRED_SNAPSHOT_PATHS - set(inventory))
    if missing:
        raise _impl.RunnerError(
            "Composition source revision does not support immutable snapshot "
            f"execution; missing: {', '.join(missing)}"
        )
    return inventory


def write_source_context(
    path: Path,
    revision: str,
    inventory: dict[str, str],
) -> Path:
    payload = {
        "schema_version": SNAPSHOT_SCHEMA,
        "repository": _impl.CANONICAL_REPOSITORY,
        "revision": revision,
        "files": {key: inventory[key] for key in sorted(inventory)},
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def run_composer(
    repository: Path,
    arguments: Sequence[str],
    *,
    explicit_revision: str | None = None,
) -> int:
    _impl.verify_host_python()
    manifest = _impl.load_manifest()
    revision = _impl.select_revision(repository, explicit_revision, manifest)
    archive = download_source_archive(revision)

    with tempfile.TemporaryDirectory(prefix="composition-source-") as temporary:
        temporary_root = Path(temporary)
        source = temporary_root / "source"
        inventory = extract_source_snapshot(archive, source, revision)
        context_path = write_source_context(
            temporary_root / "source-context.json",
            revision,
            inventory,
        )
        env = _impl.sanitized_environment()
        env[SOURCE_CONTEXT_ENV] = str(context_path)
        cache = _impl.cache_root()
        python = _impl.ensure_runtime_cache(source, revision, manifest, cache, env)
        command = [
            str(python),
            "-I",
            "-B",
            str(source / manifest["entrypoint"]),
            *arguments,
            "--target",
            str(repository),
        ]
        try:
            completed = subprocess.run(
                command,
                env=env,
                check=False,
            )
        except OSError as exc:
            raise _impl.RunnerError(
                f"cannot execute Composition Composer: {exc}"
            ) from exc
        return completed.returncode


# Override the implementation-exported entrypoint after the compatibility copy.
globals()["run_composer"] = run_composer
