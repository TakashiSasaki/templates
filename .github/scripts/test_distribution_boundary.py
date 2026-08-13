#!/usr/bin/env python3
"""Validate the source/distribution classification boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION = ROOT / "docs/architecture/distribution-classification.json"
IGNORED_LOCAL_ENTRIES = {".git", ".bundle", ".ruby-lsp", ".DS_Store"}


def main() -> int:
    failures: list[str] = []
    try:
        value = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    except Exception as exc:
        print(
            f"distribution classification could not be read: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    if not isinstance(value, dict):
        failures.append("distribution classification must be a JSON object")
        value = {}

    classification = value.get("topLevelClassification")
    expected_categories = {"distribution", "maintainer", "split"}
    if not isinstance(classification, dict) or set(classification) != expected_categories:
        failures.append(
            "topLevelClassification must contain exactly distribution, split, and maintainer"
        )
        classification = {}

    classified: list[str] = []
    for category, entries in classification.items():
        if not isinstance(entries, list) or not all(
            isinstance(entry, str) and entry for entry in entries
        ):
            failures.append(f"{category} entries must be non-empty strings")
            continue
        if entries != sorted(entries):
            failures.append(f"{category} entries must be sorted")
        if len(entries) != len(set(entries)):
            failures.append(f"{category} entries must be unique")
        classified.extend(entries)

    if len(classified) != len(set(classified)):
        failures.append("top-level entries may not be multiply classified")

    actual = sorted(
        path.name for path in ROOT.iterdir() if path.name not in IGNORED_LOCAL_ENTRIES
    )
    if actual != sorted(classified):
        failures.append(
            f"top-level classification mismatch: expected {actual!r}, "
            f"got {sorted(classified)!r}"
        )
    if classification.get("distribution") != ["template"]:
        failures.append("template must be the sole distribution top-level entry")
    if "distribution-manifest.json" not in classification.get("maintainer", []):
        failures.append("distribution manifest must remain maintainer-owned")

    if type(value.get("schemaVersion")) is not int or value.get("schemaVersion") != 1:
        failures.append("schemaVersion must be integer 1")
    if value.get("targetDistributionRoot") != "template":
        failures.append("targetDistributionRoot must be template")
    if value.get("directCopyDestination") != ".":
        failures.append("directCopyDestination must be .")
    if value.get("contentTransformationAllowed") is not False:
        failures.append("contentTransformationAllowed must be false")

    roots = value.get("targetSourceRoots")
    expected_roots = {
        "distribution": "template",
        "maintainer": ".",
        "publicationInterface": "docs/publication-catalog.json",
    }
    if roots != expected_roots:
        failures.append("targetSourceRoots mismatch")
    for path_text in expected_roots.values():
        path = PurePosixPath(path_text)
        if path.is_absolute() or ".." in path.parts or any(
            part.lower() == ".git" for part in path.parts
        ):
            failures.append(f"unsafe target source root {path_text!r}")

    profile_model = value.get("profileModel")
    expected_composable = [
        "asset-driven",
        "browser-interface",
        "headless-service",
        "knowledge-augmented",
        "mcp-enabled",
        "packaged-cli",
        "script-assisted",
    ]
    if not isinstance(profile_model, dict):
        failures.append("profileModel must be an object")
    else:
        if profile_model.get("templateMarker") != "template-scaffold":
            failures.append("templateMarker must remain template-scaffold")
        if profile_model.get("exclusiveProfiles") != ["instruction-only"]:
            failures.append("instruction-only must remain the sole exclusive profile")
        if profile_model.get("composableProfiles") != expected_composable:
            failures.append("composable profiles changed")
        if profile_model.get("compositionRule") != "union-of-required-contracts":
            failures.append("composition rule must retain required-contract union")

    rules = value.get("requiredSeparationRules")
    if (
        not isinstance(rules, list)
        or len(rules) < 6
        or not all(isinstance(rule, str) and rule for rule in rules)
    ):
        failures.append(
            "requiredSeparationRules must contain at least six non-empty strings"
        )
    else:
        combined = " ".join(rules).lower()
        for term in (
            "branch root",
            "concrete skill root",
            "escape template",
            "publication",
            "profile",
            "clean-room",
        ):
            if term not in combined:
                failures.append(f"required separation rules omit {term}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Skill source and distribution boundary tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
