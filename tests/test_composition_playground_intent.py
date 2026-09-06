from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_composition_playground_intent import build_intent_projection, decode_transition  # noqa: E402


def _recipe(projection: dict, recipe_id: str) -> dict:
    return next(item for item in projection["recipes"] if item["id"] == recipe_id)


def _transition(projection: dict, recipe: dict, case_index: int, component_id: str) -> dict:
    position = recipe["optional_components"].index(component_id)
    return decode_transition(projection, recipe["cases"][case_index][position])


def test_webmcp_exclusion_is_explicit_and_not_an_enumerated_third_axis() -> None:
    projection = build_intent_projection()
    website = _recipe(projection, "website")
    assert projection["strategy"] == "indexed-single-explicit-exclusion-transitions"
    assert "capability.webmcp" in website["optional_components"]
    assert website["case_count"] == 1 << len(website["optional_components"])
    assert len(website["cases"]) == website["case_count"]
    assert all(len(row) == len(website["optional_components"]) for row in website["cases"])
    default_exclusion = _transition(projection, website, 0, "capability.webmcp")
    assert default_exclusion["valid"] is True
    assert default_exclusion["error"] is None


def test_include_and_exclude_overlap_fails_closed() -> None:
    projection = build_intent_projection()
    website = _recipe(projection, "website")
    position = website["optional_components"].index("capability.webmcp")
    include_case = 1 << position
    transition = _transition(projection, website, include_case, "capability.webmcp")
    assert transition["valid"] is False
    assert transition["error"]["code"] == "SELECTION_OVERLAP"
    assert transition["outcome_id"] is None


def test_webmcp_exclusion_is_available_for_webapp_without_selecting_mcp() -> None:
    projection = build_intent_projection()
    webapp = _recipe(projection, "webapp")
    transition = _transition(projection, webapp, 0, "capability.webmcp")
    assert transition["valid"] is True


def test_projection_is_compact_enough_for_plain_json_publication() -> None:
    import json

    projection = build_intent_projection()
    rendered = (json.dumps(projection, indent=2) + "\n").encode()
    assert len(rendered) < 524_288
