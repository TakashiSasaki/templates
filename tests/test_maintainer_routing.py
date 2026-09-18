from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "repository-policy" / "maintainer-merge-routing.md"
CONFIG = ROOT / ".agent-policy.yml"
AGENTS = ROOT / "AGENTS.md"
REVIEW = ROOT / ".review-authority" / "review-policy.md"
REVISION = "5af977020fca701bcf6b7fb7ce12ca077b2d7220"
RULE_BLOB = "9dd1c5498dd9b37ef91afd65ad400fbdee13ee29"
SKILL_BLOB = "902b6e543d467b47b2b91819bfab5574a85456c7"
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
