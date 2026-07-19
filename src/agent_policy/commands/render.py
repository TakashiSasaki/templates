from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..config import load_config, validate_config
from ..diagnostics import Diagnostic
from ..lockfile import (
    LOCK_PATH,
    create_lock,
    load_lock_outputs,
    resolve_lock_path,
    sha256_file,
)
from ..paths import resolve_inside
from ..policy_loader import load_rules
from ..renderer import GENERATED_MARKER, render_agents, render_skill


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _safe_generated_write(path: Path, content: str) -> None:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if GENERATED_MARKER not in existing:
            raise FileExistsError(f"Refusing to overwrite non-generated file: {path}")
    _write_atomic(path, content)


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _add_planned_output(
    repository_root: Path,
    planned: dict[str, tuple[Path, str]],
    relative: str,
    content: str,
) -> None:
    target = resolve_inside(repository_root, relative)
    lock_target = resolve_lock_path(repository_root)
    if _paths_overlap(target, lock_target):
        raise ValueError(
            f"Generated output path overlaps reserved path: {relative} and {LOCK_PATH}"
        )
    for existing_relative, (existing_target, _) in planned.items():
        if _paths_overlap(target, existing_target):
            raise ValueError(
                "Generated output paths overlap: "
                f"{existing_relative} and {relative}"
            )
    planned[relative] = (target, content)


def _literal_repository_path(repository_root: Path, relative: str | Path) -> Path:
    root = repository_root.resolve()
    literal = Path(os.path.abspath(root / relative))
    try:
        literal.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes repository root: {relative}") from exc
    return literal


def _literal_output_path(repository_root: Path, relative: str) -> Path:
    root = repository_root.resolve()
    literal = _literal_repository_path(root, relative)

    for component in (literal, *literal.parents):
        if component == root:
            break
        if component.is_symlink():
            raise ValueError(
                f"Obsolete generated output path must not contain symlinks: {relative}"
            )

    resolved = resolve_inside(root, relative, allow_missing=True)
    if resolved != literal:
        raise ValueError(
            f"Obsolete generated output path resolves through a symlink: {relative}"
        )
    return literal


def _obsolete_generated_outputs(
    repository_root: Path,
    planned: dict[str, tuple[Path, str]],
    protected_inputs: set[Path],
) -> list[Path]:
    lock_path = resolve_lock_path(repository_root, allow_missing=True)
    if not lock_path.exists():
        return []

    planned_targets = {target for target, _content in planned.values()}
    locked_targets: dict[Path, str] = {}
    obsolete: list[Path] = []
    for relative, locked_digest in load_lock_outputs(lock_path).items():
        if relative in planned:
            continue

        literal_target = _literal_repository_path(repository_root, relative)
        if literal_target in protected_inputs:
            continue

        target = _literal_output_path(repository_root, relative)
        previous_relative = locked_targets.get(target)
        if previous_relative is not None:
            raise ValueError(
                "Lock output paths normalize to the same target: "
                f"{previous_relative} and {relative}"
            )
        locked_targets[target] = relative

        if target in planned_targets or target in protected_inputs or not target.exists():
            continue
        if not target.is_file():
            raise FileExistsError(
                f"Refusing to remove non-file obsolete generated output: {relative}"
            )
        if sha256_file(target) != locked_digest:
            raise ValueError(
                f"Refusing to remove modified obsolete generated output: {relative}"
            )
        if GENERATED_MARKER not in target.read_text(encoding="utf-8"):
            raise FileExistsError(
                f"Refusing to remove non-generated obsolete output: {relative}"
            )
        obsolete.append(target)
    return obsolete


def _reject_obsolete_output_overlaps(
    repository_root: Path,
    obsolete: list[Path],
    planned: dict[str, tuple[Path, str]],
) -> None:
    root = repository_root.resolve()
    for obsolete_target in obsolete:
        obsolete_relative = obsolete_target.relative_to(root).as_posix()
        for planned_relative, (planned_target, _content) in planned.items():
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
        rules = load_rules(repository_root, config.profiles, config.project_policy_files)

        planned: dict[str, tuple[Path, str]] = {}
        if config.output_agents_path:
            _add_planned_output(
                repository_root,
                planned,
                config.output_agents_path,
                render_agents(config, rules),
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
        protected_inputs = set(inputs.values())
        protected_inputs.update(
            _literal_repository_path(repository_root, relative)
            for relative in (config_path, *config.project_policy_files)
        )
        obsolete = _obsolete_generated_outputs(
            repository_root,
            planned,
            protected_inputs,
        )
        _reject_obsolete_output_overlaps(repository_root, obsolete, planned)

        outputs: dict[str, Path] = {}
        for relative, (target, content) in planned.items():
            _safe_generated_write(target, content)
            outputs[relative] = target
        for target in obsolete:
            target.unlink()

        toolchain = config.data["toolchain"]
        lock_content = create_lock(
            toolchain_repository=toolchain["repository"],
            toolchain_revision=toolchain["revision"],
            inputs=inputs,
            outputs=outputs,
        )
        _write_atomic(resolve_lock_path(repository_root), lock_content)
        return []
    except Exception as exc:
        return [Diagnostic("error", "RENDER", str(exc))]
