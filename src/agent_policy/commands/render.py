from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..config import load_config, validate_config
from ..diagnostics import Diagnostic
from ..lockfile import LOCK_PATH, create_lock
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
    lock_target = resolve_inside(repository_root, LOCK_PATH)
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
            for relative, content in render_skill(skill).items():
                target_name = f".agents/skills/{skill}/{relative}"
                _add_planned_output(repository_root, planned, target_name, content)

        outputs: dict[str, Path] = {}
        for relative, (target, content) in planned.items():
            _safe_generated_write(target, content)
            outputs[relative] = target

        toolchain = config.data["toolchain"]
        inputs = {config.path.name: config.path}
        inputs.update(
            {
                relative: resolve_inside(repository_root, relative, allow_missing=False)
                for relative in config.project_policy_files
            }
        )
        lock_content = create_lock(
            toolchain_repository=toolchain["repository"],
            toolchain_revision=toolchain["revision"],
            inputs=inputs,
            outputs=outputs,
        )
        _write_atomic(repository_root / LOCK_PATH, lock_content)
        return []
    except Exception as exc:
        return [Diagnostic("error", "RENDER", str(exc))]
