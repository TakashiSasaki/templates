#!/usr/bin/env python3
"""Validate Site-owned source declarations consumed by the Playground."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tomllib
from typing import Any


class _ElementCollector(HTMLParser):
    """Collect start-tag attributes without requiring a browser or renderer."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def load(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def _has_element(
    elements: list[tuple[str, dict[str, str | None]]],
    required: dict[str, str | None],
    present: tuple[str, ...] = (),
) -> bool:
    return any(
        all(attrs.get(name) == value for name, value in required.items())
        and all(name in attrs for name in present)
        for _, attrs in elements
    )


def validate(root: Path) -> list[str]:
    """Return errors for declarations owned by the Site consumer."""

    errors: list[str] = []
    json_documents: dict[str, dict[str, Any]] = {}
    for relative in (
        "docs/publication-catalog.json",
        "integration-source.json",
        "tests/fixtures/composition-playground-v1.json",
    ):
        try:
            json_documents[relative] = load(root, relative)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"Playground declaration {relative} is not valid JSON: {exc}")

    catalog = json_documents.get("docs/publication-catalog.json")
    documents = catalog.get("documents") if catalog else None
    expected_entry = {
        "id": "composition-playground",
        "source": "docs/composition-playground.md",
        "optional": False,
        "home": False,
    }
    if not isinstance(documents, list) or expected_entry not in documents:
        errors.append(
            "publication catalog must contain the exact composition-playground Site document entry"
        )

    template_path = root / "zensical.template.toml"
    try:
        # The renderer replaces this Site-owned placeholder before invoking
        # Zensical, so substitute a valid TOML value for source inspection.
        template_text = template_path.read_text(encoding="utf-8").replace(
            "__GENERATED_NAV__", "[]"
        )
        template = tomllib.loads(template_text)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"Playground declaration zensical.template.toml is not valid TOML: {exc}")
    else:
        project = template.get("project")
        if not isinstance(project, dict):
            errors.append("zensical.template.toml must declare a [project] table")
            project = {}
        for field, asset in (
            ("extra_css", "stylesheets/composition-playground.css"),
            ("extra_javascript", "javascripts/composition-playground.js"),
        ):
            values = project.get(field)
            if not isinstance(values, list) or asset not in values:
                errors.append(f"zensical.template.toml {field} must include {asset}")

    page_path = root / "docs/composition-playground.md"
    try:
        page_text = page_path.read_text(encoding="utf-8")
        parser = _ElementCollector()
        parser.feed(page_text)
        parser.close()
    except (OSError, ValueError) as exc:
        errors.append(f"Playground declaration docs/composition-playground.md is not valid HTML: {exc}")
    else:
        if not _has_element(
            parser.elements,
            {"id": "composition-playground", "data-provenance-url": "/build-provenance.json"},
        ):
            errors.append(
                "composition-playground page must declare the build provenance URL"
            )
        for attribute in (
            "data-playground-semantic-revision",
            "data-playground-provider-revision",
            "data-playground-projection-id",
        ):
            if not _has_element(parser.elements, {}, present=(attribute,)):
                errors.append(f"composition-playground page must declare {attribute}")
        if not _has_element(
            parser.elements,
            {
                "role": "status",
                "aria-live": "polite",
                "aria-atomic": "true",
            },
            present=("data-playground-validity",),
        ):
            errors.append(
                "composition-playground page must declare an accessible validity status"
            )

    javascript_path = root / "assets/javascripts/composition-playground.js"
    try:
        javascript = javascript_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(
            f"Playground declaration assets/javascripts/composition-playground.js is unavailable: {exc}"
        )
    else:
        for retired_token in ("SOURCE_REVISION_MISMATCH", "expectedRevision"):
            if retired_token in javascript:
                errors.append(
                    "composition-playground.js contains retired token "
                    f"{retired_token!r}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    try:
        errors = validate(Path(args.root).resolve())
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot validate Site declarations: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Site Composition Playground declarations: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
