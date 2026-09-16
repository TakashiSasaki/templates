from __future__ import annotations

import json
import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
import yaml
from markdown import markdown

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pages.yml"
CATALOG = ROOT / "docs/publication-catalog.json"
PUBLICATION_GUIDE = ROOT / "docs/publication-catalog.md"
BUILD_GUIDE = ROOT / "docs/documentation-publication.md"
LEGACY_VALIDATOR = ROOT / "scripts/validate_publication_catalog.py"
INTEGRATION_PROTOCOL_REVISION = "a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d"
INTEGRATION_PROTOCOL_PATH = ".integration-publication-protocol/integration/publication_contract.py"


def test_policy_uses_reviewed_integration_publication_protocol() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert f"ref: {INTEGRATION_PROTOCOL_REVISION}" in workflow
    assert "path: .integration-publication-protocol" in workflow
    assert "sparse-checkout: integration/publication_contract.py" in workflow
    assert "sparse-checkout-cone-mode: false" in workflow
    assert "persist-credentials: false" in workflow
    assert f"INTEGRATION_PUBLICATION_PROTOCOL: {INTEGRATION_PROTOCOL_PATH}" in workflow
    assert "scripts/run_policy_preflight.py --check docs" in workflow
    runner = (ROOT / "scripts/run_policy_preflight.py").read_text(encoding="utf-8")
    assert '"--catalog",\n        "docs/publication-catalog.json"' in runner
    assert "ref: site" not in workflow
    assert "ref: refs/heads/site" not in workflow
    assert "scripts/validate_publication_catalog.py" not in workflow
    assert not LEGACY_VALIDATOR.exists()


def test_publication_protocol_ownership_is_documented() -> None:
    publication_guide = PUBLICATION_GUIDE.read_text(encoding="utf-8")
    build_guide = BUILD_GUIDE.read_text(encoding="utf-8")

    for text in (publication_guide, build_guide):
        assert INTEGRATION_PROTOCOL_REVISION in text
        assert "Integration-owned" in text
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


MAINTAINER_SOURCES = {
    "contributing": "CONTRIBUTING.md",
    "maintainer-workflow": "docs/policy-maintainer-workflow.md",
    "adr-review-authority-and-github-runtime-boundary": (
        "docs/adr/0008-review-authority-and-github-runtime-boundary.md"
    ),
    "adr-review-result-representation-boundary": (
        "docs/adr/0009-review-result-representation-boundary.md"
    ),
}


def test_maintainer_identities_are_complete_existing_and_published() -> None:
    guide = PUBLICATION_GUIDE.read_text(encoding="utf-8")
    section = guide.split("<!-- deferred-maintainer-publications -->", 1)[1].split(
        "<!-- /deferred-maintainer-publications -->", 1
    )[0]
    rows = re.findall(r"^\| `([^`]+)` \| `([^`]+)` \|", section, re.MULTILINE)
    # Exact correspondence catches omission, rename, duplicate, and source drift.
    assert len(rows) == len(MAINTAINER_SOURCES)
    assert dict(rows) == MAINTAINER_SOURCES
    assert len({source for _, source in rows}) == len(rows)
    active = json.loads(CATALOG.read_text(encoding="utf-8"))["documents"]
    for document_id, source in rows:
        assert (ROOT / source).is_file(), source
        assert any(item["id"] == document_id and item["source"] == source for item in active)


def test_contribution_guide_describes_active_policy_publication() -> None:
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "active Policy publication entries" in contributing
    assert "Site owns their staged-to-active reader promotion" in contributing
    assert "prepared for later publication" not in contributing


def test_published_maintainer_sources_have_post_cutover_discovery_links() -> None:
    index = (ROOT / "docs/index.md").read_text(encoding="utf-8")
    adr_index = (ROOT / "docs/adr/index.md").read_text(encoding="utf-8")

    # CONTRIBUTING lives outside the local MkDocs docs root, so repository
    # discovery remains an explicit source link while Site owns its reader route.
    assert "https://github.com/TakashiSasaki/templates/blob/policy/CONTRIBUTING.md" in index
    assert "(policy-maintainer-workflow.md)" in index
    assert "repository source" not in index.lower()

    for document_id, source in MAINTAINER_SOURCES.items():
        if document_id.startswith("adr-"):
            relative = Path(source).name
            repository_link = (
                "https://github.com/TakashiSasaki/templates/blob/policy/" + source
            )
            assert f"({relative})" in adr_index
            assert repository_link not in adr_index
            assert source.removeprefix("docs/") in (ROOT / "mkdocs.yml").read_text(
                encoding="utf-8"
            )

    assert "reader publication is deferred" not in adr_index


class _RenderedLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.destinations: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.destinations.extend(value for name, value in attrs if name == "href" and value)


def _markdown_link_destinations(text: str) -> list[str]:
    # Use the already-reviewed documentation renderer, including code fences,
    # rather than maintaining a second partial Markdown grammar in a regex.
    links = _RenderedLinks()
    configured = yaml.safe_load((ROOT / "mkdocs.yml").read_text())["markdown_extensions"]
    extensions = []
    configs = {}
    for entry in configured:
        if isinstance(entry, str):
            extensions.append(entry)
        else:
            extensions.extend(entry)
            configs.update(entry)
    links.feed(markdown(text, extensions=extensions, extension_configs=configs))
    links.close()
    return links.destinations


def _relative_markdown_target(source: str, href: str) -> str | None:
    # Browser URL parsing removes boundary ASCII C0 controls and spaces.
    # Strip before percent decoding: an encoded space belongs to the path.
    url = urlsplit(href.strip("".join(chr(code) for code in range(0x21))))
    path = unquote(url.path)
    if url.scheme or url.netloc or path.startswith("/") or not path.endswith(".md"):
        return None
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), path))


def test_published_maintainer_relative_links_stay_inside_publication_catalog() -> None:
    published = {
        item["source"] for item in json.loads(CATALOG.read_text(encoding="utf-8"))["documents"]
    }
    for source in MAINTAINER_SOURCES.values():
        text = (ROOT / source).read_text(encoding="utf-8")
        for href in _markdown_link_destinations(text):
            target = _relative_markdown_target(source, href)
            if target is None:
                continue
            assert target in published, (
                f"{source}: relative reader link {href!r} targets unpublished {target}; "
                "use an explicit repository-source link instead"
            )


@pytest.mark.parametrize("text", [
    '[guide](staged-ci.md)',
    '[guide](staged-ci.md "title")',
    "[guide](staged-ci.md 'title')",
    '[guide](<staged-ci.md> "title")',
    '[guide][g]\n\n[g]: staged-ci.md',
    '[guide][g]\n\n[g]: staged-ci.md "title"',
    '[guide][]\n\n[guide]: staged-ci.md',
    '[guide]\n\n[guide]: <staged-ci.md>',
    '[guide][g]\n\n[g]:\n    staged-ci.md',
    '!!! note\n\n    [guide][g]\n\n    [g]: staged-ci.md',
])
def test_catalog_guard_extracts_rendered_markdown_link_forms(text: str) -> None:
    assert _markdown_link_destinations(text) == ["staged-ci.md"]


@pytest.mark.parametrize("text", [
    '`[example](staged-ci.md)`',
    '```markdown\n[example](staged-ci.md)\n```',
    '[unused]: staged-ci.md',
])
def test_catalog_guard_ignores_non_links(text: str) -> None:
    assert _markdown_link_destinations(text) == []


@pytest.mark.parametrize("href, expected", [
    ("unpublished.md?view=1", "docs/unpublished.md"),
    ("unpublished.md?view=1#section", "docs/unpublished.md"),
    ("../unpublished.md#section", "unpublished.md"),
    ("unpublished%2Emd", "docs/unpublished.md"),
    ("https://example.org/unpublished.md?view=1", None),
    ("//example.org/unpublished.md", None),
    ("mailto:someone@example.org", None),
    ("#section", None),
    ("/unpublished.md", None),
])
def test_catalog_guard_classifies_url_paths(href: str, expected: str | None) -> None:
    assert _relative_markdown_target("docs/guide.md", href) == expected


@pytest.mark.parametrize("boundary", [chr(code) for code in range(0x21)])
def test_catalog_guard_normalizes_url_boundary_controls(boundary: str) -> None:
    assert _relative_markdown_target(
        "docs/guide.md", boundary + "unpublished.md" + boundary
    ) == "docs/unpublished.md"


def test_catalog_guard_classifies_entity_space_but_preserves_encoded_path_space() -> None:
    href, = _markdown_link_destinations("[guide](unpublished.md&#32;)")
    assert href == "unpublished.md "
    assert _relative_markdown_target("docs/guide.md", href) == "docs/unpublished.md"
    assert _relative_markdown_target("docs/guide.md", "unpublished.md%20") is None
    assert _relative_markdown_target("docs/guide.md", "unpublished.md\u00a0") is None
