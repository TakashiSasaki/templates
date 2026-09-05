from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "delayed-qualification" / "cases.json"
PROFILE = ROOT / "profiles" / "pull-request.yml"
CANONICAL = ROOT / "policy" / "pull-request" / "defer-revision-bound-qualification.md"


def _text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").lower()


def test_delayed_qualification_rule_is_canonical_and_profiled() -> None:
    canonical = CANONICAL.read_text(encoding="utf-8").lower()
    profile = PROFILE.read_text(encoding="utf-8").lower()

    assert "id: pull-request.defer-revision-bound-qualification-until-required" in canonical
    assert "severity: mandatory" in canonical
    assert "policy/pull-request/defer-revision-bound-qualification.md" in profile

    for concept in (
        "construction head",
        "provisional candidate",
        "qualification head",
        "publication identity",
    ):
        assert concept in canonical


def test_delayed_qualification_scenarios_are_wired_across_authorities() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    assert len(cases) >= 7

    names = set()
    for case in cases:
        name = case["name"]
        assert name not in names
        names.add(name)

        required = case["required"]
        assert required
        for relative_path, fragments in required.items():
            text = _text(relative_path)
            assert fragments
            for fragment in fragments:
                assert fragment.lower() in text, f"{name}: missing {fragment!r} in {relative_path}"


def test_provisional_state_does_not_weaken_required_qualification() -> None:
    canonical = CANONICAL.read_text(encoding="utf-8").lower()

    for requirement in (
        "do not use this rule to suppress repository-required automatic checks",
        "do not use this rule",
        "must not weaken exact-head ci",
        "independent exact-head review",
        "immutable-head merge protection",
        "release trust",
        "provenance",
        "publication",
    ):
        assert requirement in canonical
