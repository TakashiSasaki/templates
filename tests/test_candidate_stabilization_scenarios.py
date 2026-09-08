from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "candidate-stabilization" / "cases.json"


def test_candidate_stabilization_scenarios_remain_cross_authority_coherent() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    assert len(cases) >= 5
    names: set[str] = set()

    for case in cases:
        name = case["name"]
        assert name not in names
        names.add(name)
        for relative_path, fragments in case["required"].items():
            text = (ROOT / relative_path).read_text(encoding="utf-8").lower()
            for fragment in fragments:
                assert fragment.lower() in text, (
                    f"{name}: missing {fragment!r} in {relative_path}"
                )
