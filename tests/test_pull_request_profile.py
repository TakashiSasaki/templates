from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agent_policy.policy_loader import load_rules, parse_policy

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/pull-request.yml"
POLICY_DIR = ROOT / "policy/pull-request"

EXPECTED = [
    "pull-request.verify-target-branch-head-freshness",
    "pull-request.close-review-threads-before-merge",
]


def _rule_id(path: Path) -> str:
    source = path.relative_to(ROOT).as_posix()
    return parse_policy(path, source, "toolchain").id


def _metadata(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"missing YAML front matter: {path}"
    _, frontmatter, _body = text.split("---\n", 2)
    data = yaml.safe_load(frontmatter)
    assert isinstance(data, dict), f"invalid YAML front matter: {path}"
    return data


def test_pull_request_profile_is_closed_and_atomic() -> None:
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    paths = [ROOT / path for path in profile["policy_files"]]
    assert [path.parent for path in paths] == [POLICY_DIR] * len(paths)
    assert all(path.is_file() for path in paths)
    assert [_rule_id(path) for path in paths] == EXPECTED
    actual_files = sorted(path.name for path in POLICY_DIR.glob("*.md"))
    profile_files = sorted(path.name for path in paths)
    assert actual_files == profile_files


def test_pull_request_policy_metadata_schema() -> None:
    metadata = [_metadata(path) for path in sorted(POLICY_DIR.glob("*.md"))]
    required = {"id", "severity", "overridable", "order"}

    assert metadata
    assert all(required.issubset(item) for item in metadata)
    assert all(isinstance(item["id"], str) and item["id"] for item in metadata)
    assert all(
        isinstance(item["severity"], str) and item["severity"]
        for item in metadata
    )
    assert all(type(item["overridable"]) is bool for item in metadata)
    assert all(type(item["order"]) is int for item in metadata)

    orders = [item["order"] for item in metadata]
    assert len(orders) == len(set(orders))


def test_pull_request_profile_composes_with_coding_and_review_contexts() -> None:
    coding = load_rules(ROOT, ["core", "security-baseline", "pull-request"], [])
    review = load_rules(
        ROOT,
        ["core", "security-baseline", "review", "pull-request"],
        [],
    )
    for rules in (coding, review):
        rule_ids = [rule.id for rule in rules]
        assert len(rule_ids) == len(set(rule_ids))
        assert set(EXPECTED).issubset(rule_ids)


def test_pull_request_rules_are_provider_neutral() -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in POLICY_DIR.glob("*.md")
    )
    provider_terms = (
        "Antigravity",
        "Codex",
        "Gemini",
        "GitHub",
        "GitLab",
        "Bitbucket",
        "LEFT",
        "RIGHT",
        "REQUEST_CHANGES",
    )
    for provider_term in provider_terms:
        assert provider_term not in corpus
