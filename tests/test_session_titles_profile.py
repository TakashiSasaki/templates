from pathlib import Path

from agent_policy.policy_loader import load_rules, profile_policy_paths

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODULES = [
    "policy/session-titles/terminal-boundary.md",
    "policy/session-titles/outcome-fidelity.md",
    "policy/session-titles/presentation-boundary.md",
]
EXPECTED_RULE_IDS = [
    "session-titles.generate-at-terminal-boundary",
    "session-titles.describe-observed-outcome",
    "session-titles.keep-title-presentation-non-authoritative",
]


def test_session_titles_profile_is_explicitly_selectable_and_not_implicit() -> None:
    selected = [
        path.relative_to(ROOT).as_posix()
        for path in profile_policy_paths("session-titles")
    ]
    assert selected == EXPECTED_MODULES

    for profile_file in (ROOT / "profiles").glob("*.yml"):
        if profile_file.stem == "session-titles":
            continue
        profile_text = profile_file.read_text(encoding="utf-8")
        assert all(module not in profile_text for module in EXPECTED_MODULES)

    rules = load_rules(ROOT, ["session-titles"], [])
    assert [rule.id for rule in rules] == EXPECTED_RULE_IDS
    assert all(rule.severity == "mandatory" for rule in rules)
    assert all(not rule.overridable for rule in rules)


def test_session_title_rules_bind_to_terminal_state_without_becoming_authority() -> None:
    texts = {
        path.name: path.read_text(encoding="utf-8")
        for path in (ROOT / "policy" / "session-titles").glob("*.md")
    }

    terminal = texts["terminal-boundary.md"]
    assert "established terminal boundary" in terminal
    assert "human-handoff" in terminal
    assert "session is expected to continue" in terminal
    assert "terminal boundary rather than at session start" in terminal

    fidelity = texts["outcome-fidelity.md"]
    assert "actual result" in fidelity
    assert "initial objective" in fidelity
    assert "must encode the established terminal state" in fidelity
    assert "Do not imply completion" in fidelity

    presentation = texts["presentation-boundary.md"]
    assert "presentation and navigation metadata" in presentation
    assert "not as repository state" in presentation
    assert "terminal title proposal" in presentation
    assert "must not change the established work state" in presentation


def test_session_title_shared_policy_is_provider_neutral() -> None:
    shared_text = "\n".join(
        (ROOT / module).read_text(encoding="utf-8") for module in EXPECTED_MODULES
    )
    provider_specific_terms = ["ChatGPT", "OpenAI", "Codex", "Claude", "Gemini"]
    assert all(term not in shared_text for term in provider_specific_terms)
