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
SITE_REVISION_META_NAME = "templates-site-revision"
EXPECTED_PUBLICATIONS = ("composition", "policy")


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


class HeadBoundaryParser(HTMLParser):
    """Locate actual parsed head boundaries rather than raw string lookalikes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.head_starts: list[tuple[int, int]] = []
        self.head_ends: list[tuple[int, int]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.casefold() == "head":
            self.head_starts.append(self.getpos())

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "head":
            self.head_ends.append(self.getpos())


class FreshnessDocumentParser(HTMLParser):
    """Collect head boundaries and meta elements in one structural HTML pass."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.head_starts: list[tuple[int, int]] = []
        self.head_ends: list[tuple[int, int]] = []
        self.metas: list[dict[str, str | None]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        folded = tag.casefold()
        if folded == "head":
            self.head_starts.append(self.getpos())
        if folded == "meta":
            self.metas.append({name.casefold(): value for name, value in attrs})

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "head":
            self.head_ends.append(self.getpos())


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
        help="Resolved provider publication revision; repeat for composition and policy.",
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


def revision_metas(
    metas: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    return [
        meta
        for meta in metas
        if (meta.get("name") or "").casefold() == SITE_REVISION_META_NAME
    ]


def freshness_revision_metas(source: str) -> list[dict[str, str | None]]:
    parser = MetaParser()
    parser.feed(source)
    parser.close()
    return revision_metas(parser.metas)


def source_offset(source: str, position: tuple[int, int]) -> int:
    line_number, column = position
    if line_number < 1 or column < 0:
        raise FreshnessMetadataError("invalid HTML parser source position")
    line_starts = [0] + [match.start() + 1 for match in re.finditer(r"\n", source)]
    if line_number > len(line_starts):
        raise FreshnessMetadataError("HTML parser source position exceeds document")
    return line_starts[line_number - 1] + column


def parsed_head_close_offset(
    source: str,
    path: Path,
    head_starts: list[tuple[int, int]],
    head_ends: list[tuple[int, int]],
) -> int:
    if len(head_starts) != 1 or len(head_ends) != 1:
        raise FreshnessMetadataError(
            f"{path}: expected exactly one closing head tag for exactly one head element, "
            f"found {len(head_starts)} start tag(s) and {len(head_ends)} closing tag(s)"
        )
    start_offset = source_offset(source, head_starts[0])
    end_offset = source_offset(source, head_ends[0])
    if end_offset <= start_offset:
        raise FreshnessMetadataError(
            f"{path}: closing head tag precedes head start tag"
        )
    return end_offset


def head_close_offset(source: str, path: Path) -> int:
    parser = HeadBoundaryParser()
    parser.feed(source)
    parser.close()
    return parsed_head_close_offset(
        source,
        path,
        parser.head_starts,
        parser.head_ends,
    )


def annotate_site_revision(source: str, revision: str, path: Path) -> str:
    revision = validate_revision(revision, "site")

    # Head placement and pre-existing revision metadata are both structural HTML
    # properties. Collect them in one pass. The generated file is reread and
    # structurally verified before generate_freshness_metadata() can succeed.
    parser = FreshnessDocumentParser()
    parser.feed(source)
    parser.close()
    position = parsed_head_close_offset(
        source,
        path,
        parser.head_starts,
        parser.head_ends,
    )
    metas = revision_metas(parser.metas)
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

    tag = (
        f'<meta name="{SITE_REVISION_META_NAME}" '
        f'content="{html.escape(revision, quote=True)}">\n'
    )
    return source[:position] + tag + source[position:]


def is_sandbox_preview(path: Path, site_root: Path) -> bool:
    relative = path.relative_to(site_root)
    return relative.parts[:2] == ("repository-trees", "previews")


def generated_html_files(site_root: Path) -> list[Path]:
    html_files: list[Path] = []
    for path in sorted(site_root.rglob("*.html")):
        relative = path.relative_to(site_root)
        if path.is_symlink() or not path.is_file():
            raise FreshnessMetadataError(
                f"generated HTML must be a regular file: {relative}"
            )
        html_files.append(path)
    if not html_files:
        raise FreshnessMetadataError(f"no generated HTML files found under {site_root}")
    return html_files


def annotate_generated_html(site_root: Path, site_revision: str) -> int:
    resolved_root = site_root.resolve(strict=True)
    updates: dict[Path, str] = {}
    for path in generated_html_files(resolved_root):
        if is_sandbox_preview(path, resolved_root):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise FreshnessMetadataError(
                f"unable to read generated HTML {path}: {exc}"
            ) from exc
        updated = annotate_site_revision(source, site_revision, path)
        if updated != source:
            updates[path] = updated

    for path, updated in updates.items():
        path.write_text(updated, encoding="utf-8")
    return len(updates)



def annotate_and_validate_generated_html(site_root: Path, site_revision: str) -> tuple[int, int]:
    """Annotate and validate each eligible page in one structural pass."""
    resolved_root = site_root.resolve(strict=True)
    updates: dict[Path, str] = {}
    verified = 0
    revision = validate_revision(site_revision, "site")
    marker = (
        f'<meta name="{SITE_REVISION_META_NAME}" '
        f'content="{html.escape(revision, quote=True)}">\n'
    )
    for path in generated_html_files(resolved_root):
        if is_sandbox_preview(path, resolved_root):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise FreshnessMetadataError(
                f"unable to read generated HTML {path}: {exc}"
            ) from exc
        updated = annotate_site_revision(source, revision, path)
        head_end = updated.find("</head>")
        if updated.count(marker) != 1 or head_end < 0 or updated.find(marker) > head_end:
            raise FreshnessMetadataError(
                f"{path}: freshness revision metadata verification failed"
            )
        if updated != source:
            updates[path] = updated
        verified += 1

    for path, updated in updates.items():
        path.write_text(updated, encoding="utf-8")
    if verified == 0:
        raise FreshnessMetadataError("no cache-eligible HTML freshness metadata verified")
    return len(updates), verified

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


def validate_output_path(output: Path) -> None:
    if output.is_symlink():
        raise FreshnessMetadataError(
            f"output path must not be a symbolic link: {output}"
        )
    if output.exists() and not output.is_file():
        raise FreshnessMetadataError(
            f"output path must be a regular file: {output}"
        )


def canonical_payload_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def verify_freshness_contract(
    site_root: Path,
    output: Path,
    site_revision: str,
    payload: dict[str, object],
) -> int:
    """Fail if the on-disk freshness identity or annotated HTML is inconsistent."""
    validate_output_path(output)
    try:
        on_disk_text = output.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FreshnessMetadataError(
            f"unable to verify freshness identity {output}: {exc}"
        ) from exc
    if on_disk_text != canonical_payload_text(payload):
        raise FreshnessMetadataError(
            f"freshness identity payload verification failed: {output}"
        )

    verified = 0
    for path in generated_html_files(site_root):
        if is_sandbox_preview(path, site_root):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise FreshnessMetadataError(
                f"unable to verify generated HTML {path}: {exc}"
            ) from exc
        metas = freshness_revision_metas(source)
        if len(metas) != 1 or metas[0].get("content") != site_revision:
            raise FreshnessMetadataError(
                f"{path}: freshness revision metadata verification failed"
            )
        verified += 1
    if verified == 0:
        raise FreshnessMetadataError("no cache-eligible HTML freshness metadata verified")
    return verified


def generate_freshness_metadata(
    site_root: Path,
    site_revision: str,
    deployment_timestamp: str,
    publications: dict[str, str],
) -> tuple[Path, int]:
    resolved_root = site_root.resolve(strict=True)
    payload = build_payload(site_revision, deployment_timestamp, publications)
    output = resolved_root / "site-version.json"
    validate_output_path(output)
    annotated, verified = annotate_and_validate_generated_html(resolved_root, site_revision)
    output.write_text(
        canonical_payload_text(payload),
        encoding="utf-8",
    )
    validate_output_path(output)
    try:
        if output.read_text(encoding="utf-8") != canonical_payload_text(payload):
            raise FreshnessMetadataError(
                f"freshness identity payload verification failed: {output}"
            )
    except (OSError, UnicodeError) as exc:
        raise FreshnessMetadataError(
            f"unable to verify freshness identity {output}: {exc}"
        ) from exc
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
        f"wrote and verified {output}; annotated {annotated} generated HTML file(s) "
        f"with {SITE_REVISION_META_NAME}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
