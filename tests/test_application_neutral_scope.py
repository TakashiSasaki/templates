from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs/adr/0003-application-neutral-policy-scope.md"
README = ROOT / "README.md"
MKDOCS = ROOT / "mkdocs.yml"
REMOVED_PROFILE = ROOT / "profiles/web-application.yml"
REMOVED_DOCUMENT = ROOT / "docs/web-application-profile.md"
REMOVED_RULE_DIRECTORY = ROOT / "policy/interfaces"
REMOVED_RULE_IDS = {
    "interfaces.define-surface-boundaries",
    "interfaces.isolate-surface-dependencies",
    "interfaces.make-navigation-intentional",
    "interfaces.model-user-visible-states",
    "interfaces.preserve-accessible-interaction",
    "interfaces.separate-diagnostics",
    "interfaces.keep-surface-contracts-synchronized",
    "interfaces.adapt-layout-to-content",
}
ARTIFACT_CATEGORY_PROFILES = {
    "web-application",
    "cli-application",
    "mobile-application",
    "library",
    "backend-service",
}


def test_application_specific_profile_and_rules_are_absent() -> None:
    assert not REMOVED_PROFILE.exists()
    assert not REMOVED_DOCUMENT.exists()
    assert not REMOVED_RULE_DIRECTORY.exists()

    shared_policy = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "policy").rglob("*.md"))
    )
    for rule_id in REMOVED_RULE_IDS:
        assert rule_id not in shared_policy


def test_builtin_profiles_do_not_classify_artifact_categories() -> None:
    profile_names = {path.stem for path in (ROOT / "profiles").glob("*.yml")}

    assert ARTIFACT_CATEGORY_PROFILES.isdisjoint(profile_names)


def test_application_neutral_scope_decision_is_documented_and_published() -> None:
    decision = ADR.read_text(encoding="utf-8")
    navigation = MKDOCS.read_text(encoding="utf-8")

    assert "Status: Accepted" in decision
    assert "Built-in shared policy must be application-type independent" in decision
    assert "Profiles may classify operational situations or risk postures" in decision
    assert "web-application-profile.md" not in navigation
    assert "adr/0003-application-neutral-policy-scope.md" in navigation


def test_current_readme_states_application_neutral_scope() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "application-type-independent" in readme
    assert "does not define the architecture or product requirements" in readme
