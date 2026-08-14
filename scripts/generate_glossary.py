#!/usr/bin/env python3
"""Generate the integrated machine-readable glossary from locked publications."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
    publications_raw = _mapping(publication_values, "publication")
    revisions = _mapping(revision_values, "revision")
    publications = {name: Path(path) for name, path in publications_raw.items()}
    value = integrate_glossaries(publications, revisions, repository)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--revision", action="append", default=[], metavar="NAME=SHA")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        generate(
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
