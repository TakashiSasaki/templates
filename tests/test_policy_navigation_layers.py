import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_TARGET = re.compile(r"\]\(([^)#]+)(?:#[^)]+)?\)")
PROFILE_MARKER = re.compile(r"<!-- PROFILE: ([a-z0-9][a-z0-9-]*) -->")
PROFILE_FILE_ENTRY = re.compile(r"^  - (policy/\S+\.md)$", re.MULTILINE)
MODULE_ENTRY = re.compile(r"^- `([^`]+)`$", re.MULTILINE)


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


def test_policy_profile_catalog_matches_profile_definitions() -> None:
    guide = (ROOT / "docs" / "shared-policy" / "profiles.md").read_text(encoding="utf-8")
    markers = PROFILE_MARKER.findall(guide)
    profile_files = sorted((ROOT / "profiles").glob("*.yml"))

    assert len(markers) == len(set(markers))
    assert set(markers) == {path.stem for path in profile_files}

    matches = list(PROFILE_MARKER.finditer(guide))
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(guide)
        sections[match.group(1)] = guide[match.end() : end]

    for profile_file in profile_files:
        expected = PROFILE_FILE_ENTRY.findall(profile_file.read_text(encoding="utf-8"))
        documented = MODULE_ENTRY.findall(sections[profile_file.stem])
        assert documented == expected


def test_policy_profile_catalog_is_published_and_linked() -> None:
    catalog = json.loads(
        (ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8")
    )
    documents = {document["id"]: document for document in catalog["documents"]}
    assert documents["policy-profiles"] == {
        "id": "policy-profiles",
        "source": "docs/shared-policy/profiles.md",
        "optional": False,
        "home": False,
    }

    navigation = (ROOT / "docs" / "shared-policy" / "index.md").read_text(encoding="utf-8")
    assert "[Policy profiles](profiles.md)" in navigation


def test_policy_profile_catalog_is_in_mkdocs_design_navigation() -> None:
    navigation = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    configuration = "      - 設定ファイル: configuration.md"
    profiles = "      - Policy profiles: shared-policy/profiles.md"
    authoring = "      - 規約の作成: policy-authoring.md"

    assert profiles in navigation
    assert (
        navigation.index(configuration)
        < navigation.index(profiles)
        < navigation.index(authoring)
    )
