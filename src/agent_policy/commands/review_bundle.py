from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from ..config import load_config, validate_config
from ..diagnostics import Diagnostic
from ..lockfile import load_lock_outputs, resolve_lock_path, sha256_file
from ..paths import resolve_inside
from ..renderer import render_skill
from ..yamlutil import load_yaml

SKILL_NAME = "pr-review"
SKILL_PREFIX = f".agents/skills/{SKILL_NAME}/"


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


def _require_external_destination(repository_root: Path, destination: Path) -> Path:
    root = repository_root.resolve()
    target = destination.expanduser().absolute()
    try:
        target.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("review procedure bundle must be outside the repository")
    _require_no_symlink_components(target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    _require_no_symlink_components(target.parent)
    return target


def _load_expected_bundle(
    repository_root: Path,
    config_path: str | Path,
) -> dict[str, bytes]:
    root = repository_root.resolve()
    config = load_config(root, config_path)
    diagnostics = validate_config(root, config)
    errors = [item for item in diagnostics if item.level == "error"]
    if errors:
        rendered = "; ".join(f"{item.code}: {item.message}" for item in errors)
        raise ValueError(f"configuration is invalid: {rendered}")
    if SKILL_NAME not in config.enabled_skills:
        raise ValueError("trusted configuration does not enable pr-review")

    lock_path = resolve_lock_path(root, allow_missing=False)
    lock = load_yaml(lock_path)
    if not isinstance(lock, dict) or lock.get("lock_version") != 1:
        raise ValueError("agent-policy lock is missing or invalid")
    config_toolchain = config.data.get("toolchain")
    if lock.get("toolchain") != config_toolchain:
        raise ValueError("agent-policy lock toolchain does not match configuration")

    rendered = render_skill(SKILL_NAME, config_path=config.relative_path)
    expected: dict[str, bytes] = {
        relative: content.encode("utf-8") for relative, content in rendered.items()
    }
    if not expected:
        raise ValueError("pr-review renderer produced no files")

    lock_outputs = load_lock_outputs(lock_path)
    locked_skill = {
        path: digest for path, digest in lock_outputs.items() if path.startswith(SKILL_PREFIX)
    }
    expected_locked_paths = {f"{SKILL_PREFIX}{relative}" for relative in expected}
    if set(locked_skill) != expected_locked_paths:
        raise ValueError("lock output inventory does not exactly match generated pr-review files")

    for relative, content in expected.items():
        locked_path = f"{SKILL_PREFIX}{relative}"
        digest = _sha256_bytes(content)
        if locked_skill[locked_path] != digest:
            raise ValueError(f"lock digest does not match rendered pr-review bytes: {locked_path}")
        source = root.joinpath(*PurePosixPath(locked_path).parts)
        resolve_inside(root, locked_path, allow_missing=False)
        _require_no_symlink_components(source)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"generated pr-review source is not a regular file: {locked_path}")
        if source.stat(follow_symlinks=False).st_nlink != 1:
            raise ValueError(f"generated pr-review source is hard linked: {locked_path}")
        if sha256_file(source) != digest:
            raise ValueError(f"generated pr-review source does not match lock digest: {locked_path}")
    return dict(sorted(expected.items()))


def _expected_directories(files: set[str]) -> set[str]:
    result: set[str] = set()
    for relative in files:
        pure = PurePosixPath(relative)
        parent = pure.parent
        while parent != PurePosixPath("."):
            result.add(parent.as_posix())
            parent = parent.parent
    return result


def _verify_bundle_tree(bundle: Path, expected: dict[str, bytes]) -> None:
    _require_no_symlink_components(bundle)
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError("review procedure bundle is missing or not a regular directory")

    expected_files = set(expected)
    expected_directories = _expected_directories(expected_files)
    actual_files: set[str] = set()
    actual_directories: set[str] = set()

    for path in sorted(bundle.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink():
            raise ValueError(f"review procedure bundle contains a symbolic link: {relative}")
        if path.is_dir():
            actual_directories.add(relative)
            continue
        if not path.is_file():
            raise ValueError(f"review procedure bundle contains a non-regular path: {relative}")
        stat = path.stat(follow_symlinks=False)
        if stat.st_nlink != 1:
            raise ValueError(f"review procedure bundle contains a hard-linked file: {relative}")
        actual_files.add(relative)
        if relative not in expected:
            continue
        if path.read_bytes() != expected[relative]:
            raise ValueError(f"review procedure bundle digest mismatch: {relative}")

    if actual_files != expected_files or actual_directories != expected_directories:
        raise ValueError("review procedure bundle path/type inventory does not match pr-review")


def materialize(
    repository_root: Path,
    config_path: str | Path,
    destination: Path,
) -> list[Diagnostic]:
    try:
        root = repository_root.resolve()
        expected = _load_expected_bundle(root, config_path)
        target = _require_external_destination(root, destination)
        if target.exists() or target.is_symlink():
            raise ValueError("review procedure bundle destination must not already exist")

        staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
        finalized = False
        try:
            for relative, content in expected.items():
                output = staging.joinpath(*PurePosixPath(relative).parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            _verify_bundle_tree(staging, expected)
            os.replace(staging, target)
            finalized = True
        finally:
            if not finalized and staging.exists():
                shutil.rmtree(staging)
    except (OSError, ValueError) as exc:
        return [Diagnostic("error", "REVIEW_BUNDLE", str(exc))]

    return [
        Diagnostic(
            "info",
            "REVIEW_BUNDLE_MATERIALIZED",
            (
                "Materialized a lock-authoritative pr-review bundle candidate. "
                "The deployment must now establish its immutable/read-only trust boundary "
                "and run review-bundle verify before execution."
            ),
            str(target),
        )
    ]


def verify(
    repository_root: Path,
    config_path: str | Path,
    bundle: Path,
) -> list[Diagnostic]:
    try:
        root = repository_root.resolve()
        expected = _load_expected_bundle(root, config_path)
        target = _require_external_destination(root, bundle)
        _verify_bundle_tree(target, expected)
    except (OSError, ValueError) as exc:
        return [Diagnostic("error", "REVIEW_BUNDLE", str(exc))]

    return [
        Diagnostic(
            "info",
            "REVIEW_BUNDLE_VERIFIED",
            (
                "Verified the protected pr-review bundle against the trusted lock and "
                "lock-selected renderer bytes. Deployment immutability remains a hosting "
                "precondition and is not inferred from filesystem mode bits."
            ),
            str(target),
        )
    ]
