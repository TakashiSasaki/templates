from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "components/capability.webmcp/files/scripts"))

from composer_core_impl import load_source_state, normalize_intent, resolve_configuration  # noqa: E402
from webmcp_evidence_targets import expected_targets  # noqa: E402


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def resolved(path: str) -> tuple[dict, list[str]]:
    raw = load(path)
    config = {"schema_version": 1, **normalize_intent(raw)}
    return resolve_configuration(load_source_state(), config)


def test_webmcp_is_independent_optional_capability() -> None:
    component = load("components/capability.webmcp/component.json")
    assert component["requires"] == ["lifecycle.implementation-evidence"]
    assert component["conflicts"] == []
    for recipe_id in ("website", "webapp"):
        recipe = load(f"recipes/{recipe_id}.json")
        assert recipe["default_components"] == []
        assert "capability.webmcp" in recipe["optional_components"]
    forbidden = {"capability.mcp", "capability.mcp-apps", "capability.runtime", "capability.web-interface"}
    assert forbidden.isdisjoint(component["requires"])


def test_webmcp_contracts_have_no_second_adoption_authority() -> None:
    for stem in ("interface", "tools"):
        document = load(f"components/capability.webmcp/files/contracts/webmcp-{stem}.json")
        serialized = json.dumps(document).lower()
        assert '"enabled"' not in serialized
        schema = load(f"components/capability.webmcp/files/schemas/webmcp-{stem}.schema.json")
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(document)


def test_examples_resolve_with_expected_intent() -> None:
    _, website_default = resolved("examples/webmcp/website-without-webmcp.json")
    _, website_webmcp = resolved("examples/webmcp/website-with-webmcp.json")
    _, webapp_webmcp = resolved("examples/webmcp/webapp-with-webmcp.json")
    _, webapp_both = resolved("examples/webmcp/webapp-with-webmcp-and-mcp.json")
    normalized_exclusion, website_excluded = resolved("examples/webmcp/explicit-webmcp-exclusion.json")
    assert "capability.webmcp" not in website_default
    assert "capability.webmcp" in website_webmcp
    assert "capability.webmcp" in webapp_webmcp
    assert {"capability.webmcp", "capability.mcp"}.issubset(webapp_both)
    assert "capability.webmcp" not in website_excluded
    assert normalized_exclusion["components"]["exclude"] == ["capability.webmcp"]


def test_tool_evidence_targets_use_stable_contract_ids() -> None:
    assert expected_targets(ROOT / "components/capability.webmcp/files") == ()
