from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

from runtime import (  # noqa: E402
    RuntimeIdentity,
    RuntimePin,
    build_runtime,
    cache_root,
    download_runtime_lock,
    ensure_runtime,
    identity_for,
    installed_distributions,
    marker_path,
    parse_runtime_lock,
    platform_token,
    python_token,
    sanitized_environment,
    select_pin,
    verify_installed_set,
    venv_python,
)

ATTESTATION_SCHEMA = 1
RUNTIME_LIMIT = 512 * 1024 * 1024
SKIPPED_SUFFIXES = (".pyc", ".pyo")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_no_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"path contains a symbolic-link component: {current}")
        if not current.exists():
            break


def _safe_relative(relative: str) -> str:
    pure = PurePosixPath(relative)
    if (
        not relative
        or pure.is_absolute()
        or pure.as_posix() != relative
        or any(
            part in {"", ".", ".."} or "\\" in part or ":" in part
            for part in pure.parts
        )
    ):
        raise ValueError(f"runtime image path is unsafe: {relative!r}")
    return relative


def _skip_name(name: str) -> bool:
    return name == "__pycache__" or name.endswith(SKIPPED_SUFFIXES)


def _walk_normalized_sources(
    source_root: Path,
) -> list[tuple[str, Path, int]]:
    root = source_root.resolve(strict=True)
    result: list[tuple[str, Path, int]] = []

    def visit(directory: Path, prefix: PurePosixPath, stack: tuple[Path, ...]) -> None:
        resolved_directory = directory.resolve(strict=True)
        if resolved_directory in stack:
            raise ValueError("runtime cache contains a symbolic-link directory cycle")
        next_stack = (*stack, resolved_directory)
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda item: item.name)
        for entry in ordered:
            if _skip_name(entry.name):
                continue
            relative = prefix / entry.name
            relative_text = _safe_relative(relative.as_posix())
            path = Path(entry.path)
            if entry.is_symlink():
                target = path.resolve(strict=True)
                if target.is_dir():
                    try:
                        target.relative_to(root)
                    except ValueError as exc:
                        raise ValueError(
                            "runtime cache contains a directory symlink outside its root: "
                            f"{relative_text}"
                        ) from exc
                    visit(target, relative, next_stack)
                    continue
                if not target.is_file():
                    raise ValueError(
                        f"runtime cache symlink does not resolve to a file: {relative_text}"
                    )
                stat = target.stat()
                mode = 0o755 if stat.st_mode & 0o111 else 0o644
                result.append((relative_text, target, mode))
                continue
            if entry.is_dir(follow_symlinks=False):
                visit(path, relative, next_stack)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise ValueError(
                    f"runtime cache contains a non-regular path: {relative_text}"
                )
            stat = path.stat(follow_symlinks=False)
            mode = 0o755 if stat.st_mode & 0o111 else 0o644
            result.append((relative_text, path, mode))
    visit(root, PurePosixPath("."), ())
    paths = [relative for relative, _, _ in result]
    if len(paths) != len(set(paths)):
        raise ValueError("normalized runtime image contains duplicate paths")
    return result


def _copy_normalized_runtime(source: Path, destination: Path) -> None:
    sources = _walk_normalized_sources(source)
    total = 0
    for relative, source_file, mode in sources:
        stat = source_file.stat()
        total += stat.st_size
        if total > RUNTIME_LIMIT:
            raise ValueError("normalized runtime image exceeds the size limit")
        target = destination.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        copied = 0
        with source_file.open("rb") as input_file, target.open("xb") as output_file:
            while True:
                chunk = input_file.read(64 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > stat.st_size or total - stat.st_size + copied > RUNTIME_LIMIT:
                    raise ValueError("runtime source changed size while being copied")
                digest.update(chunk)
                output_file.write(chunk)
            output_file.flush()
            os.fsync(output_file.fileno())
        if copied != stat.st_size:
            raise ValueError("runtime source changed size while being copied")
        target.chmod(mode)


def _expected_directories(files: set[str]) -> set[str]:
    result: set[str] = set()
    for relative in files:
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            result.add(parent.as_posix())
            parent = parent.parent
    return result


def image_inventory(root: Path) -> dict[str, dict[str, Any]]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("runtime image must be a regular directory")
    files: dict[str, dict[str, Any]] = {}
    directories: set[str] = set()
    total = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = _safe_relative(path.relative_to(root).as_posix())
        if path.is_symlink():
            raise ValueError(f"runtime image contains a symbolic link: {relative}")
        if path.is_dir():
            directories.add(relative)
            continue
        if not path.is_file():
            raise ValueError(f"runtime image contains a non-regular path: {relative}")
        stat = path.stat(follow_symlinks=False)
        if stat.st_nlink != 1:
            raise ValueError(f"runtime image contains a hard-linked file: {relative}")
        total += stat.st_size
        if total > RUNTIME_LIMIT:
            raise ValueError("runtime image exceeds the size limit")
        files[relative] = {
            "type": "file",
            "mode": "755" if stat.st_mode & 0o111 else "644",
            "sha256": _sha256_bytes(path.read_bytes()),
        }
    expected_directories = _expected_directories(set(files))
    if directories != expected_directories:
        raise ValueError("runtime image contains empty or unexpected directories")
    entries: dict[str, dict[str, Any]] = {
        relative: {"type": "directory"} for relative in sorted(directories)
    }
    entries.update(files)
    if not files:
        raise ValueError("runtime image is empty")
    return dict(sorted(entries.items()))


def _marker(root: Path) -> dict[str, Any]:
    try:
        value = json.loads(marker_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("runtime marker is missing or invalid") from exc
    if not isinstance(value, dict):
        raise ValueError("runtime marker must be a JSON object")
    return value


def _identity_from_marker(marker: dict[str, Any]) -> RuntimeIdentity:
    value = marker.get("identity")
    if not isinstance(value, dict):
        raise ValueError("runtime marker identity is invalid")
    required = {"repository", "revision", "lock_sha256", "python", "platform"}
    if set(value) != required or not all(isinstance(item, str) for item in value.values()):
        raise ValueError("runtime marker identity is invalid")
    return RuntimeIdentity(
        repository=value["repository"],
        revision=value["revision"],
        lock_sha256=value["lock_sha256"],
        python=value["python"],
        platform=value["platform"],
    )


def _validate_canonical_runtime(root: Path, pin: RuntimePin) -> tuple[RuntimeIdentity, dict[str, str]]:
    marker = _marker(root)
    identity = _identity_from_marker(marker)
    if identity.repository != pin.repository or identity.revision != pin.revision:
        raise ValueError("runtime marker does not match the selected lock pin")
    if identity.python != python_token() or identity.platform != platform_token():
        raise ValueError("runtime marker does not match the current Python/platform identity")
    lock_path = root / "requirements-runtime.lock"
    lock_data = lock_path.read_bytes()
    if _sha256_bytes(lock_data) != identity.lock_sha256:
        raise ValueError("runtime lock bytes do not match the runtime identity")
    requirements = parse_runtime_lock(lock_data.decode("utf-8"))
    env = sanitized_environment()
    python = venv_python(root)
    subprocess.run(
        [str(python), "-I", "-m", "pip", "check"],
        check=True,
        env=env,
    )
    verify_installed_set(python, requirements, pin, env)
    return identity, installed_distributions(python, env)


def _attestation_payload(
    pin: RuntimePin,
    identity: RuntimeIdentity,
    distributions: dict[str, str],
    entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": ATTESTATION_SCHEMA,
        "runtime": identity.payload(),
        "selected_pin": {
            "repository": pin.repository,
            "revision": pin.revision,
        },
        "distributions": dict(sorted(distributions.items())),
        "entries": entries,
    }


def _load_attestation(path: Path) -> dict[str, Any]:
    target = path.expanduser().absolute()
    _require_no_symlink_components(target)
    if target.is_symlink() or not target.is_file():
        raise ValueError("runtime attestation is missing or is not a regular file")
    if target.stat(follow_symlinks=False).st_nlink != 1:
        raise ValueError("runtime attestation must not be hard linked")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("runtime attestation is invalid JSON") from exc
    if not isinstance(value, dict) or value.get("schema_version") != ATTESTATION_SCHEMA:
        raise ValueError("runtime attestation schema is invalid")
    return value


def _write_new_attestation(path: Path, value: dict[str, Any]) -> None:
    target = path.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError("runtime attestation destination must not already exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    _require_no_symlink_components(target.parent)
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(rendered)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def create_attestation(repository: Path, attestation: Path) -> dict[str, Any]:
    pin = select_pin(repository)
    private_root = Path(
        tempfile.mkdtemp(prefix=".agent-policy-runtime-attest-", dir=attestation.parent)
    )
    try:
        lock_data = download_runtime_lock(pin)
        identity = identity_for(pin, lock_data)
        raw_runtime = private_root / "raw"
        build_runtime(raw_runtime, identity, pin, lock_data)
        identity, distributions = _validate_canonical_runtime(raw_runtime, pin)
        normalized = private_root / "normalized"
        normalized.mkdir()
        _copy_normalized_runtime(raw_runtime, normalized)
        entries = image_inventory(normalized)
        value = _attestation_payload(pin, identity, distributions, entries)
        _write_new_attestation(attestation, value)
        return value
    finally:
        shutil.rmtree(private_root, ignore_errors=True)


def _require_external_destination(repository: Path, destination: Path) -> Path:
    target = destination.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError("runtime image destination must not already exist")
    try:
        target.relative_to(repository.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("runtime image must be outside the trusted-base snapshot")
    target.parent.mkdir(parents=True, exist_ok=True)
    _require_no_symlink_components(target.parent)
    return target


def _attestation_for_pin(value: dict[str, Any], pin: RuntimePin) -> dict[str, Any]:
    selected = value.get("selected_pin")
    if selected != {"repository": pin.repository, "revision": pin.revision}:
        raise ValueError("runtime attestation does not match the trusted-base lock pin")
    runtime = value.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("runtime attestation identity is invalid")
    if runtime.get("python") != python_token() or runtime.get("platform") != platform_token():
        raise ValueError("runtime attestation does not match current Python/platform identity")
    entries = value.get("entries")
    distributions = value.get("distributions")
    if not isinstance(entries, dict) or not isinstance(distributions, dict):
        raise ValueError("runtime attestation inventory is invalid")
    return value


def materialize_image(
    repository: Path,
    attestation: Path,
    destination: Path,
) -> dict[str, Any]:
    pin = select_pin(repository)
    expected = _attestation_for_pin(_load_attestation(attestation), pin)
    source = ensure_runtime(pin, root=cache_root())
    target = _require_external_destination(repository, destination)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
    finalized = False
    try:
        _copy_normalized_runtime(source, staging)
        if image_inventory(staging) != expected["entries"]:
            raise ValueError("normalized runtime candidate does not match protected attestation")
        os.replace(staging, target)
        finalized = True
    finally:
        if not finalized and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return expected


def verify_image(
    repository: Path,
    attestation: Path,
    image: Path,
    *,
    execute_probe: bool = True,
) -> dict[str, Any]:
    pin = select_pin(repository)
    expected = _attestation_for_pin(_load_attestation(attestation), pin)
    target = image.expanduser().absolute()
    if image_inventory(target) != expected["entries"]:
        raise ValueError("runtime image does not match protected attestation")
    if execute_probe:
        python = venv_python(target)
        actual_distributions = installed_distributions(python, sanitized_environment())
        if actual_distributions != expected["distributions"]:
            raise ValueError("runtime image distribution set does not match attestation")
        subprocess.run(
            [str(python), "-I", "-m", "pip", "check"],
            check=True,
            env=sanitized_environment(),
        )
    return expected


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Create, materialize, or verify trusted-review runtime images."
    )
    root.add_argument("--repository", required=True, type=Path)
    sub = root.add_subparsers(dest="command", required=True)
    attest = sub.add_parser("attest")
    attest.add_argument("--attestation", required=True, type=Path)
    materialize = sub.add_parser("materialize")
    materialize.add_argument("--attestation", required=True, type=Path)
    materialize.add_argument("--destination", required=True, type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("--attestation", required=True, type=Path)
    verify.add_argument("--image", required=True, type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        repository = args.repository.expanduser().absolute()
        if repository.is_symlink() or not repository.is_dir():
            raise ValueError("trusted-base snapshot must be a regular directory")
        if args.command == "attest":
            value = create_attestation(repository, args.attestation)
            status = "ATTESTED_CANONICAL_RUNTIME"
        elif args.command == "materialize":
            value = materialize_image(repository, args.attestation, args.destination)
            status = "MATERIALIZED_NOT_YET_TRUSTED"
        else:
            value = verify_image(repository, args.attestation, args.image)
            status = "VERIFIED_FROZEN_RUNTIME"
        result = {
            "status": status,
            "runtime": value["runtime"],
            "selected_pin": value["selected_pin"],
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"trusted review runtime error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
