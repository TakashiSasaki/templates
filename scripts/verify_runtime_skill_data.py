from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

from agent_policy.config import package_root
from agent_policy.renderer import GENERATED_MARKER, NON_GENERATED_SKILLS, render_skill

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = SCRIPT_DIR.parent


def generated_skill_inventory(root: Path) -> dict[str, tuple[str, ...]]:
    skills_root = root / "skills"
    if not skills_root.is_dir():
        raise ValueError(f"generated Skill root is missing: {skills_root}")

    inventory: dict[str, tuple[str, ...]] = {}
    for skill_root in sorted(skills_root.iterdir(), key=lambda path: path.name):
        if not skill_root.is_dir() or skill_root.name in NON_GENERATED_SKILLS:
            continue
        files = tuple(
            sorted(
                path.relative_to(skill_root).as_posix()
                for path in skill_root.rglob("*")
                if path.is_file()
            )
        )
        if not files:
            raise ValueError(f"generated Skill has no files: {skill_root.name}")
        inventory[skill_root.name] = files
    if not inventory:
        raise ValueError(f"no generated Skills found under: {skills_root}")
    return inventory


def compare_skill_inventories(
    expected: Mapping[str, tuple[str, ...]],
    actual: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    errors: list[str] = []

    missing_skills = sorted(set(expected) - set(actual))
    if missing_skills:
        errors.append(
            "installed generated Skills missing from package data: "
            + ", ".join(missing_skills)
        )

    unexpected_skills = sorted(set(actual) - set(expected))
    if unexpected_skills:
        errors.append(
            "installed package data contains unexpected generated Skills: "
            + ", ".join(unexpected_skills)
        )

    for skill_name in sorted(set(expected) & set(actual)):
        expected_files = set(expected[skill_name])
        actual_files = set(actual[skill_name])

        missing_files = sorted(expected_files - actual_files)
        if missing_files:
            errors.append(
                f"installed generated Skill {skill_name} is missing files: "
                + ", ".join(missing_files)
            )

        unexpected_files = sorted(actual_files - expected_files)
        if unexpected_files:
            errors.append(
                f"installed generated Skill {skill_name} has unexpected files: "
                + ", ".join(unexpected_files)
            )

    return tuple(errors)


def verify_runtime_skill_data(source_root: Path = SOURCE_ROOT) -> tuple[str, ...]:
    runtime_root = package_root()
    try:
        expected = generated_skill_inventory(source_root)
        actual = generated_skill_inventory(runtime_root)
    except (OSError, ValueError) as exc:
        return (str(exc),)

    errors = list(compare_skill_inventories(expected, actual))
    for skill_name in sorted(set(expected) & set(actual)):
        try:
            rendered = render_skill(skill_name)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"installed generated Skill {skill_name} cannot be rendered: {exc}")
            continue

        rendered_files = set(rendered)
        expected_files = set(expected[skill_name])
        if rendered_files != expected_files:
            errors.append(
                f"rendered generated Skill {skill_name} file inventory differs from source"
            )

        skill_document = rendered.get("SKILL.md")
        if skill_document is None:
            errors.append(f"rendered generated Skill {skill_name} has no SKILL.md")
        elif GENERATED_MARKER not in skill_document:
            errors.append(
                f"rendered generated Skill {skill_name} is missing the generated marker"
            )

    return tuple(errors)


def main() -> int:
    errors = verify_runtime_skill_data()
    if errors:
        for error in errors:
            print(f"Runtime Skill data verification failed: {error}", file=sys.stderr)
        return 1

    print("Installed generated Skill package data matches source and renders successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
