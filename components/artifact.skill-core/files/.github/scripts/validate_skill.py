#!/usr/bin/env python3
"""Validate the composition-era Agent Skill scaffold with stdlib only."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ALLOWED_PROFILES = {"instruction-only", "knowledge-augmented", "asset-driven", "script-assisted"}
LEGACY_CAPABILITY_PROFILES = {"packaged-cli", "mcp-enabled", "browser-interface", "headless-service"}
CAPABILITY_FILES = {
    "capability.runtime": "RUNTIME.md",
    "capability.cli": "CLI_INTERFACE.md",
    "capability.mcp": "MCP_INTERFACE.md",
    "capability.mcp-apps": "MCP_APPS.md",
    "capability.web-interface": "WEB_INTERFACE.md",
    "capability.service": "SERVICE_INTERFACE.md",
}
DEPENDENT_FILES = {
    "CLI_INTERFACE.md": {"RUNTIME.md"},
    "MCP_INTERFACE.md": {"RUNTIME.md"},
    "MCP_APPS.md": {"RUNTIME.md", "MCP_INTERFACE.md"},
    "WEB_INTERFACE.md": {"RUNTIME.md"},
    "SERVICE_INTERFACE.md": {"RUNTIME.md"},
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def parse_frontmatter(text: str, errors: list[str]) -> None:
    if not text.startswith("---\n"):
        fail(errors, "SKILL.md must start with YAML-style frontmatter")
        return
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(errors, "SKILL.md frontmatter is not closed")
        return
    frontmatter = text[4:end]
    for key in ("name", "description"):
        match = re.search(rf"(?m)^{key}:\s*(.+?)\s*$", frontmatter)
        if not match or not match.group(1).strip():
            fail(errors, f"SKILL.md frontmatter requires non-empty {key}")


def parse_profiles(text: str, errors: list[str]) -> set[str]:
    matches = re.findall(r"(?m)^Selected profiles:\s*(.+?)\s*$", text)
    if len(matches) != 1:
        fail(errors, "SKILL.md must contain exactly one Selected profiles line")
        return set()
    raw = matches[0].strip()
    if raw == "template-scaffold":
        return {"template-scaffold"}
    tags = {item.strip() for item in raw.split(",") if item.strip()}
    legacy = tags & LEGACY_CAPABILITY_PROFILES
    if legacy:
        fail(errors, f"legacy application profile tags are composition capabilities: {sorted(legacy)}")
    unknown = tags - ALLOWED_PROFILES
    if unknown:
        fail(errors, f"unsupported Skill profile tags: {sorted(unknown)}")
    if "instruction-only" in tags and len(tags) != 1:
        fail(errors, "instruction-only must be selected alone")
    if not tags:
        fail(errors, "Selected profiles must not be empty")
    return tags


def declared_paths(text: str, label: str) -> list[str]:
    return [m.strip() for m in re.findall(rf"(?m)^{re.escape(label)}:\s*(.+?)\s*$", text) if "TODO" not in m]


def validate_resources(root: Path, text: str, profiles: set[str], errors: list[str]) -> None:
    if profiles == {"template-scaffold"}:
        return
    specs = [
        ("knowledge-augmented", "Reference", "references/"),
        ("asset-driven", "Asset", "assets/"),
        ("script-assisted", "Script", "scripts/"),
    ]
    for profile, label, prefix in specs:
        paths = declared_paths(text, label)
        if profile in profiles and not paths:
            fail(errors, f"{profile} requires at least one concrete {label}: declaration")
        if profile not in profiles and paths:
            fail(errors, f"{label}: declarations require profile {profile}")
        for rel in paths:
            if not rel.startswith(prefix):
                fail(errors, f"{label} path must be under {prefix}: {rel}")
            elif not (root / rel).is_file():
                fail(errors, f"declared {label} does not exist: {rel}")


def validate_capability_files(root: Path, errors: list[str]) -> None:
    if (root / "INTERFACES.md").exists():
        fail(errors, "INTERFACES.md is a retired legacy authority; agent routing belongs in SKILL.md")
    for filename, required in DEPENDENT_FILES.items():
        if (root / filename).exists():
            for dependency in sorted(required):
                if not (root / dependency).is_file():
                    fail(errors, f"{filename} requires {dependency}")


def validate_lock_projection(root: Path, errors: list[str]) -> None:
    lock_path = root / ".template-composition" / "lock.json"
    if not lock_path.exists():
        return
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(errors, f"cannot read composition lock: {exc}")
        return
    resolved = {entry.get("id") for entry in lock.get("resolved_components", []) if isinstance(entry, dict)}
    if "artifact.skill-core" not in resolved:
        fail(errors, "composition lock for a Skill artifact must resolve artifact.skill-core")
    for component, filename in CAPABILITY_FILES.items():
        selected = component in resolved
        present = (root / filename).is_file()
        if selected != present:
            state = "selected but missing" if selected else "present but not selected"
            fail(errors, f"{component}: {filename} is {state}")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    skill = root / "SKILL.md"
    if not skill.is_file():
        return ["SKILL.md is required"]
    text = skill.read_text(encoding="utf-8")
    parse_frontmatter(text, errors)
    profiles = parse_profiles(text, errors)
    validate_resources(root, text, profiles, errors)
    validate_capability_files(root, errors)
    validate_lock_projection(root, errors)
    if profiles == {"instruction-only"}:
        for filename in sorted(CAPABILITY_FILES.values()):
            if (root / filename).exists():
                fail(errors, f"instruction-only Skill must not retain {filename}")
        for dirname in ("references", "assets", "scripts"):
            path = root / dirname
            if path.exists() and any(path.iterdir()):
                fail(errors, f"instruction-only Skill must not retain non-empty {dirname}/")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    errors = validate(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Skill scaffold validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
