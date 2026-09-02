from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

from runtime import (  # noqa: E402, I001
    RuntimeIdentity,
    RuntimePin,
    build_runtime,
    cache_root,
    download_runtime_lock,
    identity_for,
    parse_runtime_lock,
    platform_token,
    python_token,
    select_pin,
    verify_installed_set,
    venv_python,
)

ATTESTATION_SCHEMA = 1
RUNTIME_LIMIT = 512 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
SKIPPED_SUFFIXES = (".pyc", ".pyo")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
NORMALIZED_VENV_COMMAND = "command = <agent-policy-trusted-runtime>"
TRUSTED_ENVIRONMENT_KEYS = frozenset(
    {
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "TMPDIR",
    }
)


def trusted_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    supplied = os.environ if source is None else source
    result = {
        key: value
        for key, value in supplied.items()
        if key.upper() in TRUSTED_ENVIRONMENT_KEYS
    }
    result.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "LC_ALL": "C",
            "LANG": "C",
        }
    )
    return result


def _sha256_file(path: Path, *, remaining_limit: int) -> tuple[str, int]:
    stat = path.stat(follow_symlinks=False)
    if stat.st_nlink != 1:
        raise ValueError(f"runtime image contains a hard-linked file: {path}")
    if stat.st_size < 0 or stat.st_size > remaining_limit:
        raise ValueError("runtime image exceeds the size limit")
    digest = hashlib.sha256()
    consumed = 0
    with path.open("rb") as source:
        while True:
            chunk = source.read(min(CHUNK_SIZE, remaining_limit - consumed + 1))
            if not chunk:
                break
            consumed += len(chunk)
            if consumed > remaining_limit:
                raise ValueError("runtime image exceeds the size limit")
            digest.update(chunk)
    if consumed != stat.st_size:
        raise ValueError(f"runtime image file changed while hashing: {path}")
    return digest.hexdigest(), consumed


def _require_no_symlink_components(path: Path) -> None:
    absolute = path.expanduser().absolute()
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


def _is_dist_info_record(relative: PurePosixPath) -> bool:
    return relative.name == "RECORD" and any(
        part.endswith(".dist-info") for part in relative.parts[:-1]
    )


def _is_required_venv_launcher(relative: PurePosixPath) -> bool:
    if len(relative.parts) != 3 or relative.parts[0] != "venv":
        return False
    directory, name = relative.parts[1], relative.parts[2].lower()
    if directory == "bin":
        return name.startswith("python")
    if directory == "Scripts":
        return name.startswith("python") and name.endswith(".exe")
    return False


def _skip_normalized_path(relative: PurePosixPath) -> bool:
    if _is_dist_info_record(relative):
        return True
    if (
        len(relative.parts) == 3
        and relative.parts[0] == "venv"
        and relative.parts[1] in {"bin", "Scripts"}
    ):
        return not _is_required_venv_launcher(relative)
    return False


def _normalize_pyvenv_cfg(content: bytes) -> bytes:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("runtime pyvenv.cfg must be UTF-8") from exc
    found_command = False
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("command = "):
            lines.append(NORMALIZED_VENV_COMMAND)
            found_command = True
        else:
            lines.append(line)
    if not found_command:
        raise ValueError("runtime pyvenv.cfg is missing the venv creation command")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _overlaps(repository: Path, target: Path) -> bool:
    repository = repository.resolve()
    target = target.expanduser().absolute()
    try:
        target.relative_to(repository)
        return True
    except ValueError:
        pass
    try:
        repository.relative_to(target)
        return True
    except ValueError:
        return False


def _require_external_path(
    repository: Path,
    path: Path,
    *,
    label: str,
    must_exist: bool,
) -> Path:
    target = path.expanduser().absolute()
    _require_no_symlink_components(target)
    if _overlaps(repository, target):
        raise ValueError(f"{label} must be outside the trusted-base snapshot")
    if must_exist:
        if target.is_symlink() or not target.exists():
            raise ValueError(f"{label} is missing")
    return target


def _walk_normalized_sources(source_root: Path) -> list[tuple[str, Path, int]]:
    _require_no_symlink_components(source_root)
    root = source_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("runtime cache root must be a directory")
    trusted_python = Path(sys.executable).resolve(strict=True)
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
            if _skip_normalized_path(relative):
                continue
            relative_text = _safe_relative(relative.as_posix())
            path = Path(entry.path)
            if entry.is_symlink():
                target = path.resolve(strict=True)
                try:
                    target.relative_to(root)
                    target_inside_root = True
                except ValueError:
                    target_inside_root = False
                if target.is_dir():
                    if not target_inside_root:
                        raise ValueError(
                            "runtime cache contains a directory symlink outside its root: "
                            f"{relative_text}"
                        )
                    visit(target, relative, next_stack)
                    continue
                if not target.is_file():
                    raise ValueError(
                        f"runtime cache symlink does not resolve to a file: {relative_text}"
                    )
                if not target_inside_root:
                    if not _is_required_venv_launcher(relative):
                        raise ValueError(
                            "runtime cache contains a file symlink outside its root: "
                            f"{relative_text}"
                        )
                    if target != trusted_python:
                        raise ValueError(
                            "runtime cache Python launcher does not resolve to the trusted "
                            f"bootstrap interpreter: {relative_text}"
                        )
                stat = target.stat()
                if stat.st_nlink != 1:
                    raise ValueError(
                        f"runtime cache symlink target is hard linked: {relative_text}"
                    )
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
            if stat.st_nlink != 1:
                raise ValueError(f"runtime cache contains a hard-linked file: {relative_text}")
            mode = 0o755 if stat.st_mode & 0o111 else 0o644
            result.append((relative_text, path, mode))

    visit(root, PurePosixPath("."), ())
    paths = [relative for relative, _, _ in result]
    if len(paths) != len(set(paths)):
        raise ValueError("normalized runtime image contains duplicate paths")
    if not result:
        raise ValueError("runtime cache contains no files")
    return result


def _copy_normalized_file(
    relative: str,
    source_file: Path,
    target: Path,
    *,
    source_size: int,
    remaining_limit: int,
) -> int:
    if relative == "venv/pyvenv.cfg":
        if source_size < 0 or source_size > remaining_limit:
            raise ValueError("normalized runtime image exceeds the size limit")
        raw = source_file.read_bytes()
        if len(raw) != source_size:
            raise ValueError("runtime source changed size while being copied")
        content = _normalize_pyvenv_cfg(raw)
        if len(content) > remaining_limit:
            raise ValueError("normalized runtime image exceeds the size limit")
        with target.open("xb") as output_file:
            output_file.write(content)
            output_file.flush()
            os.fsync(output_file.fileno())
        return len(content)

    copied = 0
    with source_file.open("rb") as input_file, target.open("xb") as output_file:
        while True:
            chunk = input_file.read(min(CHUNK_SIZE, source_size - copied + 1))
            if not chunk:
                break
            copied += len(chunk)
            if copied > source_size or copied > remaining_limit:
                raise ValueError("runtime source changed size while being copied")
            output_file.write(chunk)
        output_file.flush()
        os.fsync(output_file.fileno())
    if copied != source_size:
        raise ValueError("runtime source changed size while being copied")
    return copied


def _copy_normalized_runtime(source: Path, destination: Path) -> None:
    sources = _walk_normalized_sources(source)
    total = 0
    for relative, source_file, mode in sources:
        stat = source_file.stat()
        if stat.st_size < 0 or stat.st_size > RUNTIME_LIMIT - total:
            raise ValueError("normalized runtime image exceeds the size limit")
        target = destination.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        consumed = _copy_normalized_file(
            relative,
            source_file,
            target,
            source_size=stat.st_size,
            remaining_limit=RUNTIME_LIMIT - total,
        )
        target.chmod(mode)
        total += consumed


def _expected_directories(files: set[str]) -> set[str]:
    result: set[str] = set()
    for relative in files:
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            result.add(parent.as_posix())
            parent = parent.parent
    return result


def image_inventory(root: Path) -> dict[str, dict[str, Any]]:
    _require_no_symlink_components(root)
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
        digest, consumed = _sha256_file(path, remaining_limit=RUNTIME_LIMIT - total)
        total += consumed
        stat = path.stat(follow_symlinks=False)
        files[relative] = {
            "type": "file",
            "mode": "755" if stat.st_mode & 0o111 else "644",
            "sha256": digest,
        }
    expected_directories = _expected_directories(set(files))
    if directories != expected_directories:
        raise ValueError("runtime image contains empty or unexpected directories")
    if not files:
        raise ValueError("runtime image is empty")
    entries: dict[str, dict[str, Any]] = {
        relative: {"type": "directory"} for relative in sorted(directories)
    }
    entries.update(files)
    return dict(sorted(entries.items()))


def _marker(root: Path) -> dict[str, Any]:
    marker = root / "runtime.json"
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("runtime marker is missing or invalid") from exc
    if not isinstance(value, dict):
        raise ValueError("runtime marker must be a JSON object")
    return value


def _identity_from_marker(marker: dict[str, Any]) -> RuntimeIdentity:
    value = marker.get("identity")
    required = {"repository", "revision", "lock_sha256", "python", "platform"}
    if (
        not isinstance(value, dict)
        or set(value) != required
        or not all(isinstance(item, str) for item in value.values())
        or FULL_SHA.fullmatch(value["revision"]) is None
        or SHA256.fullmatch(value["lock_sha256"]) is None
    ):
        raise ValueError("runtime marker identity is invalid")
    return RuntimeIdentity(
        repository=value["repository"],
        revision=value["revision"],
        lock_sha256=value["lock_sha256"],
        python=value["python"],
        platform=value["platform"],
    )


def _validate_canonical_runtime(
    root: Path,
    pin: RuntimePin,
) -> tuple[RuntimeIdentity, dict[str, str]]:
    marker = _marker(root)
    identity = _identity_from_marker(marker)
    if identity.repository != pin.repository or identity.revision != pin.revision:
        raise ValueError("runtime marker does not match the selected lock pin")
    if pin.expected_lock_sha256 is not None and identity.lock_sha256 != pin.expected_lock_sha256:
        raise ValueError("runtime marker lock digest does not match the selected lock pin")
    if identity.python != python_token() or identity.platform != platform_token():
        raise ValueError("runtime marker does not match the current Python/platform identity")
    lock_path = root / "requirements-runtime.lock"
    lock_data = lock_path.read_bytes()
    if hashlib.sha256(lock_data).hexdigest() != identity.lock_sha256:
        raise ValueError("runtime lock bytes do not match the runtime identity")
    requirements = parse_runtime_lock(lock_data.decode("utf-8"))
    env = trusted_environment()
    python = venv_python(root)
    subprocess.run(
        [str(python), "-B", "-I", "-m", "pip", "check"],
        check=True,
        env=env,
    )
    verify_installed_set(python, requirements, pin, env)
    return identity, _installed_distributions(python, env)


def _installed_distributions(python: Path, env: dict[str, str]) -> dict[str, str]:
    script = (
        "import importlib.metadata as m,json;"
        "print(json.dumps({d.metadata['Name']:d.version for d in m.distributions()}))"
    )
    result = subprocess.run(
        [str(python), "-B", "-I", "-c", script],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or not all(
        isinstance(name, str) and isinstance(version, str)
        for name, version in value.items()
    ):
        raise ValueError("runtime returned invalid distribution metadata")
    return dict(sorted(value.items()))


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
        "distributions": distributions,
        "entries": entries,
    }


def _validate_entries(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise ValueError("runtime attestation entries are invalid")
    result: dict[str, dict[str, Any]] = {}
    for relative, metadata in value.items():
        if not isinstance(relative, str):
            raise ValueError("runtime attestation path is invalid")
        _safe_relative(relative)
        if metadata == {"type": "directory"}:
            result[relative] = {"type": "directory"}
            continue
        if not isinstance(metadata, dict):
            raise ValueError(f"runtime attestation entry is invalid: {relative}")
        digest = metadata.get("sha256")
        if (
            set(metadata) != {"type", "mode", "sha256"}
            or metadata.get("type") != "file"
            or metadata.get("mode") not in {"644", "755"}
            or not isinstance(digest, str)
            or SHA256.fullmatch(digest) is None
        ):
            raise ValueError(f"runtime attestation entry is invalid: {relative}")
        result[relative] = dict(metadata)
    file_paths = {path for path, metadata in result.items() if metadata["type"] == "file"}
    directory_paths = {
        path for path, metadata in result.items() if metadata["type"] == "directory"
    }
    if directory_paths != _expected_directories(file_paths):
        raise ValueError("runtime attestation directory inventory is invalid")
    return dict(sorted(result.items()))


def _load_attestation(repository: Path, path: Path) -> dict[str, Any]:
    target = _require_external_path(
        repository,
        path,
        label="runtime attestation",
        must_exist=True,
    )
    if target.is_symlink() or not target.is_file():
        raise ValueError("runtime attestation is missing or is not a regular file")
    if target.stat(follow_symlinks=False).st_nlink != 1:
        raise ValueError("runtime attestation must not be hard linked")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("runtime attestation is invalid JSON") from exc
    required = {"schema_version", "runtime", "selected_pin", "distributions", "entries"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("runtime attestation shape is invalid")
    if value.get("schema_version") != ATTESTATION_SCHEMA:
        raise ValueError("runtime attestation schema is invalid")
    runtime = value.get("runtime")
    runtime_fields = {"repository", "revision", "lock_sha256", "python", "platform"}
    if (
        not isinstance(runtime, dict)
        or set(runtime) != runtime_fields
        or not all(isinstance(item, str) for item in runtime.values())
        or FULL_SHA.fullmatch(runtime["revision"]) is None
        or SHA256.fullmatch(runtime["lock_sha256"]) is None
    ):
        raise ValueError("runtime attestation identity is invalid")
    selected = value.get("selected_pin")
    if (
        not isinstance(selected, dict)
        or set(selected) != {"repository", "revision"}
        or not isinstance(selected.get("repository"), str)
        or not isinstance(selected.get("revision"), str)
        or FULL_SHA.fullmatch(selected["revision"]) is None
    ):
        raise ValueError("runtime attestation selected pin is invalid")
    distributions = value.get("distributions")
    if not isinstance(distributions, dict) or not distributions or not all(
        isinstance(name, str) and name and isinstance(version, str) and version
        for name, version in distributions.items()
    ):
        raise ValueError("runtime attestation distributions are invalid")
    value["entries"] = _validate_entries(value.get("entries"))
    value["distributions"] = dict(sorted(distributions.items()))
    return value


def _write_new_attestation(repository: Path, path: Path, value: dict[str, Any]) -> None:
    target = _require_external_path(
        repository,
        path,
        label="runtime attestation",
        must_exist=False,
    )
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
        os.link(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def create_attestation(repository: Path, attestation: Path) -> dict[str, Any]:
    repository = repository.expanduser().absolute()
    target = _require_external_path(
        repository,
        attestation,
        label="runtime attestation",
        must_exist=False,
    )
    if target.exists() or target.is_symlink():
        raise ValueError("runtime attestation destination must not already exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    _require_no_symlink_components(target.parent)
    pin = select_pin(repository)
    private_root = Path(
        tempfile.mkdtemp(prefix=".agent-policy-runtime-attest-", dir=target.parent)
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
        _write_new_attestation(repository, target, value)
        return value
    finally:
        shutil.rmtree(private_root, ignore_errors=True)


def _attestation_for_pin(value: dict[str, Any], pin: RuntimePin) -> dict[str, Any]:
    selected = value["selected_pin"]
    runtime = value["runtime"]
    expected_selected = {"repository": pin.repository, "revision": pin.revision}
    if selected != expected_selected:
        raise ValueError("runtime attestation does not match the trusted-base lock pin")
    if runtime["repository"] != pin.repository or runtime["revision"] != pin.revision:
        raise ValueError("runtime attestation identity does not match the trusted-base lock pin")
    if (
        pin.expected_lock_sha256 is not None
        and runtime["lock_sha256"] != pin.expected_lock_sha256
    ):
        raise ValueError("runtime attestation lock digest does not match the trusted-base lock pin")
    if runtime["python"] != python_token() or runtime["platform"] != platform_token():
        raise ValueError("runtime attestation does not match current Python/platform identity")
    return value


def _fresh_external_destination(repository: Path, destination: Path) -> Path:
    target = _require_external_path(
        repository,
        destination,
        label="runtime image",
        must_exist=False,
    )
    if target.exists() or target.is_symlink():
        raise ValueError("runtime image destination must not already exist")
    target.parent.mkdir(parents=True, exist_ok=True)
    _require_no_symlink_components(target.parent)
    return target


def materialize_image(
    repository: Path,
    attestation: Path,
    destination: Path,
) -> dict[str, Any]:
    repository = repository.expanduser().absolute()
    pin = select_pin(repository)
    expected = _attestation_for_pin(_load_attestation(repository, attestation), pin)
    source = cache_root()
    from runtime import ensure_runtime  # local import keeps module import side effects explicit

    runtime = ensure_runtime(pin, root=source)
    target = _fresh_external_destination(repository, destination)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
    finalized = False
    try:
        _copy_normalized_runtime(runtime, staging)
        if image_inventory(staging) != expected["entries"]:
            raise ValueError("normalized runtime candidate does not match protected attestation")
        os.replace(staging, target)
        finalized = True
        if image_inventory(target) != expected["entries"]:
            raise ValueError("finalized runtime image does not match protected attestation")
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
    repository = repository.expanduser().absolute()
    pin = select_pin(repository)
    expected = _attestation_for_pin(_load_attestation(repository, attestation), pin)
    target = _require_external_path(
        repository,
        image,
        label="runtime image",
        must_exist=True,
    )
    if image_inventory(target) != expected["entries"]:
        raise ValueError("runtime image does not match protected attestation")
    if execute_probe:
        env = trusted_environment()
        python = venv_python(target)
        actual_distributions = _installed_distributions(python, env)
        if actual_distributions != expected["distributions"]:
            raise ValueError("runtime image distribution set does not match attestation")
        subprocess.run(
            [str(python), "-B", "-I", "-m", "pip", "check"],
            check=True,
            env=env,
        )
        if image_inventory(target) != expected["entries"]:
            raise ValueError("runtime image changed during execution verification")
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
        _require_no_symlink_components(repository)
        if repository.is_symlink() or not repository.is_dir():
            raise ValueError("trusted-base snapshot must be a regular directory")
        if (repository / ".git").exists() or (repository / ".git").is_symlink():
            raise ValueError("trusted-base snapshot must not contain .git metadata")
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
