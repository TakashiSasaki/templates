"""Shared validation of guided locale records against the canonical graph."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

LANGUAGE_TAG = re.compile(r"\A[a-z]{2,3}(?:-[a-z0-9]{2,8})*\Z")


class LocaleViewerError(RuntimeError):
    """Raised when localized guided navigation cannot be rendered safely."""


def validate_language(value: Any, field: str = "language") -> str:
    if (
        not isinstance(value, str)
        or not LANGUAGE_TAG.fullmatch(value)
        or value == "en"
    ):
        raise LocaleViewerError(f"{field} must be a non-English lowercase language tag")
    return value


def read_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise LocaleViewerError(f"{label} must be a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocaleViewerError(f"unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LocaleViewerError(f"{label} must be an object")
    return value


def load_overlays(path: Path, graph: dict[str, Any]) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    data = read_json(path, "guided locale overlay")
    if set(data) != {
        "schema_version",
        "canonical_graph_schema_version",
        "canonical_language",
        "locales",
    }:
        raise LocaleViewerError("guided locale overlay has unsupported fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise LocaleViewerError("guided locale overlay schema_version must be integer 1")
    if data["canonical_graph_schema_version"] != graph.get("schema_version"):
        raise LocaleViewerError("guided locale overlay does not match graph schema")
    if data["canonical_language"] != "en":
        raise LocaleViewerError("guided locale overlay canonical_language must be en")
    locales = data["locales"]
    if not isinstance(locales, list):
        raise LocaleViewerError("guided locale overlay locales must be an array")

    graph_providers = {provider["name"]: provider for provider in graph["providers"]}
    canonical_indexes_by_provider: dict[str, dict[str, dict[str, Any]]] = {}
    edges_by_source_by_provider: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for name, canonical_provider in graph_providers.items():
        canonical_indexes_by_provider[name] = {
            index["path"]: index for index in canonical_provider["indexes"]
        }
        edges_by_source: dict[str, list[dict[str, Any]]] = {}
        for edge in canonical_provider["edges"]:
            edges_by_source.setdefault(edge["source"], []).append(edge)
        edges_by_source_by_provider[name] = edges_by_source

    result: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for locale_index, locale in enumerate(locales):
        if not isinstance(locale, dict) or set(locale) != {"language", "providers"}:
            raise LocaleViewerError(f"locales[{locale_index}] is invalid")
        language = validate_language(
            locale["language"], f"locales[{locale_index}].language"
        )
        providers = locale["providers"]
        if language in result:
            raise LocaleViewerError(f"duplicate guided locale: {language}")
        if not isinstance(providers, list):
            raise LocaleViewerError(f"locales[{locale_index}].providers must be an array")
        locale_result: dict[str, dict[str, dict[str, Any]]] = {}
        for provider_index, provider in enumerate(providers):
            if not isinstance(provider, dict) or set(provider) != {"name", "revision", "indexes"}:
                raise LocaleViewerError(
                    f"locales[{locale_index}].providers[{provider_index}] is invalid"
                )
            name = provider["name"]
            canonical_provider = graph_providers.get(name)
            if canonical_provider is None or provider["revision"] != canonical_provider["revision"]:
                raise LocaleViewerError(f"locale provider revision mismatch: {name}")
            indexes = provider["indexes"]
            if not isinstance(indexes, list):
                raise LocaleViewerError(f"locale provider indexes must be an array: {name}")
            canonical_indexes = canonical_indexes_by_provider[name]
            edges_by_source = edges_by_source_by_provider[name]
            index_result: dict[str, dict[str, Any]] = {}
            for index in indexes:
                if not isinstance(index, dict) or set(index) != {"path", "title", "sections", "links"}:
                    raise LocaleViewerError(f"localized index record is invalid: {name}")
                path_value = index["path"]
                if path_value not in canonical_indexes or path_value in index_result:
                    raise LocaleViewerError(f"localized index path is invalid or duplicate: {name}:{path_value}")
                title = index["title"]
                sections = index["sections"]
                links = index["links"]
                if not isinstance(title, str) or not title:
                    raise LocaleViewerError(f"localized index title is invalid: {name}:{path_value}")
                if not isinstance(sections, list) or not isinstance(links, list):
                    raise LocaleViewerError(f"localized index prose is invalid: {name}:{path_value}")
                if len(sections) != len(canonical_indexes[path_value]["sections"]):
                    raise LocaleViewerError(f"localized section count drift: {name}:{path_value}")
                for section in sections:
                    if (
                        not isinstance(section, dict)
                        or set(section) != {"title", "level"}
                        or not isinstance(section["title"], str)
                        or not section["title"]
                        or type(section["level"]) is not int
                    ):
                        raise LocaleViewerError(f"localized section prose is invalid: {name}:{path_value}")
                source_edges = edges_by_source.get(path_value, [])
                if len(links) != len(source_edges):
                    raise LocaleViewerError(f"localized link count drift: {name}:{path_value}")
                for link in links:
                    if (
                        not isinstance(link, dict)
                        or set(link) != {"label", "description"}
                        or not isinstance(link["label"], str)
                        or not isinstance(link["description"], str)
                    ):
                        raise LocaleViewerError(f"localized link prose is invalid: {name}:{path_value}")
                index_result[path_value] = index
            locale_result[name] = index_result
        result[language] = locale_result
    return result
