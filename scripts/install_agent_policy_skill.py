#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"
INSTALLER_PATH = "scripts/install_agent_policy_skill.py"
SKILL_SOURCE_REVISION = "20cdbc720249516e3d30fc93e050391b81eaa6b4"
SKILL_SOURCE_PATH = "skills/agent-policy"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
ARCHIVE_LIMIT = 16 * 1024 * 1024
SKILL_LIMIT = 8 * 1024 * 1024
SKILL_PREFIX = ("skills", "agent-policy")
REQUIRED_SKILL_PATHS = frozenset(
    {
        PurePosixPath("SKILL.md"),
        PurePosixPath("runtime-manifest.json"),
        PurePosixPath("scripts/install.py"),
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


def archive_url(revision: str = SKILL_SOURCE_REVISION) -> str:
    if FULL_SHA.fullmatch(revision) is None:
        raise ValueError("skill source revision must be a full lowercase commit SHA")
    return f"https://codeload.github.com/{TOOLCHAIN_REPOSITORY}/tar.gz/{revision}"


def download_archive(
    revision: str = SKILL_SOURCE_REVISION,
    *,
    opener: Opener = urllib.request.urlopen,
) -> bytes:
    request = urllib.request.Request(  # noqa: S310 - fixed HTTPS GitHub origin
        archive_url(revision),
        headers={"User-Agent": "agent-policy-skill-installer/1"},
    )
    with opener(request, timeout=30) as response:
        raw_length = getattr(response.headers, "get", lambda _key: None)(
            "Content-Length"
        )
        if raw_length is not None:
            try:
                length = int(raw_length)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("skill archive returned invalid Content-Length") from exc
            if length < 0 or length > ARCHIVE_LIMIT:
                raise RuntimeError("skill archive exceeds the download size limit")
        data = response.read(ARCHIVE_LIMIT + 1)
    if len(data) > ARCHIVE_LIMIT:
        raise RuntimeError("skill archive exceeds the download size limit")
    if not data:
        raise RuntimeError("skill archive download was empty")
    return data


def safe_relative_member(member: tarfile.TarInfo) -> PurePosixPath | None:
    path = PurePosixPath(member.name)
    parts = path.parts
    if path.is_absolute() or len(parts) < 3:
        return None
    if tuple(parts[1:3]) != SKILL_PREFIX:
        return None
    relative_parts = parts[3:]
    if not relative_parts:
        return PurePosixPath(".")
    if any(
        part in {"", ".", ".."} or "\\" in part or ":" in part
        for part in relative_parts
    ):
        raise RuntimeError(f"unsafe path in skill archive: {member.name}")
    return PurePosixPath(*relative_parts)


def extract_skill_archive(data: bytes, destination: Path) -> Path:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    selected: dict[PurePosixPath, tarfile.TarInfo] = {}
    total_size = 0
    archive_root: str | None = None

    try:
        archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except tarfile.TarError as exc:
        raise RuntimeError("unable to read skill archive") from exc

    with archive:
        for member in archive.getmembers():
            relative = safe_relative_member(member)
            if relative is None:
                continue
            root = PurePosixPath(member.name).parts[0]
            if archive_root is None:
                archive_root = root
            elif root != archive_root:
                raise RuntimeError("skill archive contains multiple top-level roots")
            if member.issym() or member.islnk():
                raise RuntimeError(
                    f"symbolic and hard links are not allowed in skill archive: {member.name}"
                )
            if not member.isdir() and not member.isfile():
                raise RuntimeError(
                    f"unsupported member type in skill archive: {member.name}"
                )
            if relative in selected:
                raise RuntimeError(f"duplicate path in skill archive: {relative}")
            if member.isfile():
                if member.size < 0:
                    raise RuntimeError(f"invalid file size in skill archive: {member.name}")
                total_size += member.size
                if total_size > SKILL_LIMIT:
                    raise RuntimeError("extracted skill exceeds the size limit")
            selected[relative] = member

        missing = REQUIRED_SKILL_PATHS - set(selected)
        if missing:
            rendered = ", ".join(sorted(path.as_posix() for path in missing))
            raise RuntimeError(f"skill archive is missing required paths: {rendered}")

        for relative, member in sorted(
            selected.items(), key=lambda item: item[0].as_posix()
        ):
            if relative == PurePosixPath("."):
                continue
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source: BinaryIO | None = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"unable to read skill archive member: {member.name}")
            with source, target.open("wb") as output:
                remaining = member.size
                while remaining:
                    chunk = source.read(min(64 * 1024, remaining))
                    if not chunk:
                        raise RuntimeError(
                            f"skill archive member ended early: {member.name}"
                        )
                    output.write(chunk)
                    remaining -= len(chunk)

    return destination


def install_downloaded_skill(
    archive_data: bytes,
    target: Path,
    *,
    replace: bool,
) -> None:
    with tempfile.TemporaryDirectory(prefix="agent-policy-remote-install-") as temporary:
        source = extract_skill_archive(archive_data, Path(temporary) / "skill")
        installer = source / "scripts" / "install.py"
        command = [sys.executable, str(installer), str(target)]
        if replace:
            command.append("--replace")
        subprocess.run(command, check=True)


def require_full_sha(value: str, label: str) -> str:
    if FULL_SHA.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full lowercase commit SHA")
    return value


def require_no_symlink_components(path: Path) -> None:
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f"path contains a symbolic-link component: {current}")
        if not current.exists():
            break


def preflight_attestation_destination(target: Path, attestation_path: Path) -> None:
    target = target.expanduser().absolute()
    attestation_path = attestation_path.expanduser().absolute()
    if (
        attestation_path == target
        or target in attestation_path.parents
        or attestation_path in target.parents
    ):
        raise ValueError(
            "installation attestation must be outside the installed skill tree; "
            "path overlap in either direction is forbidden"
        )

    parent = attestation_path.parent
    require_no_symlink_components(parent)
    parent.mkdir(parents=True, exist_ok=True)
    require_no_symlink_components(parent)
    if attestation_path.exists() or attestation_path.is_symlink():
        raise ValueError("installation attestation destination must not already exist")

    source_fd, source_name = tempfile.mkstemp(
        prefix=f".{attestation_path.name}.preflight-source-",
        dir=parent,
    )
    destination_fd, destination_name = tempfile.mkstemp(
        prefix=f".{attestation_path.name}.preflight-destination-",
        dir=parent,
    )
    source = Path(source_name)
    destination = Path(destination_name)
    try:
        os.close(destination_fd)
        destination.unlink()
        with os.fdopen(source_fd, "wb") as output:
            output.write(b"attestation-preflight\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(source, destination)
    finally:
        if source.exists():
            source.unlink()
        if destination.exists():
            destination.unlink()


def hash_regular_file(path: Path, *, remaining_limit: int) -> tuple[str, int]:
    stat = path.stat(follow_symlinks=False)
    if stat.st_nlink != 1:
        raise RuntimeError(f"installed skill contains a hard-linked file: {path}")
    if stat.st_size < 0 or stat.st_size > remaining_limit:
        raise RuntimeError("installed skill exceeds the size limit")

    digest = hashlib.sha256()
    consumed = 0
    with path.open("rb") as source:
        while True:
            chunk = source.read(min(64 * 1024, remaining_limit - consumed + 1))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > remaining_limit:
                raise RuntimeError("installed skill exceeds the size limit")
            digest.update(chunk)
    if consumed != stat.st_size:
        raise RuntimeError(f"installed skill file changed while hashing: {path}")
    return digest.hexdigest(), consumed


def installed_tree_inventory(target: Path) -> dict[str, dict[str, str]]:
    target = target.expanduser().absolute()
    require_no_symlink_components(target)
    if not target.is_dir():
        raise RuntimeError(f"installed skill directory is missing: {target}")

    entries: dict[str, dict[str, str]] = {}
    total_size = 0
    for path in sorted(target.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RuntimeError(f"installed skill contains a symbolic link: {path}")
        relative = path.relative_to(target).as_posix()
        if path.is_dir():
            entries[relative] = {"type": "directory"}
            continue
        if not path.is_file():
            raise RuntimeError(f"installed skill contains a non-regular file: {path}")
        digest, consumed = hash_regular_file(
            path,
            remaining_limit=SKILL_LIMIT - total_size,
        )
        total_size += consumed
        entries[relative] = {"type": "file", "sha256": digest}

    missing = [
        path.as_posix()
        for path in REQUIRED_SKILL_PATHS
        if entries.get(path.as_posix(), {}).get("type") != "file"
    ]
    if missing:
        rendered = ", ".join(sorted(missing))
        raise RuntimeError(f"installed skill is missing required paths: {rendered}")
    if not entries:
        raise RuntimeError("installed skill contains no paths")
    return entries


def installed_file_digests(target: Path) -> dict[str, str]:
    inventory = installed_tree_inventory(target)
    return {
        path: entry["sha256"]
        for path, entry in inventory.items()
        if entry["type"] == "file"
    }


def installation_attestation(
    target: Path,
    *,
    installer_revision: str,
) -> dict[str, object]:
    installer_revision = require_full_sha(installer_revision, "installer revision")
    root = target.expanduser().absolute()
    return {
        "schema_version": 1,
        "installer": {
            "repository": TOOLCHAIN_REPOSITORY,
            "revision": installer_revision,
            "path": INSTALLER_PATH,
        },
        "skill_source": {
            "repository": TOOLCHAIN_REPOSITORY,
            "revision": SKILL_SOURCE_REVISION,
            "path": SKILL_SOURCE_PATH,
        },
        "installation": {
            "root": str(root),
            "entries": installed_tree_inventory(root),
        },
    }


def write_installation_attestation(
    target: Path,
    attestation_path: Path,
    *,
    installer_revision: str,
) -> None:
    target = target.expanduser().absolute()
    attestation_path = attestation_path.expanduser().absolute()
    preflight_attestation_destination(target, attestation_path)
    value = installation_attestation(target, installer_revision=installer_revision)
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{attestation_path.name}.",
        suffix=".tmp",
        dir=attestation_path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(rendered)
            output.flush()
            os.fsync(output.fileno())
        # Publish only a fully written artifact and fail atomically if another
        # path appeared after preflight. Trust-root rotation is a separate
        # deployment operation; this installer never overwrites prior evidence.
        os.link(temporary, attestation_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_installation_attestation(path: Path) -> dict[str, object]:
    path = path.expanduser().absolute()
    require_no_symlink_components(path)
    if not path.is_file():
        raise RuntimeError(f"installation attestation is missing: {path}")
    if path.stat(follow_symlinks=False).st_nlink != 1:
        raise RuntimeError("installation attestation must not be hard linked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("installation attestation is invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("installation attestation must be a JSON object")
    return value


def validated_attestation_entries(
    target: Path,
    attestation_path: Path,
    *,
    installer_revision: str,
) -> dict[str, dict[str, str]]:
    target = target.expanduser().absolute()
    installer_revision = require_full_sha(installer_revision, "installer revision")
    actual = load_installation_attestation(attestation_path)
    if set(actual) != {"schema_version", "installer", "skill_source", "installation"}:
        raise RuntimeError("installation attestation has unexpected top-level fields")
    if actual.get("schema_version") != 1:
        raise RuntimeError("installation attestation schema version is unsupported")
    if actual.get("installer") != {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": installer_revision,
        "path": INSTALLER_PATH,
    }:
        raise RuntimeError("installation attestation installer identity does not match")
    if actual.get("skill_source") != {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": SKILL_SOURCE_REVISION,
        "path": SKILL_SOURCE_PATH,
    }:
        raise RuntimeError("installation attestation skill-source identity does not match")
    installation = actual.get("installation")
    if not isinstance(installation, dict) or set(installation) != {"root", "entries"}:
        raise RuntimeError("installation attestation installation record is invalid")
    if installation.get("root") != str(target):
        raise RuntimeError("installation attestation root does not match installed skill")
    entries = installation.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise RuntimeError("installation attestation entries are invalid")

    result: dict[str, dict[str, str]] = {}
    for relative, metadata in entries.items():
        if not isinstance(relative, str) or not relative:
            raise RuntimeError("installation attestation path is invalid")
        pure = PurePosixPath(relative)
        if (
            pure.is_absolute()
            or pure.as_posix() != relative
            or any(part in {"", ".", ".."} or "\\" in part or ":" in part for part in pure.parts)
        ):
            raise RuntimeError(f"installation attestation path is unsafe: {relative}")
        if not isinstance(metadata, dict):
            raise RuntimeError(f"installation attestation entry is invalid: {relative}")
        if metadata == {"type": "directory"}:
            result[relative] = {"type": "directory"}
            continue
        digest = metadata.get("sha256")
        if (
            set(metadata) != {"type", "sha256"}
            or metadata.get("type") != "file"
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise RuntimeError(f"installation attestation entry is invalid: {relative}")
        result[relative] = {"type": "file", "sha256": digest}
    return dict(sorted(result.items()))


def verify_installation_attestation(
    target: Path,
    attestation_path: Path,
    *,
    installer_revision: str,
) -> None:
    expected_entries = validated_attestation_entries(
        target,
        attestation_path,
        installer_revision=installer_revision,
    )
    if installed_tree_inventory(target) != expected_entries:
        raise RuntimeError("installation attestation does not match installed skill tree")


def verify_run_image(
    target: Path,
    run_image: Path,
    attestation_path: Path,
    *,
    installer_revision: str,
) -> None:
    expected_entries = validated_attestation_entries(
        target,
        attestation_path,
        installer_revision=installer_revision,
    )
    if installed_tree_inventory(run_image) != expected_entries:
        raise RuntimeError("review-run bootstrap image does not match installation attestation")


def _copy_attested_file(
    source: Path,
    destination: Path,
    *,
    expected_digest: str,
    remaining_limit: int,
) -> int:
    if source.is_symlink() or not source.is_file():
        raise RuntimeError(f"attested source file is not regular: {source}")
    stat = source.stat(follow_symlinks=False)
    if stat.st_nlink != 1:
        raise RuntimeError(f"attested source file is hard linked: {source}")
    if stat.st_size < 0 or stat.st_size > remaining_limit:
        raise RuntimeError("installed skill exceeds the size limit")

    digest = hashlib.sha256()
    consumed = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as input_file, destination.open("xb") as output_file:
        while True:
            chunk = input_file.read(min(64 * 1024, remaining_limit - consumed + 1))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > remaining_limit:
                raise RuntimeError("installed skill exceeds the size limit")
            digest.update(chunk)
            output_file.write(chunk)
        output_file.flush()
        os.fsync(output_file.fileno())
    if consumed != stat.st_size or digest.hexdigest() != expected_digest:
        raise RuntimeError(f"attested source file changed while copying: {source}")
    return consumed


def materialize_run_image(
    target: Path,
    run_image: Path,
    attestation_path: Path,
    *,
    installer_revision: str,
) -> None:
    target = target.expanduser().absolute()
    run_image = run_image.expanduser().absolute()
    attestation_path = attestation_path.expanduser().absolute()
    verify_installation_attestation(
        target,
        attestation_path,
        installer_revision=installer_revision,
    )
    entries = validated_attestation_entries(
        target,
        attestation_path,
        installer_revision=installer_revision,
    )

    if run_image == target or target in run_image.parents or run_image in target.parents:
        raise ValueError("review-run bootstrap image must be outside the installed skill tree")
    if run_image.exists() or run_image.is_symlink():
        raise ValueError("review-run bootstrap image destination must not already exist")
    parent = run_image.parent
    require_no_symlink_components(parent)
    parent.mkdir(parents=True, exist_ok=True)
    require_no_symlink_components(parent)

    staging = Path(
        tempfile.mkdtemp(prefix=f".{run_image.name}.staging-", dir=parent)
    )
    finalized = False
    try:
        total_size = 0
        directories = [
            relative for relative, metadata in entries.items() if metadata["type"] == "directory"
        ]
        for relative in sorted(
            directories,
            key=lambda value: (len(PurePosixPath(value).parts), value),
        ):
            staging.joinpath(*PurePosixPath(relative).parts).mkdir(parents=True, exist_ok=True)
        for relative, metadata in entries.items():
            if metadata["type"] != "file":
                continue
            source = target.joinpath(*PurePosixPath(relative).parts)
            destination = staging.joinpath(*PurePosixPath(relative).parts)
            total_size += _copy_attested_file(
                source,
                destination,
                expected_digest=metadata["sha256"],
                remaining_limit=SKILL_LIMIT - total_size,
            )
        if installed_tree_inventory(staging) != entries:
            raise RuntimeError("staged review-run bootstrap image does not match attestation")
        os.replace(staging, run_image)
        finalized = True
        if installed_tree_inventory(run_image) != entries:
            raise RuntimeError("finalized review-run bootstrap image does not match attestation")
    finally:
        if not finalized and staging.exists():
            shutil.rmtree(staging)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install, verify, or materialize the immutable agent-policy skill "
            f"distribution from {TOOLCHAIN_REPOSITORY}@{SKILL_SOURCE_REVISION}."
        )
    )
    parser.add_argument("target", type=Path, help="Destination agent-policy skill directory")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing installation only when its skill identity matches.",
    )
    parser.add_argument(
        "--attestation",
        type=Path,
        help=(
            "Deployment-managed path outside the skill tree for the installation "
            "attestation."
        ),
    )
    parser.add_argument(
        "--installer-revision",
        help=(
            "Full SHA of this installer script as independently pinned by the "
            "deployment. Required with attestation verification/materialization."
        ),
    )
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify an existing installation against --attestation without installing.",
    )
    operation.add_argument(
        "--materialize-run-image",
        type=Path,
        help=(
            "Verify the installation, then atomically materialize and post-copy verify "
            "a deployment-managed bootstrap run-image candidate."
        ),
    )
    operation.add_argument(
        "--verify-run-image",
        type=Path,
        help=(
            "Verify a deployment-protected bootstrap run image against the external "
            "installation attestation."
        ),
    )
    args = parser.parse_args(argv)
    if (args.verify_only or args.materialize_run_image or args.verify_run_image) and args.replace:
        parser.error("verification/materialization operations cannot be combined with --replace")
    needs_attestation = bool(
        args.verify_only
        or args.materialize_run_image is not None
        or args.verify_run_image is not None
    )
    if needs_attestation and args.attestation is None:
        parser.error("verification/materialization operations require --attestation")
    if (args.attestation is None) != (args.installer_revision is None):
        parser.error("--attestation and --installer-revision must be supplied together")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.verify_only:
            verify_installation_attestation(
                args.target,
                args.attestation,
                installer_revision=args.installer_revision,
            )
            print(f"Verified agent-policy skill installation at {args.target}.")
            return 0
        if args.materialize_run_image is not None:
            materialize_run_image(
                args.target,
                args.materialize_run_image,
                args.attestation,
                installer_revision=args.installer_revision,
            )
            print(
                "Materialized and post-copy verified agent-policy bootstrap run image at "
                f"{args.materialize_run_image}. The deployment must now enforce its "
                "read-only/immutable trust boundary before execution and then run "
                "--verify-run-image."
            )
            return 0
        if args.verify_run_image is not None:
            verify_run_image(
                args.target,
                args.verify_run_image,
                args.attestation,
                installer_revision=args.installer_revision,
            )
            print(
                "Verified protected agent-policy bootstrap run image at "
                f"{args.verify_run_image}."
            )
            return 0

        if args.attestation is not None:
            preflight_attestation_destination(args.target, args.attestation)
        data = download_archive()
        install_downloaded_skill(
            data,
            args.target.expanduser().absolute(),
            replace=args.replace,
        )
        if args.attestation is not None:
            write_installation_attestation(
                args.target,
                args.attestation,
                installer_revision=args.installer_revision,
            )
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"agent-policy remote installer error: {exc}", file=sys.stderr)
        return 1
    print(
        f"Installed agent-policy skill from "
        f"{TOOLCHAIN_REPOSITORY}@{SKILL_SOURCE_REVISION}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())