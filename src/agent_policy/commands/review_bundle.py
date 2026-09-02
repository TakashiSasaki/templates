from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from ..config import Config, OutputSpec, load_config, validate_config
from ..diagnostics import Diagnostic
from ..lockfile import load_lock_outputs, resolve_lock_path
from ..paths import find_trusted_snapshot_root, resolve_inside
from ..yamlutil import load_yaml
from . import check as check_command

SKILL_NAME = "pr-review"
SKILL_PREFIX = f".agents/skills/{SKILL_NAME}/"
SEMANTIC_RENDERER = "policy-context-md"
BUNDLE_FORMAT = 1


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_no_symlink_components(path: Path) -> None:
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"path contains a symbolic-link component: {current}")
        if not current.exists():
            break


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.expanduser().absolute()
    try:
        right.relative_to(left)
        return True
    except ValueError:
        pass
    try:
        left.relative_to(right)
        return True
    except ValueError:
        return False


def _require_external_path(
    repository_root: Path,
    path: Path,
    *,
    label: str,
    must_exist: bool,
) -> Path:
    root = repository_root.resolve()
    target = path.expanduser().absolute()
    _require_no_symlink_components(target)
    if _paths_overlap(root, target):
        raise ValueError(f"{label} must not overlap the trusted-base snapshot")
    if must_exist and (target.is_symlink() or not target.exists()):
        raise ValueError(f"{label} is missing")
    return target


def _configured_semantic_output(config: Config, path: str) -> OutputSpec:
    matches = [
        item for item in config.output_specs if item.enabled and item.path == path
    ]
    if len(matches) != 1:
        raise ValueError(
            f"semantic review output path is missing, disabled, or ambiguous: {path}"
        )
    output = matches[0]
    if output.renderer != SEMANTIC_RENDERER:
        raise ValueError(
            f"semantic review output must use {SEMANTIC_RENDERER}: {path}"
        )
    return output


def _load_locked_file(
    root: Path,
    relative: str,
    lock_outputs: dict[str, str],
) -> bytes:
    expected_digest = lock_outputs.get(relative)
    if expected_digest is None:
        raise ValueError(
            f"review authority is not a lock-authoritative generated output: {relative}"
        )
    source = resolve_inside(root, relative, allow_missing=False)
    _require_no_symlink_components(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"review authority is not a regular file: {relative}")
    if source.stat(follow_symlinks=False).st_nlink != 1:
        raise ValueError(f"review authority is hard linked: {relative}")
    content = source.read_bytes()
    if _sha256_bytes(content) != expected_digest:
        raise ValueError(f"review authority does not match its lock digest: {relative}")
    return content


def _validate_config_and_lock(
    root: Path,
    config_path: str | Path,
) -> tuple[Config, dict[str, object], dict[str, str]]:
    config = load_config(root, config_path)
    _require_no_symlink_components(config.path)
    if config.path.is_symlink() or not config.path.is_file():
        raise ValueError("trusted configuration is not a regular file")
    if config.path.stat(follow_symlinks=False).st_nlink != 1:
        raise ValueError("trusted configuration is hard linked")

    diagnostics = validate_config(root, config)
    errors = [item for item in diagnostics if item.level == "error"]
    if errors:
        rendered = "; ".join(f"{item.code}: {item.message}" for item in errors)
        raise ValueError(f"configuration is invalid: {rendered}")
    if SKILL_NAME not in config.enabled_skills:
        raise ValueError("trusted configuration does not enable pr-review")

    lock_path = resolve_lock_path(root, allow_missing=False)
    _require_no_symlink_components(lock_path)
    if lock_path.is_symlink() or not lock_path.is_file():
        raise ValueError("agent-policy lock is not a regular file")
    if lock_path.stat(follow_symlinks=False).st_nlink != 1:
        raise ValueError("agent-policy lock is hard linked")
    lock = load_yaml(lock_path)
    if not isinstance(lock, dict) or lock.get("lock_version") != 1:
        raise ValueError("agent-policy lock is missing or invalid")
    if lock.get("toolchain") != config.data.get("toolchain"):
        raise ValueError("agent-policy lock toolchain does not match configuration")

    check_diagnostics = check_command.run(root, config.relative_path)
    check_errors = [item for item in check_diagnostics if item.level == "error"]
    if check_errors:
        rendered = "; ".join(
            f"{item.code}: {item.message}" for item in check_errors
        )
        raise ValueError(f"trusted-base agent-policy check failed: {rendered}")
    return config, lock, load_lock_outputs(lock_path)


def _load_expected_bundle(
    repository_root: Path,
    config_path: str | Path,
    semantic_output: str,
) -> dict[str, bytes]:
    root = repository_root.resolve()
    config, lock, lock_outputs = _validate_config_and_lock(root, config_path)
    semantic = _configured_semantic_output(config, semantic_output)

    locked_skill = {
        path: digest
        for path, digest in lock_outputs.items()
        if path.startswith(SKILL_PREFIX)
    }
    if not locked_skill or f"{SKILL_PREFIX}SKILL.md" not in locked_skill:
        raise ValueError("lock does not contain a complete generated pr-review Skill")

    expected: dict[str, bytes] = {}
    procedure_manifest: list[dict[str, str]] = []
    for source_path in sorted(locked_skill):
        content = _load_locked_file(root, source_path, lock_outputs)
        suffix = source_path.removeprefix(SKILL_PREFIX)
        bundle_path = f"procedure/{suffix}"
        expected[bundle_path] = content
        procedure_manifest.append(
            {
                "bundle_path": bundle_path,
                "source_path": source_path,
                "sha256": _sha256_bytes(content),
            }
        )

    semantic_bytes = _load_locked_file(root, semantic.path, lock_outputs)
    semantic_bundle_path = "semantic/review-policy.md"
    expected[semantic_bundle_path] = semantic_bytes

    toolchain = lock.get("toolchain")
    if not isinstance(toolchain, dict):
        raise ValueError("agent-policy lock toolchain is invalid")
    manifest = {
        "bundle_format": BUNDLE_FORMAT,
        "configuration": config.relative_path,
        "context": semantic.context,
        "toolchain": toolchain,
        "procedure": {
            "files": procedure_manifest,
        },
        "semantic": {
            "source_path": semantic.path,
            "renderer": semantic.renderer,
            "bundle_path": semantic_bundle_path,
            "sha256": _sha256_bytes(semantic_bytes),
        },
    }
    expected["manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return dict(sorted(expected.items()))


def _expected_directories(files: set[str]) -> set[str]:
    result: set[str] = set()
    for relative in files:
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            result.add(parent.as_posix())
            parent = parent.parent
    return result


def _verify_bundle_tree(bundle: Path, expected: dict[str, bytes]) -> None:
    _require_no_symlink_components(bundle)
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError("review authority bundle is missing or not a regular directory")

    expected_files = set(expected)
    expected_directories = _expected_directories(expected_files)
    actual_files: set[str] = set()
    actual_directories: set[str] = set()

    for path in sorted(bundle.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink():
            raise ValueError(f"review authority bundle contains a symbolic link: {relative}")
        if path.is_dir():
            actual_directories.add(relative)
            continue
        if not path.is_file():
            raise ValueError(
                f"review authority bundle contains a non-regular path: {relative}"
            )
        if path.stat(follow_symlinks=False).st_nlink != 1:
            raise ValueError(f"review authority bundle contains a hard-linked file: {relative}")
        actual_files.add(relative)
        if relative in expected and path.read_bytes() != expected[relative]:
            raise ValueError(f"review authority bundle byte mismatch: {relative}")

    if actual_files != expected_files or actual_directories != expected_directories:
        raise ValueError(
            "review authority bundle path/type inventory does not match expected inputs"
        )


def _write_bundle_tree(root: Path, expected: dict[str, bytes]) -> None:
    for relative, content in expected.items():
        output = root.joinpath(*PurePosixPath(relative).parts)
        output.parent.mkdir(parents=True, exist_ok=True)
        _require_no_symlink_components(output.parent)
        with output.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())


def _cleanup_owned_partial_bundle(
    target: Path,
    *,
    directory_identity: tuple[int, int],
) -> None:
    try:
        current = target.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    if target.is_symlink() or not target.is_dir():
        raise ValueError(
            "refusing to clean a partial review authority bundle whose path type changed"
        )
    if (current.st_dev, current.st_ino) != directory_identity:
        raise ValueError(
            "refusing to clean a partial review authority bundle whose directory identity changed"
        )
    shutil.rmtree(target)


def materialize(
    repository_root: Path,
    config_path: str | Path,
    destination: Path,
    semantic_output: str,
) -> list[Diagnostic]:
    try:
        root = find_trusted_snapshot_root(repository_root)
        expected = _load_expected_bundle(root, config_path, semantic_output)
        target = _require_external_path(
            root,
            destination,
            label="review authority bundle",
            must_exist=False,
        )
        if target.exists() or target.is_symlink():
            raise ValueError("review authority bundle destination must not already exist")
        target.parent.mkdir(parents=True, exist_ok=True)
        _require_no_symlink_components(target.parent)

        staging = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent)
        )
        try:
            _write_bundle_tree(staging, expected)
            _verify_bundle_tree(staging, expected)
            try:
                target.mkdir()
            except FileExistsError as exc:
                raise ValueError(
                    "review authority bundle destination must not already exist"
                ) from exc
            target_stat = target.stat(follow_symlinks=False)
            target_identity = (target_stat.st_dev, target_stat.st_ino)
            try:
                _write_bundle_tree(target, expected)
                _verify_bundle_tree(target, expected)
            except (OSError, ValueError):
                _cleanup_owned_partial_bundle(
                    target,
                    directory_identity=target_identity,
                )
                raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    except (OSError, ValueError) as exc:
        return [Diagnostic("error", "REVIEW_BUNDLE", str(exc))]

    manifest_sha256 = _sha256_bytes(expected["manifest.json"])
    return [
        Diagnostic(
            "info",
            "REVIEW_BUNDLE_MATERIALIZED",
            (
                "Materialized exact provider-neutral procedure and semantic-policy bytes; "
                f"manifest_sha256={manifest_sha256}. The deployment must freeze this "
                "bundle and run review-bundle verify before review analysis begins."
            ),
            str(target),
        )
    ]


def verify(
    repository_root: Path,
    config_path: str | Path,
    bundle: Path,
    semantic_output: str,
) -> list[Diagnostic]:
    try:
        root = find_trusted_snapshot_root(repository_root)
        expected = _load_expected_bundle(root, config_path, semantic_output)
        target = _require_external_path(
            root,
            bundle,
            label="review authority bundle",
            must_exist=True,
        )
        _verify_bundle_tree(target, expected)
    except (OSError, ValueError) as exc:
        return [Diagnostic("error", "REVIEW_BUNDLE", str(exc))]

    manifest_sha256 = _sha256_bytes(expected["manifest.json"])
    return [
        Diagnostic(
            "info",
            "REVIEW_BUNDLE_VERIFIED",
            (
                "Verified the deployment-frozen provider-neutral review authority bundle; "
                f"manifest_sha256={manifest_sha256}. The review executor must consume "
                "procedure/SKILL.md, its references, and semantic/review-policy.md only "
                "from this exact bundle."
            ),
            str(target),
        )
    ]
