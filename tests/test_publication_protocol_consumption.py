from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pages.yml"
CATALOG = ROOT / "docs/publication-catalog.json"
PUBLICATION_GUIDE = ROOT / "docs/publication-catalog.md"
BUILD_GUIDE = ROOT / "docs/documentation-publication.md"
LEGACY_VALIDATOR = ROOT / "scripts/validate_publication_catalog.py"
SITE_PROTOCOL_REVISION = "3ae5d1e60c65e7a8ebf5f9af0436044484e42983"
SITE_PROTOCOL_PATH = ".site-publication-protocol/scripts/publication_contract.py"


def test_policy_uses_reviewed_site_publication_protocol() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert f"ref: {SITE_PROTOCOL_REVISION}" in workflow
    assert "path: .site-publication-protocol" in workflow
    assert "sparse-checkout: scripts/publication_contract.py" in workflow
    assert "sparse-checkout-cone-mode: false" in workflow
    assert "persist-credentials: false" in workflow
    assert (
        f".venv/bin/python -I {SITE_PROTOCOL_PATH} --source-root . "
        "--catalog docs/publication-catalog.json"
    ) in workflow
    assert "ref: site" not in workflow
    assert "ref: refs/heads/site" not in workflow
    assert "scripts/validate_publication_catalog.py" not in workflow
    assert not LEGACY_VALIDATOR.exists()


def test_publication_protocol_ownership_is_documented() -> None:
    publication_guide = PUBLICATION_GUIDE.read_text(encoding="utf-8")
    build_guide = BUILD_GUIDE.read_text(encoding="utf-8")

    for text in (publication_guide, build_guide):
        assert SITE_PROTOCOL_REVISION in text
        assert "Site-owned" in text
        assert "full" in text.lower() and "sha" in text.lower()
    assert "scripts/validate_publication_catalog.py" not in publication_guide
    assert "scripts/validate_publication_catalog.py" not in build_guide


def test_policy_catalog_keeps_policy_owned_v3_declarations() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))

    assert data["schema_version"] == 3
    assert data["glossary"] == {"source": "docs/glossary.yml"}
    documents = data["documents"]
    assert isinstance(documents, list) and documents
    homes = [item for item in documents if item.get("home") is True]
    assert len(homes) == 1
    assert homes[0]["id"] == "overview"

    identifiers = [item["id"] for item in documents]
    assert identifiers.count("policy-concepts") == 1
    getting_started = identifiers.index("getting-started")
    assert identifiers[getting_started + 1] == "policy-concepts"
    assert documents[getting_started + 1] == {
        "id": "policy-concepts",
        "source": "docs/policy-concepts.md",
        "optional": False,
        "home": False,
    }
