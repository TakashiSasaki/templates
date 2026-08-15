#!/usr/bin/env python3
"""Parse, validate, and integrate canonical glossary sources."""

from __future__ import annotations

import ipaddress
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import idna
import yaml

TERM_ID = re.compile(
    r"\A(?:templates-[a-z0-9]+(?:-[a-z0-9]+)*|"
    r"external-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*)\Z"
)
REPOSITORY_TERM_ID = re.compile(r"\Atemplates-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
EXTERNAL_TERM_ID = re.compile(
    r"\Aexternal-[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*\Z"
)
LANGUAGE_TAG = re.compile(r"\A[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*\Z")
PROVIDER_NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
AUTHORITY_KINDS = {"normative", "upstream", "conventional"}
ORIGINS = {"repository", "external"}
MERGE_TAG = "tag:yaml.org,2002:merge"
ALLOWED_TEXT_CONTROLS = {"\t", "\n", "\r"}


class GlossaryError(RuntimeError):
    """Raised when glossary input or integrated output is invalid."""


class StrictLoader(yaml.SafeLoader):
    """Safe YAML loader with a deliberately small mapping-key surface."""


def _construct_mapping(
    loader: StrictLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[str, Any]:
    for key_node, _ in node.value:
        if key_node.tag == MERGE_TAG or (
            isinstance(key_node, yaml.ScalarNode) and key_node.value == "<<"
        ):
            raise GlossaryError("YAML merge keys are not supported")

    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise GlossaryError("YAML mapping keys must be strings")
        if key in result:
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


def _reject_control_characters(text: str, field: str = "glossary") -> None:
    for char in text:
        if (
            unicodedata.category(char) == "Cc"
            and char not in ALLOWED_TEXT_CONTROLS
        ):
            raise GlossaryError(f"{field} contains a disallowed control character")


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
    _reject_control_characters(value, field)
    return value


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise GlossaryError(f"{field} must be an array")
    result = [
        _nonempty_text(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    ]
    if len(set(result)) != len(result):
        raise GlossaryError(f"{field} must not contain duplicate values")
    return result


def _label_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _canonical_language_tag(value: str) -> str:
    parts = value.split("-")
    canonical = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            canonical.append(part.title())
        elif (
            len(part) == 2 and part.isalpha()
        ) or (
            len(part) == 3 and part.isdigit()
        ):
            canonical.append(part.upper())
        else:
            canonical.append(part.lower())
    return "-".join(canonical)


def _validate_labels(term: str, aliases: list[str], field: str) -> None:
    normalized = [_label_key(value) for value in (term, *aliases)]
    if len(set(normalized)) != len(normalized):
        raise GlossaryError(f"{field} contains duplicate labels")


def _parse_localized_labels(
    value: Any,
    field: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise GlossaryError(f"{field} must be a non-empty mapping")

    result: dict[str, dict[str, Any]] = {}
    normalized_languages: set[str] = set()
    for language, raw in value.items():
        if not isinstance(language, str) or not LANGUAGE_TAG.fullmatch(language):
            raise GlossaryError(
                f"{field} contains an invalid language tag: {language}"
            )
        canonical_language = _canonical_language_tag(language)
        normalized_language = canonical_language.casefold()
        if normalized_language in normalized_languages:
            raise GlossaryError(
                f"{field} contains duplicate language tags ignoring case: {language}"
            )
        normalized_languages.add(normalized_language)
        if normalized_language == "en" or normalized_language.startswith("en-"):
            raise GlossaryError(
                f"{field} must not redefine canonical English labels"
            )

        item_field = f"{field}.{language}"
        if not isinstance(raw, dict):
            raise GlossaryError(f"{item_field} must be a mapping")
        unknown = set(raw) - {"term", "aliases"}
        if unknown:
            raise GlossaryError(
                f"{item_field} contains unsupported fields: "
                + ", ".join(sorted(unknown))
            )
        if "term" not in raw:
            raise GlossaryError(f"{item_field}.term is required")

        term = _nonempty_text(raw["term"], f"{item_field}.term")
        aliases = _string_list(
            raw.get("aliases", []),
            f"{item_field}.aliases",
        )
        _validate_labels(term, aliases, item_field)
        result[canonical_language] = {"term": term, "aliases": aliases}
    return result


def _validate_authority_url(url: str, field: str) -> None:
    if any(char.isspace() for char in url):
        raise GlossaryError(f"{field} must not contain whitespace")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise GlossaryError(f"{field} must be a valid absolute HTTPS URL") from exc

    if (
        parsed.scheme.casefold() != "https"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise GlossaryError(
            f"{field} must be an absolute HTTPS URL without credentials"
        )

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        try:
            idna.encode(hostname, uts46=True, std3_rules=True)
        except idna.IDNAError as exc:
            raise GlossaryError(f"{field} has an invalid authority host") from exc


def _parse_authority(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GlossaryError(f"{field} must be a mapping")

    unknown = set(value) - {"kind", "sources"}
    missing = {"kind", "sources"} - set(value)
    if unknown:
        raise GlossaryError(
            f"{field} contains unsupported fields: "
            + ", ".join(sorted(unknown))
        )
    if missing:
        raise GlossaryError(
            f"{field} is missing required fields: "
            + ", ".join(sorted(missing))
        )

    kind = value["kind"]
    if not isinstance(kind, str) or kind not in AUTHORITY_KINDS:
        raise GlossaryError(
            f"{field}.kind must be normative, upstream, or conventional"
        )

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
                f"{source_field} contains unsupported fields: "
                + ", ".join(sorted(unknown))
            )
        if missing:
            raise GlossaryError(
                f"{source_field} is missing required fields: "
                + ", ".join(sorted(missing))
            )

        title = _nonempty_text(raw["title"], f"{source_field}.title")
        url = _nonempty_text(raw["url"], f"{source_field}.url")
        _validate_authority_url(url, f"{source_field}.url")

        source = {"title": title, "url": url}
        for optional in ("version", "locator"):
            if optional in raw:
                source[optional] = _nonempty_text(
                    raw[optional],
                    f"{source_field}.{optional}",
                )
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
        raise GlossaryError(
            f"{field} contains unsupported fields: "
            + ", ".join(sorted(unknown))
        )

    missing = {"id", "term", "origin"} - set(raw)
    if missing:
        raise GlossaryError(
            f"{field} is missing required fields: "
            + ", ".join(sorted(missing))
        )

    term_id = _nonempty_text(raw["id"], f"{field}.id")
    if not TERM_ID.fullmatch(term_id):
        raise GlossaryError(
            f"{field}.id must use a supported glossary namespace"
        )

    term = _nonempty_text(raw["term"], f"{field}.term")
    aliases = _string_list(raw.get("aliases", []), f"{field}.aliases")
    _validate_labels(term, aliases, field)

    origin = raw["origin"]
    if not isinstance(origin, str) or origin not in ORIGINS:
        raise GlossaryError(f"{field}.origin must be repository or external")

    result: dict[str, Any] = {
        "id": term_id,
        "term": term,
        "aliases": aliases,
        "origin": origin,
    }

    if "localized_labels" in raw:
        result["localized_labels"] = _parse_localized_labels(
            raw["localized_labels"],
            f"{field}.localized_labels",
        )

    if "related_terms" in raw:
        related = _string_list(
            raw["related_terms"],
            f"{field}.related_terms",
        )
        for related_id in related:
            if not TERM_ID.fullmatch(related_id):
                raise GlossaryError(
                    f"{field}.related_terms contains an invalid term ID: "
                    f"{related_id}"
                )
            if related_id == term_id:
                raise GlossaryError(
                    f"{field}.related_terms must not reference the term itself"
                )
        result["related_terms"] = related

    if "repository_usage" in raw:
        result["repository_usage"] = _nonempty_text(
            raw["repository_usage"],
            f"{field}.repository_usage",
        )

    if "summary" in raw:
        result["summary"] = _nonempty_text(
            raw["summary"],
            f"{field}.summary",
        )

    if origin == "repository":
        if not REPOSITORY_TERM_ID.fullmatch(term_id):
            raise GlossaryError(
                f"{field}.id must start with templates- for repository terms"
            )
        if "definition" not in raw:
            raise GlossaryError(
                f"{field}.definition is required for repository terms"
            )
        if "authority" in raw:
            raise GlossaryError(
                f"{field}.authority is not allowed for repository terms"
            )
        result["definition"] = _nonempty_text(
            raw["definition"],
            f"{field}.definition",
        )
    else:
        if not EXTERNAL_TERM_ID.fullmatch(term_id):
            raise GlossaryError(
                f"{field}.id must use external-<domain>-<slug> "
                "for external terms"
            )
        if "summary" not in raw:
            raise GlossaryError(
                f"{field}.summary is required for external terms"
            )
        if "authority" not in raw:
            raise GlossaryError(
                f"{field}.authority is required for external terms"
            )
        if "definition" in raw:
            raise GlossaryError(
                f"{field}.definition is not allowed for external terms"
            )
        result["authority"] = _parse_authority(
            raw["authority"],
            f"{field}.authority",
        )

    return result


def load_glossary(path: Path) -> list[dict[str, Any]]:
    data = read_yaml(path)
    allowed = {"schema_version", "terms"}
    unknown = set(data) - allowed
    missing = allowed - set(data)
    if unknown or missing:
        details: list[str] = []
        if unknown:
            details.append("unsupported fields: " + ", ".join(sorted(unknown)))
        if missing:
            details.append("missing fields: " + ", ".join(sorted(missing)))
        raise GlossaryError(
            "glossary top level is invalid (" + "; ".join(details) + ")"
        )

    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise GlossaryError("glossary schema_version must be the integer 1")

    raw_terms = data["terms"]
    if not isinstance(raw_terms, list) or not raw_terms:
        raise GlossaryError("glossary terms must be a non-empty array")

    terms = [
        parse_term(raw, index)
        for index, raw in enumerate(raw_terms)
    ]
    counts = Counter(term["id"] for term in terms)
    duplicates = sorted(term_id for term_id, count in counts.items() if count > 1)
    if duplicates:
        raise GlossaryError(
            "glossary term IDs must be unique within a provider: "
            + ", ".join(duplicates)
        )
    return terms


def safe_relative_glossary_path(value: Any, field: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\0" in value
    ):
        raise GlossaryError(f"{field} must be a safe relative POSIX path")

    parts = value.split("/")
    if any(
        part in ("", ".", "..") or part.casefold() == ".git"
        for part in parts
    ):
        raise GlossaryError(f"{field} must be a safe relative POSIX path")

    path = PurePosixPath(value)
    if path.is_absolute() or path.suffix.lower() != ".yml":
        raise GlossaryError(f"{field} must be a safe relative .yml path")
    return path


def resolve_without_symlinks(
    root: Path,
    relative: PurePosixPath,
    field: str,
) -> Path:
    root = root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current /= part
        try:
            current.relative_to(root)
        except ValueError as exc:
            raise GlossaryError(
                f"{field} must remain within publication root"
            ) from exc
        if current.is_symlink():
            raise GlossaryError(f"{field} must not traverse a symlink")

    if not current.is_file():
        raise GlossaryError(
            f"{field} must identify an existing regular file: {relative}"
        )
    return current


def glossary_source_from_catalog(root: Path) -> PurePosixPath | None:
    path = resolve_without_symlinks(
        root,
        PurePosixPath("docs/publication-catalog.json"),
        "publication catalog",
    )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise GlossaryError(
            f"unable to read publication catalog {path}: {exc}"
        ) from exc

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GlossaryError(
                    f"publication catalog contains duplicate member: {key}"
                )
            result[key] = value
        return result

    try:
        data = json.loads(text, object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise GlossaryError(
            f"unable to parse publication catalog {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise GlossaryError("publication catalog must be an object")

    version = data.get("schema_version")
    if type(version) is not int or version != 3:
        raise GlossaryError(
            "publication catalog schema_version must be integer 3"
        )

    allowed = {"schema_version", "documents", "assets", "glossary"}
    unknown = set(data) - allowed
    if unknown:
        raise GlossaryError(
            "publication catalog contains unsupported top-level fields: "
            + ", ".join(sorted(unknown))
        )

    if "glossary" not in data:
        return None

    raw = data["glossary"]
    if not isinstance(raw, dict) or set(raw) != {"source"}:
        raise GlossaryError(
            "publication catalog glossary must contain only source"
        )

    source = safe_relative_glossary_path(raw["source"], "glossary.source")
    resolve_without_symlinks(root, source, "glossary.source")
    return source


def integrate_glossaries(
    publications: dict[str, Path],
    revisions: dict[str, str],
    repository: str,
) -> dict[str, Any]:
    if not publications:
        raise GlossaryError("at least one publication is required")
    if set(publications) != set(revisions):
        raise GlossaryError("publication and revision provider sets must match")
    if not isinstance(repository, str) or not repository.strip():
        raise GlossaryError("repository must be a non-empty string")

    terms: list[dict[str, Any]] = []
    for provider in sorted(publications):
        if not PROVIDER_NAME.fullmatch(provider):
            raise GlossaryError(f"invalid provider name: {provider}")

        revision = revisions[provider]
        if not FULL_SHA.fullmatch(revision):
            raise GlossaryError(
                f"{provider} revision must be a lowercase 40-character Git SHA"
            )

        root = publications[provider].resolve(strict=True)
        source = glossary_source_from_catalog(root)
        if source is None:
            continue

        source_path = resolve_without_symlinks(
            root,
            source,
            "glossary.source",
        )
        for term in load_glossary(source_path):
            enriched = dict(term)
            enriched["provider"] = provider
            enriched["source_path"] = source.as_posix()
            enriched["source_revision"] = revision
            terms.append(enriched)

    counts = Counter(term["id"] for term in terms)
    duplicates = sorted(term_id for term_id, count in counts.items() if count > 1)
    if duplicates:
        raise GlossaryError(
            "integrated glossary has duplicate term IDs: "
            + ", ".join(duplicates)
        )

    known = set(counts)
    unresolved = sorted(
        {
            related
            for term in terms
            for related in term.get("related_terms", [])
            if related not in known
        }
    )
    if unresolved:
        raise GlossaryError(
            "integrated glossary has unresolved related terms: "
            + ", ".join(unresolved)
        )

    terms.sort(key=lambda term: term["id"])
    return {
        "schema_version": 1,
        "repository": repository,
        "terms": terms,
    }
