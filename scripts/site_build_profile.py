#!/usr/bin/env python3
"""Collect detailed, non-production profiling evidence for the generated Site tree."""

from __future__ import annotations

import argparse
import io
import json
import pstats
import re
import shutil
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any


SITE_REVISION_META_NAME = "templates-site-revision"
FRESHNESS_META_PATTERN = re.compile(
    r'<meta\s+name=["\']templates-site-revision["\']\s+'
    r'content=["\'][0-9a-f]{40}["\']>\s*\n?',
    re.IGNORECASE,
)
LINE_ANCHOR_PATTERN = re.compile(
    r'class=["\']line-number["\']\s+href=["\']#L\d+["\']',
    re.IGNORECASE,
)


class ProfileError(RuntimeError):
    """Raised when profiling input is missing, unsafe, or inconsistent."""


class MainLinkCounter(HTMLParser):
    """Count the same main-region link population used by Site link validation."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.main_depth = 0
        self.saw_main = False
        self.all_links = 0
        self.main_links = 0
        self.all_fragments = 0
        self.main_fragments = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        folded = tag.casefold()
        if folded == "main":
            self.saw_main = True
            self.main_depth += 1
        self._count_link(folded, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        folded = tag.casefold()
        if folded == "main":
            self.saw_main = True
            self.main_depth += 1
        self._count_link(folded, attrs)
        if folded == "main" and self.main_depth:
            self.main_depth -= 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "main" and self.main_depth:
            self.main_depth -= 1

    def _count_link(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag not in {"a", "area"}:
            return
        href = None
        for name, value in attrs:
            if name.casefold() == "href":
                href = value
                break
        if href is None:
            return
        self.all_links += 1
        fragment = href.startswith("#") and len(href) > 1
        if fragment:
            self.all_fragments += 1
        if self.main_depth:
            self.main_links += 1
            if fragment:
                self.main_fragments += 1

    @property
    def effective_links(self) -> int:
        return self.main_links if self.saw_main else self.all_links

    @property
    def effective_fragments(self) -> int:
        return self.main_fragments if self.saw_main else self.all_fragments


def _bucket(relative: PurePosixPath) -> str:
    parts = relative.parts
    if parts[:2] == ("repository-trees", "previews"):
        return "repository-tree-previews"
    if parts and parts[0] == "files":
        return "files"
    if parts and (parts[0] == "guided" or (len(parts) > 1 and parts[1] == "guided")):
        return "guided"
    return "reader"


def _empty_bucket() -> dict[str, int]:
    return {
        "html_pages": 0,
        "html_bytes": 0,
        "effective_links": 0,
        "fragment_links": 0,
        "line_anchors": 0,
        "freshness_meta_pages": 0,
    }


def collect_inventory(site_root: Path) -> dict[str, Any]:
    try:
        root = site_root.resolve(strict=True)
    except OSError as exc:
        raise ProfileError(f"unable to resolve site root {site_root}: {exc}") from exc
    if not root.is_dir():
        raise ProfileError(f"site root is not a directory: {root}")

    buckets: dict[str, dict[str, int]] = defaultdict(_empty_bucket)
    total_files = 0
    total_bytes = 0
    symlinks = 0

    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            symlinks += 1
            continue
        if not path.is_file():
            continue
        total_files += 1
        total_bytes += path.stat().st_size
        if path.suffix.casefold() != ".html":
            continue

        relative = PurePosixPath(path.relative_to(root).as_posix())
        bucket = buckets[_bucket(relative)]
        size = path.stat().st_size
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ProfileError(f"unable to read generated HTML {relative}: {exc}") from exc

        counter = MainLinkCounter()
        counter.feed(source)
        counter.close()
        bucket["html_pages"] += 1
        bucket["html_bytes"] += size
        bucket["effective_links"] += counter.effective_links
        bucket["fragment_links"] += counter.effective_fragments
        bucket["line_anchors"] += len(LINE_ANCHOR_PATTERN.findall(source))
        if SITE_REVISION_META_NAME in source:
            bucket["freshness_meta_pages"] += 1

    ordered_buckets = {
        name: buckets.get(name, _empty_bucket())
        for name in ("reader", "guided", "files", "repository-tree-previews")
    }
    return {
        "schema_version": 1,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "symlinks": symlinks,
        "html_pages": sum(value["html_pages"] for value in ordered_buckets.values()),
        "html_bytes": sum(value["html_bytes"] for value in ordered_buckets.values()),
        "effective_links": sum(value["effective_links"] for value in ordered_buckets.values()),
        "fragment_links": sum(value["fragment_links"] for value in ordered_buckets.values()),
        "line_anchors": sum(value["line_anchors"] for value in ordered_buckets.values()),
        "buckets": ordered_buckets,
    }


def prepare_freshness_input(source_root: Path, destination: Path) -> dict[str, int]:
    try:
        source = source_root.resolve(strict=True)
    except OSError as exc:
        raise ProfileError(f"unable to resolve source Site tree: {exc}") from exc
    if not source.is_dir():
        raise ProfileError("source Site tree must be a directory")
    if destination.exists() or destination.is_symlink():
        raise ProfileError(f"freshness destination already exists: {destination}")

    shutil.copytree(source, destination)
    stripped = 0
    touched = 0
    for path in sorted(destination.rglob("*.html")):
        relative = PurePosixPath(path.relative_to(destination).as_posix())
        if relative.parts[:2] == ("repository-trees", "previews"):
            continue
        text = path.read_text(encoding="utf-8")
        updated, count = FRESHNESS_META_PATTERN.subn("", text)
        if count:
            path.write_text(updated, encoding="utf-8")
            touched += 1
            stripped += count

    removed = 0
    for name in ("site-version.json", "build-provenance.json"):
        path = destination / name
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise ProfileError(f"freshness metadata output is not a regular file: {path}")
            path.unlink()
            removed += 1
    return {"html_files_touched": touched, "meta_tags_removed": stripped, "metadata_files_removed": removed}


def write_empty_translation_map(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ProfileError(f"translation map output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "canonical_language": "en",
                "translations": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def summarize_profile(profile: Path, label: str, limit: int) -> dict[str, Any]:
    if limit < 1:
        raise ProfileError("profile summary limit must be positive")
    if not profile.is_file():
        raise ProfileError(f"cProfile output is missing: {profile}")

    stream = io.StringIO()
    stats = pstats.Stats(str(profile), stream=stream)
    stats.strip_dirs().sort_stats("cumulative").print_stats(limit)
    rendered = stream.getvalue().rstrip()
    print(f"[profile] {label}")
    print(rendered)
    return {
        "label": label,
        "total_calls": stats.total_calls,
        "primitive_calls": stats.prim_calls,
        "profiled_cpu_seconds": round(stats.total_tt, 6),
    }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def append_inventory_summary(path: Path, inventory: dict[str, Any]) -> None:
    lines = [
        "### Generated Site profiling inventory",
        "",
        f"- HTML pages: `{inventory['html_pages']}`",
        f"- HTML bytes: `{inventory['html_bytes']}`",
        f"- link-validator effective links: `{inventory['effective_links']}`",
        f"- fragment links: `{inventory['fragment_links']}`",
        f"- repository line anchors: `{inventory['line_anchors']}`",
        "",
        "| bucket | pages | bytes | effective links | fragments | line anchors |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, bucket in inventory["buckets"].items():
        lines.append(
            f"| {name} | {bucket['html_pages']} | {bucket['html_bytes']} | "
            f"{bucket['effective_links']} | {bucket['fragment_links']} | {bucket['line_anchors']} |"
        )
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--site-root", required=True, type=Path)
    inventory_parser.add_argument("--output", required=True, type=Path)
    inventory_parser.add_argument("--summary", type=Path)

    freshness_parser = subparsers.add_parser("prepare-freshness-input")
    freshness_parser.add_argument("--source-root", required=True, type=Path)
    freshness_parser.add_argument("--destination", required=True, type=Path)
    freshness_parser.add_argument("--output", required=True, type=Path)

    translation_parser = subparsers.add_parser("write-empty-translation-map")
    translation_parser.add_argument("--output", required=True, type=Path)

    profile_parser = subparsers.add_parser("profile-summary")
    profile_parser.add_argument("--profile", required=True, type=Path)
    profile_parser.add_argument("--label", required=True)
    profile_parser.add_argument("--output-jsonl", required=True, type=Path)
    profile_parser.add_argument("--limit", type=int, default=30)

    args = parser.parse_args()
    try:
        if args.command == "inventory":
            inventory = collect_inventory(args.site_root)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(inventory, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(inventory, sort_keys=True))
            if args.summary is not None:
                append_inventory_summary(args.summary, inventory)
        elif args.command == "prepare-freshness-input":
            record = prepare_freshness_input(args.source_root, args.destination)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(record, sort_keys=True))
        elif args.command == "write-empty-translation-map":
            write_empty_translation_map(args.output)
            print(f"wrote empty profiling translation map: {args.output}")
        else:
            record = summarize_profile(args.profile, args.label, args.limit)
            append_jsonl(args.output_jsonl, record)
    except (OSError, ProfileError, ValueError) as exc:
        print(f"site_build_profile.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
