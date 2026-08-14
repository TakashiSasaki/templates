from pathlib import Path

from scripts.validate_publication_catalog import validate_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_root_navigation_separates_policy_layers() -> None:
    text = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")

    assert text.startswith("# agent-policy navigation\n")
    headings = [
        "## Provider and toolchain",
        "## Shared policy corpus",
        "## Consumer application",
    ]
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "[Provider and toolchain documentation](provider/index.md)" in text
    assert "[Shared policy corpus](shared-policy/index.md)" in text
    assert "[Applying policy to a consumer repository](consumer/index.md)" in text


def test_layer_navigation_entries_are_published() -> None:
    documents, _assets = validate_catalog(
        ROOT / "docs" / "publication-catalog.json",
        ROOT,
    )
    by_id = {document.document_id: document for document in documents}

    expected = {
        "provider-navigation": "docs/provider/index.md",
        "shared-policy-navigation": "docs/shared-policy/index.md",
        "consumer-policy-navigation": "docs/consumer/index.md",
    }
    for document_id, source in expected.items():
        document = by_id[document_id]
        assert document.source.as_posix() == source
        assert document.optional is False
        assert document.home is False


def test_provider_environment_link_targets_a_document() -> None:
    text = (ROOT / "docs" / "provider" / "index.md").read_text(encoding="utf-8")

    assert "[Google AI Studio Build mode](../agent-environments/google-ai-studio.md)" in text
    assert "(../agent-environments/)" not in text
