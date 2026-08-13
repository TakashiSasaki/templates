#!/usr/bin/env python3
"""Audit the completed source/distribution restructuring boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def read_text(relative: str) -> str:
    try:
        return (ROOT / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def main() -> int:
    failures: list[str] = []
    required_source_files = [
        "README.md", "AGENTS.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE",
        "distribution-manifest.json", "docs/architecture/distribution-boundary.md",
        "docs/architecture/distribution-classification.json",
        "docs/publication-catalog.json", "docs/publication-maintenance.md",
        "maintainer/README.md", "template/SKILL.md", "template/README.md",
        "template/AGENTS.md",
    ]
    for relative in required_source_files:
        if not regular_file(ROOT / relative):
            failures.append(f"missing required source artifact: {relative}")

    forbidden_root_skill_paths = [
        "SKILL.md", "RUNTIME.md", "INTERFACES.md", "CLI_INTERFACE.md",
        "MCP_INTERFACE.md", "MCP_APPS.md", "WEB_INTERFACE.md", "LICENSE.template",
        "assets", "examples", "mcp", "references", "scripts", "src", "tests",
    ]
    for relative in forbidden_root_skill_paths:
        path = ROOT / relative
        if path.exists() or path.is_symlink():
            failures.append(f"obsolete root Skill authority reintroduced: {relative}")

    canonical_validator_relatives = [
        "lib/core_profile_interfaces.py", "lib/core_profile_runtime.py",
        "lib/profile_contracts.py", "validate_bundled_mcp_client_consistency.py",
        "validate_cli_exit_code_contract.py", "validate_cli_structured_output_contract.py",
        "validate_concrete_profile_consistency.py", "validate_core_profile_contracts.py",
        "validate_decomposed_interface_contracts.py", "validate_extended_profile_contracts.py",
        "validate_interface_routing_contract.py", "validate_interface_runtime_consistency.py",
        "validate_interface_summary_details.py", "validate_late_review_contracts.py",
        "validate_mcp_extensions.py", "validate_mcp_protocol_conformance.py",
        "validate_mcp_runtime_authority.py", "validate_profile_contracts.py",
        "validate_review_followup_contracts.py",
        "validate_selected_contract_scalar_placeholders.py",
        "validate_skill_repository.py",
    ]
    for relative in canonical_validator_relatives:
        canonical = ROOT / "template/.github/scripts" / relative
        legacy = ROOT / ".github/scripts" / relative
        if not regular_file(canonical):
            failures.append(f"canonical downstream validator is missing: {relative}")
        if legacy.exists() or legacy.is_symlink():
            failures.append(f"alternate root validator authority reintroduced: {relative}")

    try:
        manifest = json.loads((ROOT / "distribution-manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 2:
            failures.append("distribution manifest schema must remain canonical-inventory v2")
        if "mirrors" in manifest:
            failures.append("distribution manifest must not regain mirrors")
        if "distribution_owned_files" in manifest:
            failures.append("distribution manifest must not regain distribution_owned_files")
        if not isinstance(manifest.get("distribution_files"), list):
            failures.append("distribution manifest must declare canonical distribution_files")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"invalid distribution manifest: {exc}")

    try:
        classification = json.loads(
            (ROOT / "docs/architecture/distribution-classification.json").read_text(encoding="utf-8")
        )
        top_level = classification["topLevelClassification"]
        if top_level.get("distribution") != ["template"]:
            failures.append("template must remain the sole distribution root")
        if top_level.get("split") != []:
            failures.append("completed separation must have no split top-level entries")
        if "maintainer" not in top_level.get("maintainer", []):
            failures.append("maintainer directory must be source-owned")

        profile = classification["profileModel"]
        if profile.get("templateMarker") != "template-scaffold":
            failures.append("template marker changed")
        if profile.get("exclusiveProfiles") != ["instruction-only"]:
            failures.append("exclusive profile set changed")
        expected_composable = [
            "asset-driven", "browser-interface", "headless-service",
            "knowledge-augmented", "mcp-enabled", "packaged-cli", "script-assisted",
        ]
        if profile.get("composableProfiles") != expected_composable:
            failures.append("composable profile set changed")
        if profile.get("compositionRule") != "union-of-required-contracts":
            failures.append("profile composition rule changed")
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"invalid distribution classification: {exc}")

    try:
        catalog = json.loads((ROOT / "docs/publication-catalog.json").read_text(encoding="utf-8"))
        documents = catalog["documents"]
        expected_ids = [
            "overview", "skill-contract", "skill-profiles", "profile-contract-map",
            "runtime-decision-record", "interface-routing", "packaged-cli-interface",
            "mcp-interface", "mcp-apps-interface", "human-web-interface",
            "architecture", "runtime-selection", "mcp-transports", "mcp-apps-guidance",
        ]
        actual_ids = [document["id"] for document in documents]
        if actual_ids != expected_ids:
            failures.append("stable publication document IDs changed")
        for document in documents:
            source = document["source"]
            if not regular_file(ROOT / source):
                failures.append(f"publication source is missing: {source}")
            if document["id"] == "overview":
                if source != "README.md":
                    failures.append("overview must remain the source-product README")
            elif not source.startswith("template/"):
                failures.append(f"consumer publication source escapes template/: {source}")
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"invalid publication catalog: {exc}")

    root_readme = read_text("README.md")
    for snippet in (
        "The canonical user-facing artifact and its canonical source tree are `template/`.",
        "cp -a template/. /path/to/new-skill/",
        "The branch root deliberately contains no `SKILL.md`",
    ):
        if snippet not in root_readme:
            failures.append(f"source README omits completed boundary: {snippet!r}")

    if "This repository is a template for developing a portable Agent Skill" not in read_text("template/README.md"):
        failures.append("template README lost its consumer identity")

    boundary = read_text("docs/architecture/distribution-boundary.md")
    for snippet in (
        "The branch root is not an installable Skill directory.",
        "The copyable distribution is `template/`, and `template/` is also the sole canonical source tree",
        "The structural separation is complete.",
    ):
        if snippet not in boundary:
            failures.append(f"distribution boundary omits completion statement: {snippet!r}")
    for stale in (
        "future `template/`", "After this migration",
        "Until the structural migration is merged", "The future `template/` tree",
        "The intended source layout",
    ):
        if stale in boundary:
            failures.append(f"distribution boundary retains transitional wording: {stale!r}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Skill template restructuring completion audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
