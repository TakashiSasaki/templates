from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
REGULAR_MODES = {"100644": 0o644, "100755": 0o755}
SNAPSHOT_LIMIT = 256 * 1024 * 1024


def require_full_sha(value: str) -> str:
    if FULL_SHA.fullmatch(value) is None:
        raise ValueError("base revision must be a full lowercase commit SHA")
    return value


def require_trusted_git(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("trusted Git executable path must be absolute")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("trusted Git executable must resolve to a regular file")
    return resolved


def require_object_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("Git object repository must be a directory")
    return resolved


def git_environment() -> dict[str, str]:
    result = dict(os.environ)
    result.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
    for name in (
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_OBJECT_DIRECTORY",
        "GIT_INDEX_FILE",
        "GIT_WORK_TREE",
    ):
        result.pop(name, None)
    return result


def run_git(
    git: Path,
    repository: Path,
    arguments: list[str],
    *,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(git), "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=text,
        env=git_environment(),
    )


def safe_relative(raw: str) -> str:
    pure = PurePosixPath(raw)
    if (
        not raw
        or pure.is_absolute()
        or pure.as_posix() != raw
        or any(part in {"", ".", ".."} or "\\" in part or ":" in part for part in pure.parts)
    ):
        raise ValueError(f"Git tree contains an unsafe path: {raw!r}")
    return raw


def git_blob_oid(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def expected_tree(
    git: Path,
    repository: Path,
    revision: str,
) -> tuple[str, dict[str, tuple[str, str]], set[str]]:
    revision = require_full_sha(revision)
    commit = run_git(git, repository, ["rev-parse", "--verify", f"{revision}^{{commit}}"])
    if commit.stdout.strip() != revision:
        raise RuntimeError("Git object repository did not resolve the requested base commit")
    tree = run_git(git, repository, ["rev-parse", "--verify", f"{revision}^{{tree}}"])
    tree_sha = tree.stdout.strip()
    if FULL_SHA.fullmatch(tree_sha) is None:
        raise RuntimeError("Git object repository returned an invalid tree identity")

    listing = run_git(
        git,
        repository,
        ["ls-tree", "-rz", "--full-tree", "-r", revision],
        text=False,
    )
    files: dict[str, tuple[str, str]] = {}
    directories: set[str] = set()
    for record in listing.stdout.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, object_id = metadata.decode("ascii").split(" ", 2)
            relative = safe_relative(raw_path.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("Git tree contains an unsupported entry") from exc
        if kind != "blob" or mode not in REGULAR_MODES:
            raise ValueError(
                f"trusted base contains an unsupported non-regular entry: {relative}"
            )
        if FULL_SHA.fullmatch(object_id) is None:
            raise ValueError(f"Git tree contains an invalid object identity: {relative}")
        if relative in files:
            raise ValueError(f"Git tree path is duplicated: {relative}")
        files[relative] = (mode, object_id)
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    if not files:
        raise ValueError("trusted base Git tree must contain at least one regular file")
    return tree_sha, dict(sorted(files.items())), directories


def require_external_destination(repository: Path, destination: Path) -> Path:
    target = destination.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError("trusted-base snapshot destination must not already exist")
    resolved_repository = repository.resolve()
    try:
        target.relative_to(resolved_repository)
    except ValueError:
        pass
    else:
        raise ValueError("trusted-base snapshot must be outside the Git object repository")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink():
        raise ValueError("trusted-base snapshot parent must not be a symbolic link")
    return target


def verify_snapshot_tree(
    snapshot: Path,
    files: dict[str, tuple[str, str]],
    directories: set[str],
) -> None:
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise ValueError("trusted-base snapshot is missing or is not a regular directory")
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    total = 0
    for path in sorted(snapshot.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(snapshot).as_posix()
        if path.is_symlink():
            raise ValueError(f"trusted-base snapshot contains a symbolic link: {relative}")
        if path.is_dir():
            actual_directories.add(relative)
            continue
        if not path.is_file():
            raise ValueError(f"trusted-base snapshot contains a non-regular path: {relative}")
        stat = path.stat(follow_symlinks=False)
        if stat.st_nlink != 1:
            raise ValueError(f"trusted-base snapshot contains a hard-linked file: {relative}")
        total += stat.st_size
        if total > SNAPSHOT_LIMIT:
            raise ValueError("trusted-base snapshot exceeds the size limit")
        actual_files.add(relative)
        expected = files.get(relative)
        if expected is None:
            continue
        expected_mode, expected_oid = expected
        actual_mode = "100755" if stat.st_mode & 0o111 else "100644"
        if actual_mode != expected_mode:
            raise ValueError(f"trusted-base snapshot mode mismatch: {relative}")
        if git_blob_oid(path.read_bytes()) != expected_oid:
            raise ValueError(f"trusted-base snapshot object mismatch: {relative}")
    if actual_files != set(files) or actual_directories != directories:
        raise ValueError("trusted-base snapshot path/type inventory does not match the Git tree")


def materialize(
    git: Path,
    repository: Path,
    revision: str,
    destination: Path,
) -> dict[str, str]:
    git = require_trusted_git(git)
    repository = require_object_repository(repository)
    tree_sha, files, directories = expected_tree(git, repository, revision)
    target = require_external_destination(repository, destination)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
    finalized = False
    try:
        process = subprocess.Popen(
            [str(git), "-C", str(repository), "archive", "--format=tar", revision],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_environment(),
        )
        assert process.stdout is not None
        assert process.stderr is not None
        seen_files: set[str] = set()
        seen_directories: set[str] = set()
        total = 0
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                relative = safe_relative(member.name.rstrip("/"))
                if member.isdir():
                    seen_directories.add(relative)
                    staging.joinpath(*PurePosixPath(relative).parts).mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    continue
                if not member.isfile() or relative not in files:
                    raise ValueError(
                        f"Git archive contains an unsupported entry: {relative}"
                    )
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError(f"Git archive file is unreadable: {relative}")
                content = source.read()
                total += len(content)
                if total > SNAPSHOT_LIMIT:
                    raise ValueError("trusted-base snapshot exceeds the size limit")
                mode, object_id = files[relative]
                if git_blob_oid(content) != object_id:
                    raise RuntimeError(f"Git archive object mismatch: {relative}")
                output = staging.joinpath(*PurePosixPath(relative).parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                output.chmod(REGULAR_MODES[mode])
                seen_files.add(relative)
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait() != 0:
            raise RuntimeError(f"trusted Git archive failed: {stderr.strip()}")
        if seen_files != set(files) or seen_directories != directories:
            raise RuntimeError("Git archive inventory does not match the exact base tree")
        verify_snapshot_tree(staging, files, directories)
        os.replace(staging, target)
        finalized = True
    finally:
        if not finalized and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return {"revision": revision, "tree": tree_sha, "snapshot": str(target)}


def verify(
    git: Path,
    repository: Path,
    revision: str,
    snapshot: Path,
) -> dict[str, str]:
    git = require_trusted_git(git)
    repository = require_object_repository(repository)
    tree_sha, files, directories = expected_tree(git, repository, revision)
    target = snapshot.expanduser().absolute()
    verify_snapshot_tree(target, files, directories)
    return {"revision": revision, "tree": tree_sha, "snapshot": str(target)}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Materialize or verify a deployment-frozen exact-base review snapshot."
    )
    root.add_argument("--git-executable", required=True, type=Path)
    root.add_argument("--object-repository", required=True, type=Path)
    root.add_argument("--base", required=True, type=require_full_sha)
    sub = root.add_subparsers(dest="command", required=True)
    materialize_parser = sub.add_parser("materialize")
    materialize_parser.add_argument("--destination", required=True, type=Path)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--snapshot", required=True, type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "materialize":
            result = materialize(
                args.git_executable,
                args.object_repository,
                args.base,
                args.destination,
            )
            result["status"] = "MATERIALIZED_NOT_YET_TRUSTED"
        else:
            result = verify(
                args.git_executable,
                args.object_repository,
                args.base,
                args.snapshot,
            )
            result["status"] = "VERIFIED_FROZEN_INPUT"
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"trusted review base error: {exc}", file=os.sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
