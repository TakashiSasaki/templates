from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs/adr/0006-copyable-artifact-policy-adoption.md"
CATALOG = ROOT / "docs/publication-catalog.json"
MKDOCS = ROOT / "mkdocs.yml"


def test_composition_materialized_artifact_adoption_is_opt_in() -> None:
    text = ADR.read_text(encoding="utf-8")

    assert "Composition-materialized artifacts are **not pre-enrolled**" in text
    assert "must not add `.agent-policy.yml`, `.agent-policy.lock`" in text
    assert "explicitly adopt the shared Policy toolchain" in text
    assert "separate repository-maintenance decision" in text
    assert "Composer must not invoke `agent-policy`" in text


def test_artifact_adoption_preserves_authority_and_handoff() -> None:
    text = ADR.read_text(encoding="utf-8")

    assert "Artifact-level instructions remain governed by the artifact ownership contract" in text
    assert "consumer-facing `AGENTS.md` as a Composition `seed`" in text
    assert "a later explicit Policy adoption may inspect and migrate" in text
    assert "a Web application artifact is not required to add `AGENTS.md`" in text
    assert "does not interpret `.template-composition/**` as Policy state" in text
    assert "Reverse ownership transfer" in text
    assert "fail-closed" in text


def test_artifact_adoption_adr_is_published() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    matches = [
        document
        for document in catalog["documents"]
        if document["id"] == "adr-copyable-artifact-policy-adoption"
    ]

    assert matches == [
        {
            "id": "adr-copyable-artifact-policy-adoption",
            "source": "docs/adr/0006-copyable-artifact-policy-adoption.md",
            "optional": False,
            "home": False,
        }
    ]
    assert "adr/0006-copyable-artifact-policy-adoption.md" in MKDOCS.read_text(
        encoding="utf-8"
    )
