from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ..config import load_config, validate_config
from ..diagnostics import Diagnostic
from ..generated_mutation import (
    DeleteSpec,
    MutationSafetyError,
    WriteSpec,
    apply_generated_mutations,
)
from ..lockfile import (
    LOCK_PATH,
    create_lock,
    load_lock_outputs,
    resolve_lock_path,
    sha256_file,
)
from ..paths import resolve_inside
from ..policy_loader import load_rules
from ..renderer import GENERATED_MARKER, render_output, render_skill


def _generated_bytes(content: bytes) -> bool:
    try:
        return GENERATED_MARKER in content.decode("utf-8")
    except UnicodeDecodeError:
        return False


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
) -> list[tuple[str, Path, bytes]]:
    lock_path = resolve_lock_path(repository_root, allow_missing=True)
    if not lock_path.exists():
        return []

    planned_targets = {target for target, _content in planned.values()}
    locked_targets: dict[Path, str] = {}
    obsolete: list[tuple[str, Path, bytes]] = []
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
        content = target.read_bytes()
        if sha256_file(target) != locked_digest:
            raise ValueError(
                f"Refusing to remove modified obsolete generated output: {relative}"
            )
        if not _generated_bytes(content):
            raise FileExistsError(
                f"Refusing to remove non-generated obsolete output: {relative}"
            )
        obsolete.append((relative, target, content))
    return obsolete


def _reject_obsolete_output_overlaps(
    repository_root: Path,
    obsolete: list[tuple[str, Path, bytes]],
    planned: dict[str, tuple[Path, str]],
) -> None:
    root = repository_root.resolve()
    for _relative, obsolete_target, _content in obsolete:
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

        outputs: dict[str, Path] = {
            relative: target for relative, (target, _content) in planned.items()
        }

        toolchain = config.data["toolchain"]
        lock_content = create_lock(
            toolchain_repository=toolchain["repository"],
            toolchain_revision=toolchain["revision"],
            inputs=inputs,
            outputs=outputs,
            output_digests={
                relative: hashlib.sha256(content.encode("utf-8")).hexdigest()
                for relative, (_target, content) in planned.items()
            },
        )
        writes = {
            _target.relative_to(repository_root.resolve()).as_posix(): WriteSpec(
                content=content.encode("utf-8"),
                owns_existing=_generated_bytes,
            )
            for relative, (_target, content) in planned.items()
        }
        aliases = {
            _target.relative_to(repository_root.resolve()).as_posix(): relative
            for relative, (_target, _content) in planned.items()
            if _target.relative_to(repository_root.resolve()).as_posix() != relative
        }
        deletes = {
            relative: DeleteSpec(
                expected=content,
                owns_existing=_generated_bytes,
            )
            for relative, _target, content in obsolete
        }
        apply_generated_mutations(
            repository_root,
            writes,
            deletes,
            lock_path=LOCK_PATH,
            lock=WriteSpec(
                content=lock_content.encode("utf-8"),
                owns_existing=lambda _content: True,
            ),
            aliases=aliases,
        )
        return []
    except MutationSafetyError as exc:
        return [Diagnostic("error", "RENDER", str(exc))]
    except Exception as exc:
        return [Diagnostic("error", "RENDER", str(exc))]
