#!/usr/bin/env python3
"""Generate integrated glossary data and its static human-readable viewer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_glossary_viewer import (
    GlossaryViewerError,
    generate as generate_viewer,
)
from scripts.glossary import GlossaryError, integrate_glossaries


def _mapping(values: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise GlossaryError(f"{label} values must use name=value syntax")
        name, item = value.split("=", 1)
        if not name or not item:
            raise GlossaryError(f"{label} values must use non-empty name=value syntax")
        if name in result:
            raise GlossaryError(f"duplicate {label} provider: {name}")
        result[name] = item
    return result


def generate(
    publication_values: list[str],
    revision_values: list[str],
    repository: str,
    output: Path,
) -> None:
    """Write only the canonical integrated JSON model.

    Tests and other Python callers can use this semantic layer without creating
    presentation output. The CLI calls ``generate_publication`` below so the
    Pages workflow receives both the JSON read model and its static viewer.
    """
    publications_raw = _mapping(publication_values, "publication")
    revisions = _mapping(revision_values, "revision")
    publications = {name: Path(path) for name, path in publications_raw.items()}
    try:
        value = integrate_glossaries(publications, revisions, repository)
    except OSError as exc:
        raise GlossaryError(f"unable to resolve glossary publication input: {exc}") from exc
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as exc:
        raise GlossaryError(f"unable to write integrated glossary {output}: {exc}") from exc


def generate_publication(
    publication_values: list[str],
    revision_values: list[str],
    repository: str,
    output: Path,
) -> Path:
    """Write a ``.json`` model plus a sibling ``.html`` human viewer."""
    if output.suffix.lower() != ".json":
        raise GlossaryError("integrated glossary output must use a .json suffix")
    viewer_output = output.with_suffix(".html")
    if viewer_output == output:
        raise GlossaryError("glossary viewer output must differ from JSON output")
    generate(publication_values, revision_values, repository, output)
    try:
        generate_viewer(output, viewer_output)
    except GlossaryViewerError as exc:
        raise GlossaryError(f"unable to generate glossary viewer: {exc}") from exc
    return viewer_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--revision", action="append", default=[], metavar="NAME=SHA")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        generate_publication(
            args.publication,
            args.revision,
            args.repository,
            args.output,
        )
    except GlossaryError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
