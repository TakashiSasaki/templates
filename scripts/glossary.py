#!/usr/bin/env python3
"""Parse and validate canonical glossary sources."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import yaml

TERM_ID = re.compile(r"\A(?:templates-[a-z0-9]+(?:-[a-z0-9]+)*|external-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*)\Z")
REPOSITORY_TERM_ID = re.compile(r"\Atemplates-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
EXTERNAL_TERM_ID = re.compile(r"\Aexternal-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
LANGUAGE_TAG = re.compile(r"\A[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*\Z")
PROVIDER_NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
AUTHORITY_KINDS = {"normative", "upstream", "conventional"}
ORIGINS = {"repository", "external"}


class GlossaryError(RuntimeError):
    """Raised when glossary input or integrated output is invalid."""


class StrictLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate and merge mapping keys."""


def _construct_mapping(loader: StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key == "<<":
            raise GlossaryError("YAML merge keys are not supported")
        try:
            duplicate = key in result
        except TypeError as exc:
            raise GlossaryError("YAML mapping keys must be scalar values") from exc
        if duplicate:
            raise GlossaryError(f"YAML contains duplicate mapping key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _reject_yaml_features(text: str) -> None:
    try:
        tokens = yaml.scan(text, Loader=StrictLoader)
        for token in tokens:
            if isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)):
                raise GlossaryError("YAML anchors and aliases are not supported")
            if isinstance(token, yaml.tokens.TagToken):
                raise GlossaryError("YAML custom tags are not supported")
    except yaml.YAMLError as exc:
        raise GlossaryError(f"unable to scan glossary YAML: {exc}") from exc


def _reject_control_characters(text: str) -> None:
    allowed = {"\t", "\n", "\r"}
    for char in text:
        if unicodedata.category(char) == "Cc" and char not in allowed:
            raise GlossaryError("glossary contains a disallowed control character")


def read_yaml(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise GlossaryError(f"glossary source must be a regular file: {path}")
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise GlossaryError(f"unable to read UTF-8 glossary {path}: {exc}") from exc
    _reject_control_characters(text)
    _reject_yaml_features(text)
    try:
        value = yaml.load(text, Loader=StrictLoader)
    except GlossaryError:
        raise
    except yaml.YAMLError as exc:
        raise GlossaryError(f"unable to parse glossary {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GlossaryError("glossary must be a YAML mapping")
    return value


def _nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GlossaryError(f"{field} must be a non-empty string")
    return value


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise GlossaryError(f"{field} must be an array")
    result = [_nonempty_text(item, f"{field}[{index}]") for index, item in enumerate(value)]
    if len(set(result)) != len(result):
        raise GlossaryError(f"{field} must not contain duplicate values")
    return result


def _label_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _validate_labels(term: str, aliases: list[str], field: str) -> None:
    labels = [term, *aliases]
    normalized = [_label_key(value) for value in labels]
    if len(set(normalized)) != len(normalized):
        raise GlossaryError(f"{field} contains duplicate labels")


def _parse_localized_labels(value: Any, field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise GlossaryError(f"{field} must be a non-empty mapping")
    result: dict[str, dict[str, Any]] = {}
    for language, raw in value.items():
        if not isinstance(language, str) or not LANGUAGE_TAG.fullmatch(language):
            raise GlossaryError(f"{field} contains an invalid language tag: {language}")
        if language.casefold() == "en" or language.casefold().startswith("en-"):
            raise GlossaryError(f"{field} must not redefine canonical English labels")
        item_field = f"{field}.{language}"
        if not isinstance(raw, dict):
            raise GlossaryError(f"{item_field} must be a mapping")
        unknown = set(raw) - {"term", "aliases"}
        if unknown:
            raise GlossaryError(
                f"{item_field} contains unsupported fields: {', '.join(sorted(unknown))}"
            )
        if "term" not in raw:
            raise GlossaryError(f"{item_field}.term is required")
        term = _nonempty_text(raw["term"], f"{item_field}.term")
        aliases = _string_list(raw.get("aliases", []), f"{item_field}.aliases")
        _validate_labels(term, aliases, item_field)
        result[language] = {"term": term, "aliases": aliases}
    return result


def _parse_authority(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GlossaryError(f"{field} must be a mapping")
    unknown = set(value) - {"kind", "sources"}
    missing = {"kind", "sources"} - set(value)
    if unknown:
        raise GlossaryError(f"{field} contains unsupported fields: {', '.join(sorted(unknown))}")
    if missing:
        raise GlossaryError(f"{field} is missing required fields: {', '.join(sorted(missing))}")
    kind = value["kind"]
    if kind not in AUTHORITY_KINDS:
        raise GlossaryError(f"{field}.kind must be normative, upstream, or conventional")
    raw_sources = value["sources"]
    if not isinstance(raw_sources, list) or not raw_sources:
        raise GlossaryError(f"{field}.sources must be a non-empty array")
    sources: list[dict[str, str]] = []
    for index, raw in enumerate(raw_sources):
        source_field = f"{field}.sources[{index}]"
        if not isinstance(raw, dict):
            raise GlossaryError(f"{source_field} must be a mapping")
        unknown = set(raw) - {"title", "url", "version", "locator"}
        missing = {"title", "url"} - set(raw)
        if unknown:
            raise GlossaryError(
                f"{source_field} contains unsupported fields: {', '.join(sorted(unknown))}"
            )
        if missing:
            raise GlossaryError(
                f"{source_field} is missing required fields: {', '.join(sorted(missing))}"
            )
        title = _nonempty_text(raw["title"], f"{source_field}.title")
        url = _nonempty_text(raw["url"], f"{source_field}.url")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise GlossaryError(f"{source_field}.url must be an absolute HTTPS URL without credentials")
        source = {"title": title, "url": url}
        for optional in ("version", "locator"):
            if optional in raw:
                source[optional] = _nonempty_text(raw[optional], f"{source_field}.{optional}")
        sources.append(source)
    return {"kind": kind, "sources": sources}


def parse_term(raw: Any, index: int) -> dict[str, Any]:
    field = f"terms[{index}]"
    if not isinstance(raw, dict):
        raise GlossaryError(f"{field} must be a mapping")
    allowed = {
        "id",
        "term",
        "aliases",
        "localized_labels",
        "origin",
        "definition",
        "summary",
        "authority",
        "repository_usage",
        "related_terms",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise GlossaryError(f"{field} contains unsupported fields: {', '.join(sorted(unknown))}")
    missing = {"id", "term", "origin"} - set(raw)
    if missing:
        raise GlossaryError(f"{field} is missing required fields: {', '.join(sorted(missing))}")

    term_id = _nonempty_text(raw["id"], f"{field}.id")
    if not TERM_ID.fullmatch(term_id):
        raise GlossaryError(f"{field}.id must use a supported glossary namespace")
    term = _nonempty_text(raw["term"], f"{field}.term")
    aliases = _string_list(raw.get("aliases", []), f"{field}.aliases")
    _validate_labels(term, aliases, field)
    origin = raw["origin"]
    if origin not in ORIGINS:
        raise GlossaryError(f"{field}.origin must be repository or external")

    result: dict[str, Any] = {
        "id": term_id,
        "term": term,
        "aliases": aliases,
        "origin": origin,
    }
    if "localized_labels" in raw:
        result["localized_labels"] = _parse_localized_labels(
            raw["localized_labels"], f"{field}.localized_labels"
        )
    if "related_terms" in raw:
        related = _string_list(raw["related_terms"], f"{field}.related_terms")
        for related_id in related:
            if not TERM_ID.fullmatch(related_id):
                raise GlossaryError(f"{field}.related_terms contains an invalid term ID: {related_id}")
        result["related_terms"] = related
    if "repository_usage" in raw:
        result["repository_usage"] = _nonempty_text(
            raw["repository_usage"], f"{field}.repository_usage"
        )
    if "summary" in raw:
        result["summary"] = _nonempty_text(raw["summary"], f"{field}.summary")

    if origin == "repository":
        if not REPOSITORY_TERM_ID.fullmatch(term_id):
            raise GlossaryError(f"{field}.id must start with templates- for repository terms")
        if "definition" not in raw:
            raise GlossaryError(f"{field}.definition is required for repository terms")
        if "authority" in raw:
            raise GlossaryError(f"{field}.authority is not allowed for repository terms")
        result["definition"] = _nonempty_text(raw["definition"], f"{field}.definition")
    else:
        if not EXTERNAL_TERM_ID.fullmatch(term_id):
            raise GlossaryError(f"{field}.id must use external-<domain>-<slug> for external terms")
        if "summary" not in raw:
            raise GlossaryError(f"{field}.summary is required for external terms")
        if "authority" not in raw:
            raise GlossaryError(f"{field}.authority is required for external terms")
        if "definition" in raw:
            raise GlossaryError(f"{field}.definition is not allowed for external terms")
        result["authority"] = _parse_authority(raw["authority"], f"{field}.authority")
    return result


def load_glossary(path: Path) -> list[dict[str, Any]]:
    data = read_yaml(path)
    if set(data) != {"schema_version", "terms"}:
        unknown = set(data) - {"schema_version", "terms"}
        missing = {"schema_version", "terms"} - set(data)
        details = []
        if unknown:
            details.append("unsupported fields: " + ", ".join(sorted(unknown)))
        if missing:
            details.append("missing fields: " + ", ".join(sorted(missing)))
        raise GlossaryError("glossary top level is invalid (" + "; ".join(details) + ")")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise GlossaryError("glossary schema_version must be the integer 1")
    raw_terms = data["terms"]
    if not isinstance(raw_terms, list) or not raw_terms:
        raise GlossaryError("glossary terms must be a non-empty array")
    terms = [parse_term(raw, index) for index, raw in enumerate(raw_terms)]
    ids = [term["id"] for term in terms]
    if len(set(ids)) != len(ids):
        raise GlossaryError("glossary term IDs must be unique within a provider")
    return terms


def safe_relative_glossary_path(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\0" in value:
        raise GlossaryError(f"{field} must be a safe relative POSIX path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.casefold() == ".git" for part in parts):
        raise GlossaryError(f"{field} must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.suffix.lower() != ".yml":
        raise GlossaryError(f"{field} must be a safe relative .yml path")
    return path


def resolve_without_symlinks(root: Path, relative: PurePosixPath, field: str) -> Path:
    root = root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        try:
            current.relative_to(root)
        except ValueError as exc:
            raise GlossaryError(f"{field} must remain within publication root") from exc
        if current.is_symlink():
            raise GlossaryError(f"{field} must not traverse a symlink")
    if not current.is_file():
        raise GlossaryError(f"{field} must identify an existing regular file: {relative}")
    return current


def glossary_source_from_catalog(root: Path) -> PurePosixPath | None:
    path = root / "docs" / "publication-catalog.json"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise GlossaryError(f"unable to read publication catalog {path}: {exc}") from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GlossaryError(f"publication catalog contains duplicate member: {key}")
            result[key] = value
        return result

    try:
        data = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise GlossaryError(f"unable to parse publication catalog {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise GlossaryError("publication catalog must be an object")
    version = data.get("schema_version")
    if type(version) is not int or version not in (1, 2, 3):
        raise GlossaryError("publication catalog schema_version must be integer 1, 2, or 3")
    if version < 3:
        if "glossary" in data:
            raise GlossaryError("publication catalog versions 1 and 2 do not support glossary")
        return None
    raw = data.get("glossary")
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {"source"}:
        raise GlossaryError("publication catalog glossary must contain only source")
    source = safe_relative_glossary_path(raw["source"], "glossary.source")
    resolve_without_symlinks(root, source, "glossary.source")
    return source


def integrate_glossaries(
    publications: dict[str, Path],
    revisions: dict[str, str],
    repository: str,
) -> dict[str, Any]:
    if set(publications) != set(revisions):
        raise GlossaryError("publication and revision provider sets must match")
    terms: list[dict[str, Any]] = []
    for provider in sorted(publications):
        if not PROVIDER_NAME.fullmatch(provider):
            raise GlossaryError(f"invalid provider name: {provider}")
        revision = revisions[provider]
        if not FULL_SHA.fullmatch(revision):
            raise GlossaryError(f"{provider} revision must be a lowercase 40-character Git SHA")
        root = publications[provider].resolve(strict=True)
        source = glossary_source_from_catalog(root)
        if source is None:
            continue
        for term in load_glossary(resolve_without_symlinks(root, source, "glossary.source")):
            enriched = dict(term)
            enriched["provider"] = provider
            enriched["source_path"] = source.as_posix()
            enriched["source_revision"] = revision
            terms.append(enriched)

    ids = [term["id"] for term in terms]
    if len(set(ids)) != len(ids):
        duplicates = sorted({term_id for term_id in ids if ids.count(term_id) > 1})
        raise GlossaryError("integrated glossary has duplicate term IDs: " + ", ".join(duplicates))
    known = set(ids)
    unresolved = sorted(
        {
            related
            for term in terms
            for related in term.get("related_terms", [])
            if related not in known
        }
    )
    if unresolved:
        raise GlossaryError("integrated glossary has unresolved related terms: " + ", ".join(unresolved))
    terms.sort(key=lambda term: term["id"])
    return {"schema_version": 1, "repository": repository, "terms": terms}
