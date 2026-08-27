#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"
SKILL_SOURCE_REVISION = "e8ee87483ea97e6cce8f27e6438d98a5a7c724a7"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
ARCHIVE_LIMIT = 16 * 1024 * 1024
SKILL_LIMIT = 8 * 1024 * 1024
SKILL_PREFIX = ("skills", "composition")
INSTALLATION_RECEIPT = PurePosixPath("installation-receipt.json")
REQUIRED_SKILL_PATHS = frozenset(
    {
        PurePosixPath("SKILL.md"),
        PurePosixPath("runtime-manifest.json"),
        PurePosixPath("scripts/install.py"),
        PurePosixPath("scripts/run.py"),
        PurePosixPath("scripts/run_checkout.py"),
        PurePosixPath("scripts/runtime.py"),
        PurePosixPath("scripts/runtime_checkout.py"),
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
    request = urllib.request.Request(
        archive_url(revision),
        headers={"User-Agent": "composition-skill-installer/1"},
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
    relative = PurePosixPath(*relative_parts)
    if relative == INSTALLATION_RECEIPT:
        raise RuntimeError(
            "skill archive must not provide the reserved installation receipt path"
        )
    return relative


def extract_skill_archive(data: bytes, destination: Path) -> Path:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    selected: dict[PurePosixPath, tarfile.TarInfo] = {}
    total_size = 0
    archive_root: str | None = None

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                relative = safe_relative_member(member)
                if relative is None:
                    continue
                root = PurePosixPath(member.name).parts[0]
                if root in {"", ".", ".."} or "\\" in root or ":" in root:
                    raise RuntimeError(
                        f"unsafe root prefix in skill archive: {member.name}"
                    )
                if archive_root is None:
                    archive_root = root
                elif root != archive_root:
                    raise RuntimeError("skill archive contains multiple top-level roots")
                if member.issym() or member.islnk():
                    raise RuntimeError(
                        "symbolic and hard links are not allowed in skill archive: "
                        f"{member.name}"
                    )
                if not member.isdir() and not member.isfile():
                    raise RuntimeError(
                        f"unsupported member type in skill archive: {member.name}"
                    )
                if relative in selected:
                    raise RuntimeError(f"duplicate path in skill archive: {relative}")
                if member.isfile():
                    if member.size < 0:
                        raise RuntimeError(
                            f"invalid file size in skill archive: {member.name}"
                        )
                    total_size += member.size
                    if total_size > SKILL_LIMIT:
                        raise RuntimeError("extracted skill exceeds the size limit")
                selected[relative] = member

            missing = {
                path
                for path in REQUIRED_SKILL_PATHS
                if path not in selected or not selected[path].isfile()
            }
            if missing:
                rendered = ", ".join(sorted(path.as_posix() for path in missing))
                raise RuntimeError(f"skill archive is missing required files: {rendered}")

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
                    raise RuntimeError(
                        f"unable to read skill archive member: {member.name}"
                    )
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
    except tarfile.TarError as exc:
        raise RuntimeError(f"unable to read skill archive: {exc}") from exc

    return destination


def installation_receipt_payload(
    repository: str = TOOLCHAIN_REPOSITORY,
    revision: str = SKILL_SOURCE_REVISION,
) -> dict[str, object]:
    if repository != TOOLCHAIN_REPOSITORY:
        raise ValueError("skill source repository is unsupported")
    if FULL_SHA.fullmatch(revision) is None:
        raise ValueError("skill source revision must be a full lowercase SHA")
    return {
        "schema_version": 1,
        "source": {
            "repository": repository,
            "revision": revision,
        },
    }


def write_installation_receipt(
    source: Path,
    *,
    repository: str = TOOLCHAIN_REPOSITORY,
    revision: str = SKILL_SOURCE_REVISION,
) -> Path:
    path = source / INSTALLATION_RECEIPT.as_posix()
    if path.exists() or path.is_symlink():
        raise RuntimeError("reserved installation receipt path already exists")
    path.write_text(
        json.dumps(
            installation_receipt_payload(repository, revision),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def install_downloaded_skill(
    archive_data: bytes,
    target: Path,
    *,
    replace: bool,
) -> None:
    with tempfile.TemporaryDirectory(prefix="composition-remote-install-") as temporary:
        source = extract_skill_archive(archive_data, Path(temporary) / "skill")
        write_installation_receipt(source)
        installer = source / "scripts" / "install.py"
        command = [sys.executable, "-I", str(installer), str(target)]
        if replace:
            command.append("--replace")
        subprocess.run(command, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install the immutable Composition skill distribution from "
            f"{TOOLCHAIN_REPOSITORY}@{SKILL_SOURCE_REVISION}."
        )
    )
    parser.add_argument("target", type=Path, help="Destination Composition skill directory")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing installation only when its skill identity matches.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        data = download_archive()
        install_downloaded_skill(
            data,
            args.target.expanduser().absolute(),
            replace=args.replace,
        )
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"Composition remote installer error: {exc}", file=sys.stderr)
        return 1
    print(
        "Installed Composition skill from "
        f"{TOOLCHAIN_REPOSITORY}@{SKILL_SOURCE_REVISION}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
