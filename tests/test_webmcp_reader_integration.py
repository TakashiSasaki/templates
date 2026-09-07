from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_webmcp_reader_page_is_site_owned_and_composition_delegating() -> None:
    page = (ROOT / "docs" / "webmcp.md").read_text(encoding="utf-8")
    required = [
        "What is WebMCP?",
        "Should I adopt it?",
        "WebMCP vs MCP",
        "WebMCP vs MCP Apps",
        "ordinary Web UI",
        "explicit non-adoption",
        "Imperative",
        "Declarative",
        "Composition",
    ]
    for text in required:
        assert text in page
    assert "semantic authority" in page.lower()


def test_site_publication_catalog_registers_reader_page() -> None:
    catalog = json.loads((ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8"))
    document = next((item for item in catalog["documents"] if item["id"] == "webmcp-guide"), None)
    assert document == {
        "id": "webmcp-guide",
        "source": "docs/webmcp.md",
        "optional": False,
        "home": False,
    }


def test_site_manifest_maps_site_and_provider_webmcp_documents() -> None:
    manifest = json.loads((ROOT / "site-manifest.json").read_text(encoding="utf-8"))
    leaves: list[dict] = []
    pending = list(manifest["navigation"])
    while pending:
        node = pending.pop()
        if "children" in node:
            pending.extend(node["children"])
        else:
            leaves.append(node)
    keys = {(item["publication"], item["document"]) for item in leaves}
    assert ("site", "webmcp-guide") in keys
    for document in ("webmcp-capability", "webmcp-tool-design", "webmcp-security", "webmcp-testing"):
        assert ("composition", document) in keys


def test_capabilities_index_links_webmcp_reader_page() -> None:
    page = (ROOT / "docs" / "capabilities.md").read_text(encoding="utf-8")
    assert "WebMCP" in page
    assert "webmcp/" in page
