from __future__ import annotations

from pathlib import Path

from scripts.glossary import load_glossary

ROOT = Path(__file__).resolve().parents[1]


def test_site_glossary_contains_reviewed_first_expansion_terms() -> None:
    terms = load_glossary(ROOT / "docs/glossary.yml")
    by_id = {term["id"]: term for term in terms}

    integrated = by_id["templates-integrated-publication"]
    assert integrated["localized_labels"]["ja"]["term"] == "統合公開"
    assert "templates-provider-branch" in integrated["related_terms"]
    assert "templates-publication-catalog" in integrated["related_terms"]
    assert "templates-publication-source-lock" in integrated["related_terms"]

    source_lock = by_id["templates-publication-source-lock"]
    assert source_lock["localized_labels"]["ja"]["term"] == "公開ソースロック"
    assert "full 40-character commit SHA" in source_lock["definition"]
    assert "templates-integrated-publication" in source_lock["related_terms"]
