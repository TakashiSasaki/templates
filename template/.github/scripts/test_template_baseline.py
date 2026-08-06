#!/usr/bin/env python3
"""Validate the copyable template's Skill-root boundary."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run() -> int:
    failures: list[str] = []

    required = [
        "SKILL.md",
        "README.md",
        "AGENTS.md",
        ".github/scripts/validate-skill-repository.rb",
        ".github/scripts/validate-profile-contracts.rb",
        ".github/scripts/lib/profile_contracts.py",
    ]
    for relative in required:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            failures.append(f"missing required Skill-root file: {relative}")

    forbidden = [
        "template",
        "distribution-manifest.json",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "docs/publication-catalog.json",
        "docs/publication-maintenance.md",
        "docs/architecture/distribution-boundary.md",
        "docs/architecture/distribution-classification.json",
        ".github/REVIEW_GUIDELINES.md",
        ".github/fixtures",
        ".github/workflows/pages.yml",
        ".github/workflows/validate-structure.yml",
        ".github/workflows/validate-portable-consumption.yml",
        ".github/workflows/validate-extended-profile-contracts.yml",
    ]
    for relative in forbidden:
        path = ROOT / relative
        if path.exists() or path.is_symlink():
            failures.append(
                f"source-maintainer path leaked into Skill distribution: {relative}"
            )

    skill_path = ROOT / "SKILL.md"
    if skill_path.is_file():
        skill = skill_path.read_text(encoding="utf-8")
        selections = [
            line for line in skill.splitlines() if line.startswith("Selected profiles:")
        ]
        if len(selections) != 1:
            failures.append(
                "SKILL.md must contain exactly one Selected profiles line"
            )

        if selections and selections[0].strip() == "Selected profiles: template-scaffold":
            readme = (ROOT / "README.md").read_text(encoding="utf-8")
            if not (
                "# Language-neutral Agent Skill Template" in readme
                and "This repository is a template for developing a portable Agent Skill"
                in readme
            ):
                failures.append(
                    "uncustomized template must retain its canonical README identity"
                )
            if not (ROOT / "LICENSE.template").is_file():
                failures.append(
                    "uncustomized template must retain LICENSE.template"
                )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Agent Skill template-root boundary is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
