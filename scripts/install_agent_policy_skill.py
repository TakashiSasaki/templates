#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"
INSTALLER_PATH = "scripts/install_agent_policy_skill.py"
SKILL_SOURCE_REVISION = "499dc8699e3dcd9f460d603718bdf2266c45e7ca"
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


def installed_file_digests(target: Path) -> dict[str, str]:
    target = target.expanduser().absolute()
    require_no_symlink_components(target)
    if not target.is_dir():
        raise RuntimeError(f"installed skill directory is missing: {target}")

    digests: dict[str, str] = {}
    for path in sorted(target.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RuntimeError(f"installed skill contains a symbolic link: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"installed skill contains a non-regular file: {path}")
        relative = path.relative_to(target).as_posix()
        digests[relative] = hashlib.sha256(path.read_bytes()).hexdigest()

    missing = {path.as_posix() for path in REQUIRED_SKILL_PATHS} - set(digests)
    if missing:
        rendered = ", ".join(sorted(missing))
        raise RuntimeError(f"installed skill is missing required paths: {rendered}")
    if not digests:
        raise RuntimeError("installed skill contains no files")
    return digests


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
            "files": installed_file_digests(root),
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
    if attestation_path == target or target in attestation_path.parents:
        raise ValueError("installation attestation must be outside the installed skill tree")
    require_no_symlink_components(attestation_path.parent)
    if attestation_path.is_symlink():
        raise ValueError("installation attestation path must not be a symbolic link")
    attestation_path.parent.mkdir(parents=True, exist_ok=True)
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
        os.replace(temporary, attestation_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_installation_attestation(path: Path) -> dict[str, object]:
    path = path.expanduser().absolute()
    require_no_symlink_components(path)
    if not path.is_file():
        raise RuntimeError(f"installation attestation is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("installation attestation is invalid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError("installation attestation must be a JSON object")
    return value


def verify_installation_attestation(
    target: Path,
    attestation_path: Path,
    *,
    installer_revision: str,
) -> None:
    expected = installation_attestation(
        target,
        installer_revision=require_full_sha(installer_revision, "installer revision"),
    )
    actual = load_installation_attestation(attestation_path)
    if actual != expected:
        raise RuntimeError("installation attestation does not match installed skill bytes")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install or verify the immutable agent-policy skill distribution from "
            f"{TOOLCHAIN_REPOSITORY}@{SKILL_SOURCE_REVISION}."
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
            "deployment. Required with --attestation or --verify-only."
        ),
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify an existing installation against --attestation without installing.",
    )
    args = parser.parse_args(argv)
    if args.verify_only and args.replace:
        parser.error("--verify-only cannot be combined with --replace")
    if args.verify_only and args.attestation is None:
        parser.error("--verify-only requires --attestation")
    if (args.attestation is None) != (args.installer_revision is None):
        parser.error("--attestation and --installer-revision must be supplied together")
    if args.verify_only and args.installer_revision is None:
        parser.error("--verify-only requires --installer-revision")
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
