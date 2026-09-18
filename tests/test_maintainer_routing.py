from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "repository-policy" / "maintainer-merge-routing.md"
CONFIG = ROOT / ".agent-policy.yml"
AGENTS = ROOT / "AGENTS.md"
REVIEW = ROOT / ".review-authority" / "review-policy.md"
REVISION = "a878da560c5286634b21671b54793e26ed8167b2"
RULE_BLOB = "9dd1c5498dd9b37ef91afd65ad400fbdee13ee29"
SKILL_BLOB = "b433bdf781eb1fd0f32a525bfd68bac2563316d7"
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_policy_routing_is_declared_in_both_generated_contexts() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    for context in ("coding", "review"):
        files = config["contexts"][context]["project_policy"]["files"]
        assert "repository-policy/maintainer-merge-routing.md" in files
        assert "repository-policy/stacked-pr-landing.md" not in files


def test_routing_declares_immutable_rule_and_skill_bindings() -> None:
    text = ROUTING.read_text(encoding="utf-8")
    for required in (
        REVISION,
        "repository-policy/stacked-pr-landing.md",
        RULE_BLOB,
        "repository-skills/land-templates-stack/SKILL.md",
        SKILL_BLOB,
        "733c86941f8154f301a225054d88c6b8a477058a",
        "cb12e6aa296a0ba4e7871dc57b554ef867eeefed",
        "33a7ab809225c2a8b8dd2598ef04d0a39cf076a7",
        "stop as blocked",
        "single PR",
        "same-authority stack",
    ):
        assert required in text


def test_generated_entrypoints_expose_route_without_copying_rule() -> None:
    route = ROUTING.read_text(encoding="utf-8")
    for generated in (AGENTS, REVIEW):
        text = generated.read_text(encoding="utf-8")
        assert REVISION in text
        assert "repository-skills/land-templates-stack/SKILL.md" in text
        assert "Do not edit this generated file directly" in text
        assert "# Maintainer stacked-PR landing rules" not in text
        assert route.split("# Maintainer merge routing", 1)[1].strip() in text


def test_pinned_objects_match_the_committed_snapshot() -> None:
    assert FULL_SHA.fullmatch(REVISION)
    assert _git("rev-parse", f"{REVISION}:repository-policy/stacked-pr-landing.md") == RULE_BLOB
    assert (
        _git("rev-parse", f"{REVISION}:repository-skills/land-templates-stack/SKILL.md")
        == SKILL_BLOB
    )


def test_policy_local_landing_entry_has_an_adjacent_source_manifest() -> None:
    local_skill = ROOT / ".agents/skills/land-templates-stack/SKILL.md"
    source = ROOT / ".agents/skills/land-templates-stack/source.json"
    assert local_skill.is_file()
    data = json.loads(source.read_text(encoding="utf-8"))
    assert data["repository"] == "TakashiSasaki/templates"
    assert data["revision"] == REVISION
    assert data["path"] == "repository-skills/land-templates-stack/SKILL.md"
    assert data["blob_sha"] == SKILL_BLOB
    text = local_skill.read_text(encoding="utf-8")
    assert ".agents/skills/pr-merge-gate/SKILL.md" in text
    assert "shim's separate" in text
    assert "`source.json` before loading" in text


def test_policy_local_gate_entry_has_a_separate_shared_gate_manifest() -> None:
    local_skill = ROOT / ".agents/skills/pr-merge-gate/SKILL.md"
    source = ROOT / ".agents/skills/pr-merge-gate/source.json"
    assert local_skill.is_file()
    text = local_skill.read_text(encoding="utf-8")
    assert "contains no acceptance semantics" in text
    data = json.loads(source.read_text(encoding="utf-8"))
    assert data == {
        "schema_version": 1,
        "kind": "policy-adapter-reference",
        "repository": "TakashiSasaki/templates",
        "revision": "733c86941f8154f301a225054d88c6b8a477058a",
        "path": "skills/pr-merge-gate/SKILL.md",
        "blob_sha": "cb12e6aa296a0ba4e7871dc57b554ef867eeefed",
    }
