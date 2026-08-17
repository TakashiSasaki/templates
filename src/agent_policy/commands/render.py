from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import Config, load_config, validate_config
from ..diagnostics import Diagnostic
from ..lockfile import LOCK_PATH, load_lock, sha256_file, write_lock
from ..paths import resolve_inside
from ..policy_loader import load_rules
from ..renderer import GENERATED_MARKER, render_output, render_skill


def _is_generated_file(path: Path) -> bool:
    try:
        return GENERATED_MARKER in path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
        return False


def _hash_bytes(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _add_planned_output(
    repository_root: Path,
    planned: dict[str, tuple[Path, str]],
    relative: str,
    content: str,
) -> None:
    target = resolve_inside(repository_root, relative, allow_missing=True)
    for existing_relative, (existing_target, _existing_content) in planned.items():
        if target == existing_target:
            raise ValueError(
                "Generated output paths overlap: "
                f"{relative} resolves to the same target as {existing_relative}"
            )
        if existing_target in target.parents or target in existing_target.parents:
            raise ValueError(
                "Generated output paths overlap: "
                f"{relative} overlaps {existing_relative}"
            )
    planned[relative] = (target, content)


def _load_previous_outputs(repository_root: Path) -> dict[str, dict[str, str]]:
    lock_path = resolve_inside(repository_root, LOCK_PATH, allow_missing=True)
    if not lock_path.exists():
        return {}
    lock = load_lock(repository_root)
    outputs = lock.get("outputs", {})
    if not isinstance(outputs, dict):
        raise ValueError("Lock outputs must be a mapping")
    result: dict[str, dict[str, str]] = {}
    for relative, metadata in outputs.items():
        if not isinstance(relative, str) or not isinstance(metadata, dict):
            raise ValueError("Lock outputs are malformed")
        digest = metadata.get("sha256")
        if not isinstance(digest, str):
            raise ValueError("Lock output hash is malformed")
        result[relative] = {"sha256": digest}
    return result


def _normalize_previous_output_targets(
    repository_root: Path,
    previous_outputs: dict[str, dict[str, str]],
) -> dict[str, Path]:
    normalized: dict[str, Path] = {}
    by_target: dict[Path, str] = {}
    for relative in previous_outputs:
        target = resolve_inside(repository_root, relative, allow_missing=True)
        existing = by_target.get(target)
        if existing is not None:
            raise ValueError(
                "Lock output paths normalize to the same target: "
                f"{existing} and {relative}"
            )
        by_target[target] = relative
        normalized[relative] = target
    return normalized


def _remove_obsolete_outputs(
    repository_root: Path,
    previous_outputs: dict[str, dict[str, str]],
    planned: dict[str, tuple[Path, str]],
    current_inputs: set[Path],
) -> None:
    planned_targets = {target for target, _content in planned.values()}
    previous_targets = _normalize_previous_output_targets(
        repository_root,
        previous_outputs,
    )
    for relative, metadata in previous_outputs.items():
        target = previous_targets[relative]
        if target in planned_targets or target in current_inputs:
            continue
        if target.is_symlink():
            raise ValueError(
                f"Refusing to remove obsolete generated path that must not contain symlinks: {relative}"
            )
        if not target.exists():
            continue
        if not target.is_file():
            raise ValueError(
                f"Refusing to remove obsolete generated output that is not a file: {relative}"
            )
        if sha256_file(target) != metadata["sha256"]:
            raise ValueError(
                f"Refusing to remove modified obsolete generated output: {relative}"
            )
        target.unlink()


def _validate_obsolete_output_transitions(
    repository_root: Path,
    previous_outputs: dict[str, dict[str, str]],
    planned: dict[str, tuple[Path, str]],
    current_inputs: set[Path],
) -> None:
    planned_by_target = {target: relative for relative, (target, _content) in planned.items()}
    previous_targets = _normalize_previous_output_targets(
        repository_root,
        previous_outputs,
    )
    for obsolete_relative, obsolete_target in previous_targets.items():
        if obsolete_target in planned_by_target or obsolete_target in current_inputs:
            continue
        for planned_target, planned_relative in planned_by_target.items():
            if obsolete_target in planned_target.parents:
                raise ValueError(
                    "Refusing to replace obsolete generated file with nested output: "
                    f"{obsolete_relative} is an ancestor of {planned_relative}"
                )
            if planned_target in obsolete_target.parents:
                raise ValueError(
                    "Refusing to replace obsolete nested output with parent output: "
                    f"{obsolete_relative} is a descendant of {planned_relative}"
                )


def run(repository_root: Path, config_path: str) -> list[Diagnostic]:
    try:
        config = load_config(repository_root, config_path)
        diagnostics = validate_config(repository_root, config)
        if diagnostics:
            return diagnostics

        planned: dict[str, tuple[Path, str]] = {}
        contexts = config.contexts
        for output in config.output_specs:
            if not output.enabled:
                continue
            context = contexts[output.context]
            rules = load_rules(
                repository_root,
                list(context.profiles),
                list(context.project_policy_files),
                declared_overrides=context.override_reasons,
                require_explicit_overrides=True,
            )
            content = render_output(
                output.renderer,
                config,
                rules,
                context_name=context.name,
                project_policy_files=context.project_policy_files,
            )
            _add_planned_output(
                repository_root,
                planned,
                output.path,
                content,
            )

        for skill in config.enabled_skills:
            for relative, content in render_skill(
                skill,
                config_path=config.relative_path,
            ).items():
                target_name = f".agents/skills/{skill}/{relative}"
                _add_planned_output(repository_root, planned, target_name, content)

        inputs = {config.relative_path: config.path}
        inputs.update(
            {
                relative: resolve_inside(repository_root, relative, allow_missing=False)
                for relative in config.project_policy_files
            }
        )
        current_inputs = set(inputs.values())
        previous_outputs = _load_previous_outputs(repository_root)
        _validate_obsolete_output_transitions(
            repository_root,
            previous_outputs,
            planned,
            current_inputs,
        )

        for relative, (target, content) in planned.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        _remove_obsolete_outputs(
            repository_root,
            previous_outputs,
            planned,
            current_inputs,
        )

        outputs = {
            relative: {"sha256": _hash_bytes(content)}
            for relative, (_target, content) in planned.items()
        }
        input_hashes = {
            relative: {"sha256": sha256_file(path)}
            for relative, path in inputs.items()
        }
        write_lock(
            repository_root,
            toolchain=config.data["toolchain"],
            inputs=input_hashes,
            outputs=outputs,
            skills=config.enabled_skills,
        )
        return []
    except Exception as exc:
        return [Diagnostic("error", "RENDER", str(exc))]
