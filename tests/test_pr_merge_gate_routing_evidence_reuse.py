from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"


def test_composition_routing_uses_selective_evidence_invalidation() -> None:
    routing = AGENTS.read_text(encoding="utf-8").lower()

    for invariant in (
        "invalidate evidence bound to the previous head",
        "reacquiring only the evidence whose bindings changed",
        "do not discard unaffected evidence",
        "do not automatically discard unrelated exact-head ci or review evidence",
        "do not become mandatory gates unless current repository authority requires them",
    ):
        assert invariant in routing

    assert "discard final acceptance for the previous head" not in routing
    assert "run the merge gate again" not in routing
