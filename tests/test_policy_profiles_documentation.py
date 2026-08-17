from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_MARKER = re.compile(r"<!-- PROFILE: ([a-z0-9][a-z0-9-]*) -->")
PROFILE_FILE_ENTRY = re.compile(r"^  - (policy/\S+\.md)$", re.MULTILINE)
MODULE_ENTRY = re.compile(r"^- `([^`]+)`$", re.MULTILINE)


def _profile_definitions() -> dict[str, list[str]]:
    definitions: dict[str, list[str]] = {}
    for path in sorted((ROOT / "profiles").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        definitions[path.stem] = PROFILE_FILE_ENTRY.findall(text)
    return definitions


def _catalog_sections(text: str) -> dict[str, str]:
    matches = list(PROFILE_MARKER.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def test_profile_catalog_matches_executable_profile_definitions() -> None:
    text = (ROOT / "docs" / "shared-policy" / "profiles.md").read_text(
        encoding="utf-8"
    )
    definitions = _profile_definitions()
    markers = PROFILE_MARKER.findall(text)

    assert len(markers) == len(set(markers)), "profile catalog markers must be unique"
    assert set(markers) == set(definitions), (
        "profile guide must catalog exactly the executable profiles in profiles/*.yml"
    )


def test_profile_catalog_lists_exact_included_modules() -> None:
    text = (ROOT / "docs" / "shared-policy" / "profiles.md").read_text(
        encoding="utf-8"
    )
    definitions = _profile_definitions()
    sections = _catalog_sections(text)

    for profile, policy_files in definitions.items():
        documented_modules = MODULE_ENTRY.findall(sections[profile])
        assert documented_modules == policy_files, (
            f"documented modules for {profile} drifted from profiles/{profile}.yml"
        )


def test_shared_policy_navigation_links_to_profile_catalog() -> None:
    text = (ROOT / "docs" / "shared-policy" / "index.md").read_text(
        encoding="utf-8"
    )
    assert "[Policy profiles](profiles.md)" in text


def test_profile_catalog_is_published() -> None:
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
