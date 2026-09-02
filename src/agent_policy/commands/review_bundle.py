from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from . import check as check_command
from ..config import Config, OutputSpec, load_config, validate_config
from ..diagnostics import Diagnostic
from ..lockfile import load_lock_outputs, resolve_lock_path
from ..paths import resolve_inside
from ..yamlutil import load_yaml

SKILL_NAME = "pr-review"
SKILL_PREFIX = f".agents/skills/{SKILL_NAME}/"
SUPPORTED_ADAPTER_RENDERERS = frozenset({"github-review-json-adapter-v1"})


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
        raise ValueError("review-run bundle must be outside the trusted-base snapshot")
    _require_no_symlink_components(target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    _require_no_symlink_components(target.parent)
    return target


def _configured_output(config: Config, path: str) -> OutputSpec:
    matches = [
        item for item in config.output_specs if item.enabled and item.path == path
    ]
    if len(matches) != 1:
        raise ValueError(f"review output path is missing, disabled, or ambiguous: {path}")
    return matches[0]


def _load_locked_file(
    root: Path,
    relative: str,
    lock_outputs: dict[str, str],
) -> bytes:
    expected_digest = lock_outputs.get(relative)
    if expected_digest is None:
        raise ValueError(f"review input is not a lock-authoritative generated output: {relative}")
    source = resolve_inside(root, relative, allow_missing=False)
    _require_no_symlink_components(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"review input is not a regular file: {relative}")
    stat = source.stat(follow_symlinks=False)
    if stat.st_nlink != 1:
        raise ValueError(f"review input is hard linked: {relative}")
    content = source.read_bytes()
    if _sha256_bytes(content) != expected_digest:
        raise ValueError(f"review input does not match its lock digest: {relative}")
    return content


def _validate_config_and_lock(
    root: Path,
    config_path: str | Path,
) -> tuple[Config, dict[str, object], dict[str, str]]:
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
    adapter_output: str,
    adapter_renderer: str,
) -> dict[str, bytes]:
    root = repository_root.resolve()
    config, lock, lock_outputs = _validate_config_and_lock(root, config_path)
    semantic = _configured_output(config, semantic_output)
    adapter = _configured_output(config, adapter_output)
    if semantic.path == adapter.path:
        raise ValueError("semantic and adapter outputs must use distinct paths")
    if semantic.context != adapter.context:
        raise ValueError("semantic and adapter outputs must reference the same context")
    if semantic.renderer != "policy-context-md":
        raise ValueError("semantic review output must use policy-context-md")
    if adapter_renderer not in SUPPORTED_ADAPTER_RENDERERS:
        raise ValueError(f"unsupported review adapter renderer: {adapter_renderer}")
    if adapter.renderer != adapter_renderer:
        raise ValueError("adapter output renderer does not match the requested adapter")

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
    adapter_bytes = _load_locked_file(root, adapter.path, lock_outputs)
    expected["projections/semantic.md"] = semantic_bytes
    expected["projections/adapter.md"] = adapter_bytes

    toolchain = lock.get("toolchain")
    if not isinstance(toolchain, dict):
        raise ValueError("agent-policy lock toolchain is invalid")
    manifest = {
        "schema_version": 1,
        "configuration": config.relative_path,
        "context": semantic.context,
        "toolchain": toolchain,
        "procedure": {
            "revision": toolchain.get("revision"),
            "files": procedure_manifest,
        },
        "semantic": {
            "source_path": semantic.path,
            "renderer": semantic.renderer,
            "bundle_path": "projections/semantic.md",
            "sha256": _sha256_bytes(semantic_bytes),
        },
        "adapter": {
            "source_path": adapter.path,
            "renderer": adapter.renderer,
            "bundle_path": "projections/adapter.md",
            "sha256": _sha256_bytes(adapter_bytes),
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
        raise ValueError("review-run bundle is missing or not a regular directory")

    expected_files = set(expected)
    expected_directories = _expected_directories(expected_files)
    actual_files: set[str] = set()
    actual_directories: set[str] = set()

    for path in sorted(bundle.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink():
            raise ValueError(f"review-run bundle contains a symbolic link: {relative}")
        if path.is_dir():
            actual_directories.add(relative)
            continue
        if not path.is_file():
            raise ValueError(f"review-run bundle contains a non-regular path: {relative}")
        stat = path.stat(follow_symlinks=False)
        if stat.st_nlink != 1:
            raise ValueError(f"review-run bundle contains a hard-linked file: {relative}")
        actual_files.add(relative)
        if relative not in expected:
            continue
        if path.read_bytes() != expected[relative]:
            raise ValueError(f"review-run bundle byte mismatch: {relative}")

    if actual_files != expected_files or actual_directories != expected_directories:
        raise ValueError("review-run bundle path/type inventory does not match expected inputs")


def materialize(
    repository_root: Path,
    config_path: str | Path,
    destination: Path,
    semantic_output: str,
    adapter_output: str,
    adapter_renderer: str,
) -> list[Diagnostic]:
    try:
        root = repository_root.resolve()
        expected = _load_expected_bundle(
            root,
            config_path,
            semantic_output,
            adapter_output,
            adapter_renderer,
        )
        target = _require_external_destination(root, destination)
        if target.exists() or target.is_symlink():
            raise ValueError("review-run bundle destination must not already exist")

        staging = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent)
        )
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
                "Materialized exact procedure, semantic, and adapter input bytes. "
                "The deployment must establish the immutable/read-only trust boundary "
                "and run review-bundle verify before analysis or serialization."
            ),
            str(target),
        )
    ]


def verify(
    repository_root: Path,
    config_path: str | Path,
    bundle: Path,
    semantic_output: str,
    adapter_output: str,
    adapter_renderer: str,
) -> list[Diagnostic]:
    try:
        root = repository_root.resolve()
        expected = _load_expected_bundle(
            root,
            config_path,
            semantic_output,
            adapter_output,
            adapter_renderer,
        )
        target = _require_external_destination(root, bundle)
        _verify_bundle_tree(target, expected)
    except (OSError, ValueError) as exc:
        return [Diagnostic("error", "REVIEW_BUNDLE", str(exc))]

    return [
        Diagnostic(
            "info",
            "REVIEW_BUNDLE_VERIFIED",
            (
                "Verified the deployment-frozen review-run bundle. The executor must "
                "consume procedure/SKILL.md, its references, projections/semantic.md, "
                "and projections/adapter.md only from this exact bundle."
            ),
            str(target),
        )
    ]
