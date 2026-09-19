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
REVISION = "04bf86977675bfc8f1082b8b8d6c70817f4eb9c2"
RULE_BLOB = "9761cdbcd21b0e8ba2f3eb2ffb306725a82f5eef"
SKILL_BLOB = "06efa38681e374636bcabcbcb984be5ec43b47ee"
PLANNER_BLOB = "16c0907a19e3f8d339fe81e29f7b204e791fc781"
GATE_REVISION = "94eb84397d913f2ebb0e2c79d0b841ae580fbc31"
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
        "repository-skills/land-templates-stack/scripts/plan_review_scope.py",
        PLANNER_BLOB,
        REVISION,
        "2ef890673600f0f4c30b53cef7c19a78d34cf5bc",
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
    assert (
        _git(
            "rev-parse",
            f"{REVISION}:repository-skills/land-templates-stack/scripts/plan_review_scope.py",
        )
        == PLANNER_BLOB
    )


def test_policy_local_landing_entry_has_an_adjacent_source_manifest() -> None:
    local_skill = ROOT / ".agents/skills/land-templates-stack/SKILL.md"
    source = ROOT / ".agents/skills/land-templates-stack/source.json"
    assert local_skill.is_file()
    data = json.loads(source.read_text(encoding="utf-8"))
    assert data["schema_version"] == 2
    assert data["repository"] == "TakashiSasaki/templates"
    assert data["revision"] == REVISION
    assert data["path"] == "repository-skills/land-templates-stack/SKILL.md"
    assert data["blob_sha"] == SKILL_BLOB
    assert data["closure"] == [
        {
            "path": "repository-policy/stacked-pr-landing.md",
            "blob_sha": RULE_BLOB,
        },
        {
            "path": "repository-skills/land-templates-stack/scripts/plan_review_scope.py",
            "blob_sha": PLANNER_BLOB,
        },
    ]
    text = local_skill.read_text(encoding="utf-8")
    assert "version-2" in text
    assert "scope planner" in text
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
        "schema_version": 2,
        "kind": "policy-adapter-reference",
        "repository": "TakashiSasaki/templates",
            "revision": GATE_REVISION,
        "path": "skills/pr-merge-gate/SKILL.md",
        "blob_sha": "2ef890673600f0f4c30b53cef7c19a78d34cf5bc",
        "closure": data["closure"],
    }
    profile = yaml.safe_load(_git("show", f"{GATE_REVISION}:profiles/pull-request.yml"))
    references = _git("ls-tree", "-r", "--name-only", GATE_REVISION,
                      "skills/pr-merge-gate/references").splitlines()
    expected = set(profile["policy_files"] + references + ["profiles/pull-request.yml"])
    assert {entry["path"] for entry in data["closure"]} == expected
    assert len(data["closure"]) == len(expected)
    for entry in data["closure"]:
        assert _git("rev-parse", f"{GATE_REVISION}:{entry['path']}") == entry["blob_sha"]
