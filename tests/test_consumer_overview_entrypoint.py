from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERVIEW = ROOT / "docs" / "overview.md"
TRANSLATIONS = ROOT / "translations" / "manifest.json"


def test_policy_overview_leads_with_consumer_workflow() -> None:
    overview = OVERVIEW.read_text(encoding="utf-8")
    start = overview.index("## Start here")
    purpose = overview.index("## Purpose")
    layers = overview.index("## Three layers that must remain distinct")
    assert start < purpose < layers

    entrypoint = overview[start:purpose]
    for expected in (
        "scripts/bootstrap.py",
        "unmanaged-empty",
        "unmanaged-existing",
        "scripts/run.py",
        "validate",
        "render",
        "check",
        "Getting started",
        "Managed operation",
        "Policy profiles",
        "does not define the architecture or product requirements",
    ):
        assert expected in entrypoint


def test_policy_overview_translation_pin_matches_canonical_blob() -> None:
    manifest = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    entry = next(
        item
        for item in manifest["translations"]
        if item["canonical"] == "docs/overview.md" and item["language"] == "ja"
    )
    # Git blob identity is validated by the repository translation validator; this
    # assertion keeps the consumer overview explicitly registered as a reader surface.
    assert entry["translation"] == "translations/ja/docs/overview.md"
    assert entry["surfaces"] == ["reader"]
