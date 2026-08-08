from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs/adr/0006-copyable-artifact-policy-adoption.md"
CATALOG = ROOT / "docs/publication-catalog.json"
MKDOCS = ROOT / "mkdocs.yml"


def test_copyable_artifact_adoption_is_opt_in() -> None:
    text = ADR.read_text(encoding="utf-8")

    assert "Copyable template distributions are **not pre-enrolled**" in text
    assert "must not include `.agent-policy.yml`, `.agent-policy.lock`" in text
    assert "explicitly adopt the shared policy toolchain" in text
    assert "separate repository-maintenance decision" in text
    assert "does not require an agent-instruction entry point" in text


def test_copyable_artifact_adoption_preserves_artifact_authority() -> None:
    text = ADR.read_text(encoding="utf-8")

    assert "Artifact-level instructions remain owned by the artifact contract" in text
    assert "a Skill template may retain consumer-facing `AGENTS.md`" in text
    assert "a Web application template is not required to add `AGENTS.md`" in text
    assert "source-maintainer `.agent-policy.yml`" in text
    assert "do not flow into `template/` by inheritance" in text


def test_copyable_artifact_adoption_adr_is_published() -> None:
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
