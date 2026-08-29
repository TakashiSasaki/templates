from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
SITE_ACCEPTANCE = (
    ROOT / ".agents" / "skills" / "site-pr-exact-head-acceptance" / "SKILL.md"
)


def test_site_routing_does_not_restore_blanket_acceptance_restart() -> None:
    routing = AGENTS.read_text(encoding="utf-8").lower()
    skill = SITE_ACCEPTANCE.read_text(encoding="utf-8").lower()

    for invariant in (
        "invalidate evidence bound to the previous head",
        "reacquire only the affected site-acceptance and merge-gate evidence",
        "do not discard unaffected evidence",
        "do not become mandatory gates unless current repository authority requires them",
    ):
        assert invariant in routing

    assert "discard final acceptance for the previous head" not in routing
    assert "do not discard the entire snapshot when only one binding changes" in skill
