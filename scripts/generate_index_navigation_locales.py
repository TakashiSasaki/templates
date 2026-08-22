#!/usr/bin/env python3
"""Generate locale overlays for the canonical English index-navigation graph."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from scripts.generate_index_navigation import parse_index
    from scripts.translation_manifest import (
        TranslationManifestError,
        load_translation_manifest,
    )
except ModuleNotFoundError:
    from generate_index_navigation import parse_index
    from translation_manifest import TranslationManifestError, load_translation_manifest

PROVIDER_ORDER = ("skill", "policy", "webapp")
JA_NOTICE = "> **参考訳（非正本）:**"


class IndexNavigationLocaleError(RuntimeError):
    """Raised when a locale overlay cannot be bound safely to the canonical graph."""


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise IndexNavigationLocaleError(f"unable to read {label} {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise IndexNavigationLocaleError(f"{label} contains duplicate member: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise IndexNavigationLocaleError(f"unable to parse {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IndexNavigationLocaleError(f"{label} must be an object")
    return value


def regular_file(root: Path, relative: PurePosixPath, field: str) -> Path:
    root = root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        try:
            current.relative_to(root)
        except ValueError as exc:
            raise IndexNavigationLocaleError(
                f"{field} must remain within provider root: {relative}"
            ) from exc
        if current.is_symlink():
            raise IndexNavigationLocaleError(f"{field} must not traverse a symlink: {relative}")
    if not current.is_file():
        raise IndexNavigationLocaleError(f"{field} must be an existing regular file: {relative}")
    return current


def optional_manifest(root: Path, provider: str) -> Path | None:
    relative = PurePosixPath("translations/manifest.json")
    current = root.resolve(strict=True)
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise IndexNavigationLocaleError(
                f"{provider} translation manifest must not traverse a symlink"
            )
        if not current.exists():
            return None
    if not current.is_file():
        raise IndexNavigationLocaleError(
            f"{provider} translation manifest must be a regular file"
        )
    return current


def strip_translation_preamble(text: str, language: str, field: str) -> str:
    """Remove optional front matter and the visible non-authoritative notice for parsing."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[0] == "---":
        try:
            end = lines.index("---", 1)
        except ValueError as exc:
            raise IndexNavigationLocaleError(f"{field} has unterminated front matter") from exc
        lines = lines[end + 1 :]

    title_index = 0
    while title_index < len(lines) and not lines[title_index].strip():
        title_index += 1
    if title_index >= len(lines) or not lines[title_index].startswith("# "):
        raise IndexNavigationLocaleError(f"{field} must begin with a level-1 title")

    notice_index = title_index + 1
    while notice_index < len(lines) and not lines[notice_index].strip():
        notice_index += 1
    if notice_index >= len(lines) or not lines[notice_index].startswith(">"):
        raise IndexNavigationLocaleError(
            f"{field} must place a visible non-authoritative notice after its title"
        )
    if language == "ja" and not lines[notice_index].startswith(JA_NOTICE):
        raise IndexNavigationLocaleError(
            f"{field} must use the standard Japanese non-authoritative notice"
        )

    end_notice = notice_index
    while end_notice < len(lines) and lines[end_notice].startswith(">"):
        end_notice += 1
    del lines[notice_index:end_notice]
    return "\n".join(lines)


def section_index(section: str | None, titles: list[str], field: str) -> int | None:
    if section is None:
        return None
    try:
        return titles.index(section)
    except ValueError as exc:
        raise IndexNavigationLocaleError(f"{field} references unknown section {section!r}") from exc


def validate_graph(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if graph.get("schema_version") != 1:
        raise IndexNavigationLocaleError("canonical navigation graph schema_version must be 1")
    providers = graph.get("providers")
    if not isinstance(providers, list):
        raise IndexNavigationLocaleError("canonical navigation graph providers must be an array")
    if [provider.get("name") for provider in providers if isinstance(provider, dict)] != list(PROVIDER_ORDER):
        raise IndexNavigationLocaleError(
            "canonical navigation graph providers must be skill, policy, webapp in order"
        )
    return {str(provider["name"]): provider for provider in providers}


def parse_provider_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise IndexNavigationLocaleError("provider must use NAME=PATH syntax")
        name, raw_path = value.split("=", maxsplit=1)
        if name in roots or not raw_path:
            raise IndexNavigationLocaleError(f"invalid or duplicate provider: {name}")
        roots[name] = Path(raw_path)
    if tuple(roots) != PROVIDER_ORDER:
        raise IndexNavigationLocaleError(
            "providers must be supplied exactly in this order: " + ", ".join(PROVIDER_ORDER)
        )
    return roots


def collect_provider_overlays(
    provider: str,
    root: Path,
    graph: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    manifest_path = optional_manifest(root, provider)
    if manifest_path is None:
        return []
    label = f"{provider} translation manifest"
    try:
        manifest = load_translation_manifest(
            manifest_path,
            label,
            publication_root=root,
        )
    except TranslationManifestError as exc:
        raise IndexNavigationLocaleError(str(exc)) from exc

    indexes = graph.get("indexes")
    edges = graph.get("edges")
    if not isinstance(indexes, list) or not isinstance(edges, list):
        raise IndexNavigationLocaleError(f"{provider} canonical graph is malformed")
    index_by_path = {
        str(index["path"]): index
        for index in indexes
        if isinstance(index, dict) and isinstance(index.get("path"), str)
    }
    overlays: list[tuple[str, dict[str, Any]]] = []

    for entry in manifest.for_surface("guided"):
        field = f"{provider}.translations[{entry.index}]"
        canonical = entry.canonical
        translation = entry.translation
        language = entry.language
        if canonical.name != "index.md":
            raise IndexNavigationLocaleError(
                f"{field}.canonical must be an index.md document for guided use"
            )

        canonical_index = index_by_path.get(canonical.as_posix())
        if canonical_index is None:
            raise IndexNavigationLocaleError(
                f"{field}.canonical is not reachable in the canonical navigation graph"
            )
        if entry.current_blob_sha is None:
            raise IndexNavigationLocaleError(
                f"{field}.canonical freshness was not bound to provider bytes"
            )
        if canonical_index.get("object_id") != entry.current_blob_sha:
            raise IndexNavigationLocaleError(
                f"canonical graph blob differs from provider bytes for {provider}:{canonical}: "
                f"graph {canonical_index.get('object_id')}, current {entry.current_blob_sha}"
            )

        translation_file = regular_file(root, translation, f"{field}.translation")
        if not entry.is_current:
            continue
        try:
            translated_text = translation_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise IndexNavigationLocaleError(
                f"unable to read guided translation {translation}: {exc}"
            ) from exc
        parsed = parse_index(
            strip_translation_preamble(translated_text, language, field),
            translation.as_posix(),
        )

        canonical_sections = canonical_index.get("sections")
        if not isinstance(canonical_sections, list):
            raise IndexNavigationLocaleError(f"{field} canonical sections are malformed")
        if [section.level for section in parsed.sections] != [
            section.get("level") for section in canonical_sections if isinstance(section, dict)
        ]:
            raise IndexNavigationLocaleError(
                f"{field} translated section hierarchy does not match canonical index"
            )
        canonical_edges = [
            edge for edge in edges
            if isinstance(edge, dict) and edge.get("source") == canonical.as_posix()
        ]
        if len(parsed.links) != len(canonical_edges):
            raise IndexNavigationLocaleError(
                f"{field} translated link count does not match canonical index"
            )
        canonical_section_titles = [
            str(section["title"]) for section in canonical_sections if isinstance(section, dict)
        ]
        translated_section_titles = [section.title for section in parsed.sections]
        links: list[dict[str, str]] = []
        for link_index, (translated_link, canonical_edge) in enumerate(
            zip(parsed.links, canonical_edges, strict=True)
        ):
            if translated_link.raw_target != canonical_edge.get("raw_target"):
                raise IndexNavigationLocaleError(
                    f"{field} link {link_index} target differs from canonical index"
                )
            canonical_section = section_index(
                canonical_edge.get("section"),
                canonical_section_titles,
                f"{field} canonical link {link_index}",
            )
            translated_section = section_index(
                translated_link.section,
                translated_section_titles,
                f"{field} translated link {link_index}",
            )
            if canonical_section != translated_section:
                raise IndexNavigationLocaleError(
                    f"{field} link {link_index} moved to a different section"
                )
            links.append(
                {
                    "label": translated_link.label,
                    "description": translated_link.description,
                }
            )

        overlays.append(
            (
                language,
                {
                    "path": canonical.as_posix(),
                    "title": parsed.title,
                    "sections": [
                        {"title": section.title, "level": section.level}
                        for section in parsed.sections
                    ],
                    "links": links,
                },
            )
        )
    return overlays


def generate_locale_overlays(
    graph: dict[str, Any],
    provider_roots: dict[str, Path],
) -> dict[str, Any]:
    provider_graphs = validate_graph(graph)
    locale_providers: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for provider in PROVIDER_ORDER:
        overlays = collect_provider_overlays(
            provider,
            provider_roots[provider],
            provider_graphs[provider],
        )
        for language, overlay in overlays:
            locale_providers.setdefault(language, {}).setdefault(provider, []).append(overlay)

    locales: list[dict[str, Any]] = []
    for language in sorted(locale_providers):
        providers: list[dict[str, Any]] = []
        for provider in PROVIDER_ORDER:
            indexes = locale_providers[language].get(provider, [])
            if not indexes:
                continue
            providers.append(
                {
                    "name": provider,
                    "revision": provider_graphs[provider]["revision"],
                    "indexes": indexes,
                }
            )
        locales.append({"language": language, "providers": providers})
    return {
        "schema_version": 1,
        "canonical_graph_schema_version": 1,
        "canonical_language": "en",
        "locales": locales,
    }


def write_output(path: Path, payload: dict[str, Any]) -> None:
    if path.is_symlink():
        raise IndexNavigationLocaleError("locale overlay output must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider", action="append", default=[])
    args = parser.parse_args()
    try:
        graph = read_json(args.graph, "canonical navigation graph")
        roots = parse_provider_roots(args.provider)
        payload = generate_locale_overlays(graph, roots)
        write_output(args.output, payload)
        print(
            "guided locale overlays: "
            + ", ".join(
                f"{locale['language']}={sum(len(provider['indexes']) for provider in locale['providers'])}"
                for locale in payload["locales"]
            )
        )
    except (IndexNavigationLocaleError, OSError, RuntimeError) as exc:
        print(f"generate_index_navigation_locales.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
