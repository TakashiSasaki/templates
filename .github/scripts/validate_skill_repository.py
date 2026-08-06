#!/usr/bin/env python3
"""Validate Skill repository structure and all profile contracts."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

from lib.profile_contracts import (
    ParseError,
    ProfileSelection,
    SkillDocument,
    ValuePolicy,
)


SCRIPT_ROOT = Path(__file__).resolve().parent


def run(arguments: list[str] | None = None) -> int:
    effective_arguments = list(sys.argv[1:] if arguments is None else arguments)
    if len(effective_arguments) > 1:
        print(
            f"usage: python {Path(__file__).name} [SKILL_ROOT]",
            file=sys.stderr,
        )
        return 2

    repository_root = Path(
        effective_arguments[0] if effective_arguments else Path.cwd()
    ).expanduser().resolve()
    if not repository_root.is_dir():
        print(
            f"Skill root is not a directory: {repository_root}",
            file=sys.stderr,
        )
        return 2

    previous_directory = Path.cwd()
    os.chdir(repository_root)
    try:
        try:
            skill = SkillDocument.read("SKILL.md")
            selection = ProfileSelection.load("SKILL.md", document=skill)
        except (ParseError, OSError) as exc:
            print(exc, file=sys.stderr)
            return 1

        errors: list[str] = []
        name = skill.metadata.get("name")
        if not (
            isinstance(name, str)
            and 1 <= len(name) <= 64
            and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
        ):
            errors.append(
                "SKILL.md frontmatter name must be a 1-64 character lowercase "
                "hyphenated string."
            )

        description = skill.metadata.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append(
                "SKILL.md frontmatter description must be a non-empty string."
            )

        if not selection.template_scaffold():
            license_template = Path("LICENSE.template")
            if license_template.exists() or license_template.is_symlink():
                errors.append(
                    "A concrete skill must replace or remove LICENSE.template."
                )

            readme_path = Path("README.md")
            if readme_path.is_file():
                try:
                    readme = readme_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    readme = None
                canonical_title = "# Language-neutral Agent Skill Template"
                canonical_identity = (
                    "This repository is a template for developing a portable "
                    "Agent Skill"
                )
                if (
                    readme is not None
                    and canonical_title in readme
                    and canonical_identity in readme
                ):
                    errors.append(
                        "A concrete skill must replace or remove the canonical "
                        "template README identity."
                    )

        resource_specs = {
            "Reference": {
                "directory": "references",
                "placeholder": "references/TODO.md",
                "required_fields": ("Read when", "Provides"),
            },
            "Asset": {
                "directory": "assets",
                "placeholder": "assets/TODO",
                "required_fields": ("Use when", "Handling"),
            },
            "Script": {
                "directory": "scripts",
                "placeholder": "scripts/TODO",
                "required_fields": ("Run when", "Exact invocation"),
            },
        }

        declarations_by_path: dict[str, object] = {}
        for label, specification in resource_specs.items():
            for declaration in skill.declarations(label):
                path = declaration.path
                if path == specification["placeholder"]:
                    continue

                pure_path = PurePosixPath(path)
                clean_path = pure_path.as_posix()
                expected_prefix = f"{specification['directory']}/"
                invalid_segments = any(
                    part in {"", ".", ".."} for part in pure_path.parts
                )
                if (
                    pure_path.is_absolute()
                    or invalid_segments
                    or clean_path != path
                    or not path.startswith(expected_prefix)
                ):
                    errors.append(
                        f"SKILL.md line {declaration.line_number} has an invalid "
                        f"{label} path: {path}"
                    )
                    continue

                if path in declarations_by_path:
                    errors.append(
                        "SKILL.md declares the same operational resource more "
                        f"than once: {path}"
                    )
                    continue

                declarations_by_path[path] = declaration

                for field in specification["required_fields"]:
                    value = declaration.fields.get(field)
                    if not ValuePolicy.resolved(value):
                        errors.append(
                            f"SKILL.md declaration for {path} must include a "
                            f"concrete '{field}:' value."
                        )

                resource_path = Path(path)
                if not resource_path.is_file() or resource_path.is_symlink():
                    errors.append(
                        "SKILL.md declares a missing or non-regular operational "
                        f"resource: {path}"
                    )

        for specification in resource_specs.values():
            directory = str(specification["directory"])
            directory_path = Path(directory)
            if directory_path.is_symlink():
                errors.append(
                    "Operational resource directory symlinks are not allowed: "
                    f"{directory}"
                )
                continue
            if not directory_path.is_dir():
                continue

            for current_root, directory_names, file_names in os.walk(
                directory_path, followlinks=False
            ):
                root = Path(current_root)
                directory_names.sort()
                file_names.sort()

                retained_directories: list[str] = []
                for name_entry in directory_names:
                    path = root / name_entry
                    relative = path.as_posix()
                    if path.is_symlink():
                        errors.append(
                            "Operational resource symlinks are not allowed: "
                            f"{relative}"
                        )
                    else:
                        retained_directories.append(name_entry)
                directory_names[:] = retained_directories

                for name_entry in file_names:
                    path = root / name_entry
                    relative = path.as_posix()
                    if path.is_symlink():
                        errors.append(
                            "Operational resource symlinks are not allowed: "
                            f"{relative}"
                        )
                        continue
                    if relative == f"{directory}/README.md":
                        continue
                    if not path.is_file():
                        errors.append(
                            "Operational resources must be regular files: "
                            f"{relative}"
                        )
                        continue
                    if relative not in declarations_by_path:
                        resource_label = next(
                            (
                                candidate_label
                                for candidate_label, candidate_specification
                                in resource_specs.items()
                                if relative.startswith(
                                    f"{candidate_specification['directory']}/"
                                )
                            ),
                            None,
                        )
                        errors.append(
                            "SKILL.md must declare the exact retained resource "
                            f"path as '{resource_label}: {relative}'."
                        )

        if errors:
            for error in dict.fromkeys(errors):
                print(error, file=sys.stderr)
            return 1

        profile_validator = SCRIPT_ROOT / "validate_profile_contracts.py"
        environment = os.environ.copy()
        environment.pop("RUBYOPT", None)
        completed = subprocess.run(
            [sys.executable, str(profile_validator)],
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode or 1

        print("Agent Skill repository structure and profile contracts are valid.")
        return 0
    finally:
        os.chdir(previous_directory)


if __name__ == "__main__":
    raise SystemExit(run())
