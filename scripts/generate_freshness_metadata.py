#!/usr/bin/env python3
"""Generate deployment identity and annotate cache-eligible HTML with its Site revision."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


SHA_PATTERN = re.compile(r"\A[0-9a-f]{40}\Z")
DEPLOYMENT_TIMESTAMP_PATTERN = re.compile(
    r"\A\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} JST\Z"
)
DEPLOYMENT_NOTICE_PATTERN = re.compile(
    r"Deployment time:\s*(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} JST)"
)
PREVIEW_NOTICE = "Preview build (not deployed)"
HEAD_CLOSE_PATTERN = re.compile(r"</head\s*>", re.IGNORECASE)
SITE_REVISION_META_NAME = "templates-site-revision"
EXPECTED_PUBLICATIONS = ("skill", "policy", "webapp")


class FreshnessMetadataError(RuntimeError):
    """Raised when deployment freshness metadata is invalid or ambiguous."""


class MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metas: list[dict[str, str | None]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() == "meta":
            self.metas.append({name.casefold(): value for name, value in attrs})

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)


class TextParser(HTMLParser):
    SKIPPED_ELEMENTS = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipped_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.casefold() in self.SKIPPED_ELEMENTS:
            self.skipped_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self.SKIPPED_ELEMENTS and self.skipped_depth:
            self.skipped_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skipped_depth:
            return
        if data.strip():
            self.parts.append(data.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--site-revision", required=True)
    parser.add_argument("--deployment-timestamp", default=None)
    parser.add_argument(
        "--publication",
        action="append",
        default=[],
        metavar="NAME=REVISION",
        help="Resolved provider publication revision; repeat for skill, policy, and webapp.",
    )
    return parser.parse_args()


def validate_revision(value: str, label: str) -> str:
    if SHA_PATTERN.fullmatch(value) is None:
        raise FreshnessMetadataError(
            f"{label} revision must be a lowercase full 40-character Git SHA"
        )
    return value


def validate_deployment_timestamp(value: str) -> str | None:
    if not value:
        return None
    if DEPLOYMENT_TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise FreshnessMetadataError(
            "deployment timestamp must use YYYY-MM-DD HH:MM:SS JST"
        )
    return value


def deployment_timestamp_from_index(site_root: Path) -> str:
    index = site_root / "index.html"
    try:
        source = index.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FreshnessMetadataError(
            f"unable to read rendered deployment notice from {index}: {exc}"
        ) from exc

    parser = TextParser()
    parser.feed(source)
    parser.close()
    visible_text = " ".join(parser.parts)
    timestamps = [
        match.group("timestamp")
        for match in DEPLOYMENT_NOTICE_PATTERN.finditer(visible_text)
    ]
    preview = PREVIEW_NOTICE in visible_text
    if len(timestamps) > 1 or (timestamps and preview):
        raise FreshnessMetadataError(
            f"{index}: rendered deployment notice is ambiguous"
        )
    if timestamps:
        validate_deployment_timestamp(timestamps[0])
        return timestamps[0]
    if preview:
        return ""
    raise FreshnessMetadataError(
        f"{index}: rendered deployment notice is missing"
    )


def validate_publications(publications: dict[str, str]) -> dict[str, str]:
    unexpected = sorted(set(publications) - set(EXPECTED_PUBLICATIONS))
    if unexpected:
        raise FreshnessMetadataError(
            "unsupported publication(s): " + ", ".join(unexpected)
        )
    missing = [name for name in EXPECTED_PUBLICATIONS if name not in publications]
    if missing:
        raise FreshnessMetadataError(
            "missing publication revision(s): " + ", ".join(missing)
        )
    return {
        name: validate_revision(publications[name], name)
        for name in EXPECTED_PUBLICATIONS
    }


def parse_publications(values: list[str]) -> dict[str, str]:
    publications: dict[str, str] = {}
    for value in values:
        name, separator, revision = value.partition("=")
        if not separator or not name or not revision:
            raise FreshnessMetadataError(
                f"publication must use NAME=REVISION syntax: {value!r}"
            )
        if name in publications:
            raise FreshnessMetadataError(f"duplicate publication: {name!r}")
        publications[name] = revision
    return validate_publications(publications)


def freshness_revision_metas(source: str) -> list[dict[str, str | None]]:
    parser = MetaParser()
    parser.feed(source)
    parser.close()
    return [
        meta
        for meta in parser.metas
        if (meta.get("name") or "").casefold() == SITE_REVISION_META_NAME
    ]


def annotate_site_revision(source: str, revision: str, path: Path) -> str:
    revision = validate_revision(revision, "site")
    metas = freshness_revision_metas(source)
    if len(metas) > 1:
        raise FreshnessMetadataError(
            f"{path}: expected at most one {SITE_REVISION_META_NAME} meta element"
        )
    if metas:
        if metas[0].get("content") != revision:
            raise FreshnessMetadataError(
                f"{path}: existing {SITE_REVISION_META_NAME} metadata conflicts with build revision"
            )
        return source

    head_closes = list(HEAD_CLOSE_PATTERN.finditer(source))
    if len(head_closes) != 1:
        raise FreshnessMetadataError(
            f"{path}: expected exactly one closing head tag, found {len(head_closes)}"
        )
    position = head_closes[0].start()
    tag = (
        f'<meta name="{SITE_REVISION_META_NAME}" '
        f'content="{html.escape(revision, quote=True)}">\n'
    )
    updated = source[:position] + tag + source[position:]
    metas = freshness_revision_metas(updated)
    if len(metas) != 1 or metas[0].get("content") != revision:
        raise FreshnessMetadataError(f"{path}: Site revision metadata insertion failed")
    return updated


def is_sandbox_preview(path: Path, site_root: Path) -> bool:
    relative = path.relative_to(site_root)
    return relative.parts[:2] == ("repository-trees", "previews")


def annotate_generated_html(site_root: Path, site_revision: str) -> int:
    resolved_root = site_root.resolve(strict=True)
    html_files = sorted(path for path in resolved_root.rglob("*.html") if path.is_file())
    if not html_files:
        raise FreshnessMetadataError(f"no generated HTML files found under {resolved_root}")

    modified = 0
    for path in html_files:
        if is_sandbox_preview(path, resolved_root):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise FreshnessMetadataError(
                f"unable to read generated HTML {path}: {exc}"
            ) from exc
        updated = annotate_site_revision(source, site_revision, path)
        if updated == source:
            continue
        path.write_text(updated, encoding="utf-8")
        modified += 1
    return modified


def build_payload(
    site_revision: str,
    deployment_timestamp: str,
    publications: dict[str, str],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "site_revision": validate_revision(site_revision, "site"),
        "deployed_at": validate_deployment_timestamp(deployment_timestamp),
        "publications": validate_publications(publications),
    }


def generate_freshness_metadata(
    site_root: Path,
    site_revision: str,
    deployment_timestamp: str,
    publications: dict[str, str],
) -> tuple[Path, int]:
    resolved_root = site_root.resolve(strict=True)
    payload = build_payload(site_revision, deployment_timestamp, publications)
    annotated = annotate_generated_html(resolved_root, site_revision)
    output = resolved_root / "site-version.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output, annotated


def main() -> int:
    args = parse_args()
    try:
        publications = parse_publications(args.publication)
        deployment_timestamp = args.deployment_timestamp
        if deployment_timestamp is None:
            deployment_timestamp = deployment_timestamp_from_index(args.site_root)
        output, annotated = generate_freshness_metadata(
            args.site_root,
            args.site_revision,
            deployment_timestamp,
            publications,
        )
    except (OSError, FreshnessMetadataError) as exc:
        print(f"generate_freshness_metadata.py: {exc}", file=sys.stderr)
        return 1
    print(
        f"wrote {output} and annotated {annotated} generated HTML file(s) "
        f"with {SITE_REVISION_META_NAME}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
