#!/usr/bin/env python3
"""Reject generated references to the retired /templates/ publication base."""

from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath


FORBIDDEN_TEXT = (
    "https://takashisasaki.github.io/templates/",
    "https://templates.moukaeritai.work/templates/",
)
ROOT_ATTRIBUTE = re.compile(r'''(?:href|src|action)=["']/templates(?:/|["'])''')
STRUCTURED_ATTRIBUTE_CANDIDATE = re.compile(
    r"""
    \b(?:href|src|action|content)\s*=\s*
    (?:"|')?
    (?:
        https://takashisasaki\.github\.io/templates/
        |https://templates\.moukaeritai\.work/templates/
        |/templates(?:/|(?=["'\s>]))
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


class PublicURLBoundaryError(RuntimeError):
    """Raised when the generated tree cannot be checked."""


class URLAttributeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def collect(self, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src", "action", "content"} and value:
                self.targets.append(value)

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.collect(attrs)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.collect(attrs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    return parser.parse_args()


def retired_target(value: str) -> bool:
    return (
        any(value.startswith(prefix) for prefix in FORBIDDEN_TEXT)
        or value == "/templates"
        or value.startswith("/templates/")
    )


def uses_structured_attribute_check(relative: PurePosixPath) -> bool:
    if relative.suffix.lower() != ".html":
        return False
    browser_source_view = (
        len(relative.parts) == 4
        and relative.parts[0] == "files"
        and relative.parts[2] == "content"
    )
    guided_view = bool(relative.parts) and (
        relative.parts[0] == "guided"
        or (len(relative.parts) > 1 and relative.parts[1] == "guided")
    )
    return browser_source_view or guided_view


def structured_retired_target_present(text: str) -> bool:
    """Parse HTML only when decoded source could contain a retired URL attribute."""
    # HTMLParser decodes character references in attribute values.  Decode only for
    # this conservative prefilter so entity-encoded retired values cannot bypass the
    # structural check.  False positives are harmless: they fall back to the exact
    # parser used by the previous workflow implementation.
    candidate_text = html.unescape(text)
    if STRUCTURED_ATTRIBUTE_CANDIDATE.search(candidate_text) is None:
        return False

    parser = URLAttributeParser()
    parser.feed(text)
    parser.close()
    return any(retired_target(target) for target in parser.targets)


def find_retired_public_urls(site_root: Path) -> list[Path]:
    try:
        root = site_root.resolve(strict=True)
    except OSError as exc:
        raise PublicURLBoundaryError(
            f"unable to resolve generated site root {site_root}: {exc}"
        ) from exc
    if not root.is_dir():
        raise PublicURLBoundaryError(f"generated site root is not a directory: {root}")

    failures: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".xml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise PublicURLBoundaryError(
                f"unable to read generated document {path}: {exc}"
            ) from exc

        relative = PurePosixPath(path.relative_to(root).as_posix())
        if uses_structured_attribute_check(relative):
            failed = structured_retired_target_present(text)
        else:
            failed = any(value in text for value in FORBIDDEN_TEXT) or bool(
                ROOT_ATTRIBUTE.search(text)
            )
        if failed:
            failures.append(relative)

    return failures


def main() -> int:
    args = parse_args()
    try:
        failures = find_retired_public_urls(args.site_root)
    except PublicURLBoundaryError as exc:
        print(f"Public URL boundary check failed: {exc}", file=sys.stderr)
        return 1

    if failures:
        print(
            "generated site retains the retired /templates/ publication base: "
            + ", ".join(path.as_posix() for path in failures),
            file=sys.stderr,
        )
        return 1

    print("Generated public URL boundary is clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
