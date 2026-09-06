from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_composition_playground_intent import build_intent_projection  # noqa: E402


def _recipe(projection: dict, recipe_id: str) -> dict:
    return next(item for item in projection["recipes"] if item["id"] == recipe_id)


def _transition(recipe: dict, case_index: int, component_id: str) -> dict:
    case = recipe["cases"][case_index]
    return next(item for item in case["exclude"] if item["component"] == component_id)


def test_webmcp_exclusion_is_explicit_and_not_an_enumerated_third_axis() -> None:
    projection = build_intent_projection()
    website = _recipe(projection, "website")
    assert "capability.webmcp" in website["optional_components"]
    assert website["case_count"] == 1 << len(website["optional_components"])
    default_exclusion = _transition(website, 0, "capability.webmcp")
    assert default_exclusion["valid"] is True
    assert default_exclusion["error"] is None


def test_include_and_exclude_overlap_fails_closed() -> None:
    projection = build_intent_projection()
    website = _recipe(projection, "website")
    position = website["optional_components"].index("capability.webmcp")
    include_case = 1 << position
    transition = _transition(website, include_case, "capability.webmcp")
    assert transition["valid"] is False
    assert transition["error"]["code"] == "SELECTION_OVERLAP"
    assert transition["outcome_id"] is None


def test_webmcp_exclusion_is_available_for_webapp_without_selecting_mcp() -> None:
    projection = build_intent_projection()
    webapp = _recipe(projection, "webapp")
    transition = _transition(webapp, 0, "capability.webmcp")
    assert transition["valid"] is True
