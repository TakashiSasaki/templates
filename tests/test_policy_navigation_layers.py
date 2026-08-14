import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_TARGET = re.compile(r"\]\(([^)#]+)(?:#[^)]+)?\)")


def test_root_navigation_separates_policy_layers() -> None:
    text = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")

    assert text.startswith("# agent-policy navigation\n")
    headings = [
        "## Orientation",
        "## Provider and toolchain",
        "## Shared policy corpus",
        "## Consumer application",
    ]
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "[Overview](overview.md)" in text
    assert "[Provider and toolchain documentation](provider/index.md)" in text
    assert "[Shared policy corpus](shared-policy/index.md)" in text
    assert "[Applying policy to a consumer repository](consumer/index.md)" in text


def test_layer_navigation_entries_are_published() -> None:
    text = (ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8")

    expected_entries = [
        (
            '"id": "provider-navigation"',
            '"source": "docs/provider/index.md"',
        ),
        (
            '"id": "shared-policy-navigation"',
            '"source": "docs/shared-policy/index.md"',
        ),
        (
            '"id": "consumer-policy-navigation"',
            '"source": "docs/consumer/index.md"',
        ),
    ]
    for document_id, source in expected_entries:
        id_position = text.index(document_id)
        source_position = text.index(source, id_position)
        next_entry = text.find('"id":', id_position + len(document_id))
        assert source_position > id_position
        assert next_entry == -1 or source_position < next_entry
        entry_end = next_entry if next_entry != -1 else len(text)
        entry = text[id_position:entry_end]
        assert '"optional": false' in entry
        assert '"home": false' in entry


def test_all_layer_navigation_links_target_existing_files() -> None:
    layer_files = [
        ROOT / "docs" / "provider" / "index.md",
        ROOT / "docs" / "shared-policy" / "index.md",
        ROOT / "docs" / "consumer" / "index.md",
    ]

    for layer_file in layer_files:
        text = layer_file.read_text(encoding="utf-8")
        targets = LINK_TARGET.findall(text)
        assert targets
        for target in targets:
            target_path = layer_file.parent / target
            assert target_path.is_file(), f"Broken link in {layer_file}: {target}"


def test_published_layer_navigation_links_remain_inside_catalog() -> None:
    catalog = json.loads(
        (ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8")
    )
    published_sources = {ROOT / document["source"] for document in catalog["documents"]}
    layer_files = [
        ROOT / "docs" / "provider" / "index.md",
        ROOT / "docs" / "shared-policy" / "index.md",
        ROOT / "docs" / "consumer" / "index.md",
    ]

    for layer_file in layer_files:
        for target in LINK_TARGET.findall(layer_file.read_text(encoding="utf-8")):
            target_path = (layer_file.parent / target).resolve()
            assert target_path in published_sources, (
                f"Published layer navigation links to uncataloged document: "
                f"{layer_file} -> {target}"
            )


def test_provider_environment_link_targets_a_document() -> None:
    text = (ROOT / "docs" / "provider" / "index.md").read_text(encoding="utf-8")

    assert "[Google AI Studio Build mode](../agent-environments/google-ai-studio.md)" in text
    assert "(../agent-environments/)" not in text
