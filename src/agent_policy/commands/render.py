from __future__ import annotations

import json
import os
import shlex
import tempfile
from pathlib import Path

from ..config import Config, load_config, validate_config
from ..delivery import render_staged_agents
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
from ..renderer import (
    GENERATED_MARKER,
    SKILL_DELIVERY_BUNDLE_PATH_PYTHON_TOKEN,
    SKILL_DELIVERY_BUNDLE_PATH_SHELL_TOKEN,
    SKILL_DELIVERY_BUNDLE_PATH_TOKEN,
    render_output,
    render_skill,
)

_NO_EXPECTED_CONTENT = object()


def _write_atomic(
    path: Path,
    content: str,
    *,
    expected_existing: str | None | object = _NO_EXPECTED_CONTENT,
) -> None:
    if expected_existing is not _NO_EXPECTED_CONTENT:
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != expected_existing:
            raise FileExistsError(
                f"Refusing to replace file changed during render: {path}"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    if expected_existing is not _NO_EXPECTED_CONTENT:
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != expected_existing:
            temporary.unlink(missing_ok=True)
            raise FileExistsError(
                f"Refusing to replace file changed during render: {path}"
            )
    os.replace(temporary, path)


def _is_generated_content(content: str, *, json_output: bool = False) -> bool:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # A staged detail bundle is JSON. Do not let malformed JSON that
        # merely contains the textual marker take the destructive fallback;
        # otherwise an authored file could be overwritten.
        if json_output:
            return False
        return GENERATED_MARKER in content
    return isinstance(parsed, dict) and parsed.get("agent-policy-generated") is True


def _validate_generated_write(
    path: Path, content: str, *, json_output: bool = False
) -> None:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if not _is_generated_content(existing, json_output=json_output):
            raise FileExistsError(f"Refusing to overwrite non-generated file: {path}")


def _safe_generated_write(
    path: Path, content: str, *, json_output: bool = False
) -> str | None:
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    _validate_generated_write(path, content, json_output=json_output)
    _write_atomic(path, content, expected_existing=previous)
    return previous


def _safe_generated_remove(path: Path, expected: str, *, json_output: bool) -> None:
    current = path.read_text(encoding="utf-8")
    if current != expected:
        raise FileExistsError(
            f"Refusing to remove changed obsolete generated output: {path}"
        )
    if not _is_generated_content(current, json_output=json_output):
        raise FileExistsError(
            f"Refusing to remove non-generated obsolete output: {path}"
        )
    path.unlink()


def _restore_owned_file(path: Path, previous: str | None, written: str) -> None:
    if not path.exists() or path.read_text(encoding="utf-8") != written:
        return
    try:
        if previous is None:
            _safe_generated_remove(path, written, json_output=False)
        else:
            _write_atomic(path, previous, expected_existing=written)
    except (FileExistsError, FileNotFoundError):
        return


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
    json_outputs: set[str],
) -> list[Path]:
    lock_path = resolve_lock_path(repository_root, allow_missing=True)
    if not lock_path.exists():
        return []

    planned_targets = {target for target, _content in planned.values()}
    locked_targets: dict[Path, str] = {}
    obsolete: list[tuple[Path, str, bool]] = []
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
        if not _is_generated_content(
            target.read_text(encoding="utf-8"),
            json_output=relative in json_outputs,
        ):
            raise FileExistsError(
                f"Refusing to remove non-generated obsolete output: {relative}"
            )
        obsolete.append(
            (
                target,
                target.read_text(encoding="utf-8"),
                relative in json_outputs,
            )
        )
    return obsolete


def _reject_obsolete_output_overlaps(
    repository_root: Path,
    obsolete: list[tuple[Path, str, bool]],
    planned: dict[str, tuple[Path, str]],
) -> None:
    root = repository_root.resolve()
    for obsolete_target, _content, _json_output in obsolete:
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


def _configured_inputs(
    repository_root: Path, config: Config, config_path: str
) -> dict[str, Path]:
    inputs = {config.relative_path: config.path}
    inputs.update(
        {
            relative: resolve_inside(repository_root, relative, allow_missing=False)
            for relative in config.project_policy_files
        }
    )
    return inputs


def run(repository_root: Path, config_path: str) -> list[Diagnostic]:
    try:
        config = load_config(repository_root, config_path)
        diagnostics = validate_config(repository_root, config)
        if diagnostics:
            return diagnostics

        planned: dict[str, tuple[Path, str]] = {}
        inputs = _configured_inputs(repository_root, config, config_path)
        staged_bundle_paths: list[str] = []
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
            if output.renderer == "agents-md-staged":
                if output.detail_bundle_path is None:
                    raise ValueError("agents-md-staged requires detail_bundle")
                staged = render_staged_agents(
                    config,
                    rules,
                    context_name=context.name,
                    project_policy_files=list(context.project_policy_files),
                    input_paths=inputs,
                    bundle_path=output.detail_bundle_path,
                )
                _add_planned_output(repository_root, planned, output.path, staged.startup)
                _add_planned_output(
                    repository_root,
                    planned,
                    output.detail_bundle_path,
                    staged.bundle,
                )
                staged_bundle_paths.append(output.detail_bundle_path)
            else:
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
            replacement_values = None
            if skill == "policy-guidance":
                if len(staged_bundle_paths) != 1:
                    raise ValueError(
                        "policy-guidance requires exactly one enabled agents-md-staged output"
                    )
                bundle_path = staged_bundle_paths[0]
                replacement_values = {
                    SKILL_DELIVERY_BUNDLE_PATH_TOKEN: bundle_path,
                    SKILL_DELIVERY_BUNDLE_PATH_SHELL_TOKEN: shlex.quote(bundle_path),
                    SKILL_DELIVERY_BUNDLE_PATH_PYTHON_TOKEN: json.dumps(bundle_path)[
                        1:-1
                    ],
                }
            for relative, content in render_skill(
                skill,
                config_path=config.relative_path,
                replacement_values=replacement_values,
            ).items():
                target_name = f".agents/skills/{skill}/{relative}"
                _add_planned_output(repository_root, planned, target_name, content)

        protected_inputs = set(inputs.values())
        protected_inputs.update(
            _literal_repository_path(repository_root, relative)
            for relative in (config_path, *config.project_policy_files)
        )
        obsolete = _obsolete_generated_outputs(
            repository_root,
            planned,
            protected_inputs,
            set(staged_bundle_paths),
        )
        _reject_obsolete_output_overlaps(repository_root, obsolete, planned)

        for relative, (target, content) in planned.items():
            _validate_generated_write(
                target,
                content,
                json_output=relative in staged_bundle_paths,
            )
        written: list[tuple[Path, str | None, str]] = []
        removed: list[tuple[Path, str]] = []
        try:
            outputs: dict[str, Path] = {}
            for relative, (target, content) in planned.items():
                previous = _safe_generated_write(
                    target,
                    content,
                    json_output=relative in staged_bundle_paths,
                )
                written.append((target, previous, content))
                outputs[relative] = target
            for target, previous, json_output in obsolete:
                _safe_generated_remove(
                    target, previous, json_output=json_output
                )
                removed.append((target, previous))

            toolchain = config.data["toolchain"]
            lock_content = create_lock(
                toolchain_repository=toolchain["repository"],
                toolchain_revision=toolchain["revision"],
                inputs=inputs,
                outputs=outputs,
            )
            lock_path = resolve_lock_path(repository_root)
            previous_lock = (
                lock_path.read_text(encoding="utf-8")
                if lock_path.exists()
                else None
            )
            _write_atomic(
                lock_path,
                lock_content,
                expected_existing=previous_lock,
            )
            written.append((lock_path, previous_lock, lock_content))
        except Exception:
            for path, previous in reversed(removed):
                if not path.exists():
                    _write_atomic(path, previous)
            for path, previous, content in reversed(written):
                _restore_owned_file(path, previous, content)
            raise
        return []
    except Exception as exc:
        return [Diagnostic("error", "RENDER", str(exc))]
