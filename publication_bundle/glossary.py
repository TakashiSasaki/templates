"""Public integrated glossary record validation."""
from __future__ import annotations
import ipaddress
import json
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit
import idna

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


ALLOWED_TEXT_CONTROLS = {"\t", "\n", "\r"}

ROOT_KEYS = {"schema_version", "repository", "terms"}


TERM_KEYS = {
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
    "provider",
    "source_path",
    "source_revision",
}


GITHUB_REPOSITORY_COMPONENT = re.compile(r"\A[A-Za-z0-9_.-]+\Z")


class GlossaryViewerError(RuntimeError):
    """Raised when integrated glossary data cannot be rendered safely."""


def _reject_control_characters(value: str, field: str) -> None:
    for char in value:
        if (
            unicodedata.category(char) == "Cc"
            and char not in ALLOWED_TEXT_CONTROLS
        ):
            raise GlossaryViewerError(
                f"{field} contains a disallowed control character"
            )


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GlossaryViewerError(f"{field} must be a non-empty string")
    _reject_control_characters(value, field)
    return value


def _string_array(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise GlossaryViewerError(f"{field} must be an array")
    result = [
        _nonempty_string(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    ]
    if len(set(result)) != len(result):
        raise GlossaryViewerError(f"{field} must not contain duplicates")
    return result


def _label_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _validate_labels(term: str, aliases: list[str], field: str) -> None:
    normalized = [_label_key(value) for value in (term, *aliases)]
    if len(set(normalized)) != len(normalized):
        raise GlossaryViewerError(f"{field} contains duplicate labels")


def _canonical_language_tag(value: str) -> str:
    parts = value.split("-")
    canonical = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            canonical.append(part.title())
        elif (len(part) == 2 and part.isalpha()) or (
            len(part) == 3 and part.isdigit()
        ):
            canonical.append(part.upper())
        else:
            canonical.append(part.lower())
    return "-".join(canonical)


def _validate_repository(value: Any) -> str:
    repository = _nonempty_string(value, "repository")
    if repository.count("/") != 1:
        raise GlossaryViewerError("repository must use owner/name form")
    owner, name = repository.split("/", 1)
    for component in (owner, name):
        if (
            component in {".", ".."}
            or GITHUB_REPOSITORY_COMPONENT.fullmatch(component) is None
        ):
            raise GlossaryViewerError(
                "repository must use safe owner/name path segments"
            )
    return repository


def _validate_https_url(value: Any, field: str) -> str:
    url = _nonempty_string(value, field)
    if any(char.isspace() for char in url):
        raise GlossaryViewerError(f"{field} must be a valid HTTPS URL")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise GlossaryViewerError(f"{field} must be a valid HTTPS URL") from exc
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise GlossaryViewerError(f"{field} must be a valid HTTPS URL")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        try:
            idna.encode(hostname, uts46=True, std3_rules=True)
        except idna.IDNAError as exc:
            raise GlossaryViewerError(
                f"{field} must have a valid authority host"
            ) from exc
    return url


def _validate_source_path(value: Any, field: str) -> str:
    source = _nonempty_string(value, field)
    if "\\" in source or ":" in source or "\0" in source:
        raise GlossaryViewerError(f"{field} must be a safe relative .yml path")
    parts = source.split("/")
    if any(
        part in {"", ".", ".."} or part.casefold() == ".git"
        for part in parts
    ):
        raise GlossaryViewerError(f"{field} must be a safe relative .yml path")
    path = PurePosixPath(source)
    if path.is_absolute() or path.suffix.lower() != ".yml":
        raise GlossaryViewerError(f"{field} must be a safe relative .yml path")
    return source


def _parse_localized_labels(value: Any, field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise GlossaryViewerError(f"{field} must be a non-empty object")
    result: dict[str, dict[str, Any]] = {}
    normalized_languages: set[str] = set()
    for language, raw in value.items():
        if not isinstance(language, str) or LANGUAGE_TAG.fullmatch(language) is None:
            raise GlossaryViewerError(
                f"{field} contains an invalid language tag: {language}"
            )
        canonical_language = _canonical_language_tag(language)
        normalized_language = canonical_language.casefold()
        if normalized_language in normalized_languages:
            raise GlossaryViewerError(
                f"{field} contains duplicate language tags ignoring case: {language}"
            )
        normalized_languages.add(normalized_language)
        if normalized_language == "en" or normalized_language.startswith("en-"):
            raise GlossaryViewerError(
                f"{field} must not redefine canonical English labels"
            )
        if not isinstance(raw, dict) or set(raw) != {"term", "aliases"}:
            raise GlossaryViewerError(
                f"{field}.{language} must contain exactly term and aliases"
            )
        preferred = _nonempty_string(raw["term"], f"{field}.{language}.term")
        aliases = _string_array(raw["aliases"], f"{field}.{language}.aliases")
        _validate_labels(preferred, aliases, f"{field}.{language}")
        result[canonical_language] = {"term": preferred, "aliases": aliases}
    return result


def _parse_authority(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"kind", "sources"}:
        raise GlossaryViewerError(f"{field} must contain exactly kind and sources")
    kind = _nonempty_string(value["kind"], f"{field}.kind")
    if kind not in AUTHORITY_KINDS:
        raise GlossaryViewerError(
            f"{field}.kind must be normative, upstream, or conventional"
        )
    raw_sources = value["sources"]
    if not isinstance(raw_sources, list) or not raw_sources:
        raise GlossaryViewerError(f"{field}.sources must be a non-empty array")
    sources: list[dict[str, str]] = []
    for index, raw in enumerate(raw_sources):
        source_field = f"{field}.sources[{index}]"
        if not isinstance(raw, dict):
            raise GlossaryViewerError(f"{source_field} must be an object")
        allowed = {"title", "url", "version", "locator"}
        if set(raw) - allowed or not {"title", "url"} <= set(raw):
            raise GlossaryViewerError(f"{source_field} has invalid fields")
        source = {
            "title": _nonempty_string(raw["title"], f"{source_field}.title"),
            "url": _validate_https_url(raw["url"], f"{source_field}.url"),
        }
        for optional in ("version", "locator"):
            if optional in raw:
                source[optional] = _nonempty_string(
                    raw[optional], f"{source_field}.{optional}"
                )
        sources.append(source)
    return {"kind": kind, "sources": sources}


def _parse_term(raw: Any, index: int) -> dict[str, Any]:
    field = f"terms[{index}]"
    if not isinstance(raw, dict):
        raise GlossaryViewerError(f"{field} must be an object")
    required = {
        "id", "term", "aliases", "origin", "provider", "source_path",
        "source_revision",
    }
    if set(raw) - TERM_KEYS or required - set(raw):
        raise GlossaryViewerError(f"{field} has invalid fields")

    term_id = _nonempty_string(raw["id"], f"{field}.id")
    if TERM_ID.fullmatch(term_id) is None:
        raise GlossaryViewerError(f"{field}.id is invalid")
    preferred = _nonempty_string(raw["term"], f"{field}.term")
    aliases = _string_array(raw["aliases"], f"{field}.aliases")
    _validate_labels(preferred, aliases, field)
    origin = _nonempty_string(raw["origin"], f"{field}.origin")
    if origin not in {"repository", "external"}:
        raise GlossaryViewerError(f"{field}.origin is invalid")
    provider = _nonempty_string(raw["provider"], f"{field}.provider")
    if PROVIDER_NAME.fullmatch(provider) is None:
        raise GlossaryViewerError(f"{field}.provider is invalid")
    revision = _nonempty_string(raw["source_revision"], f"{field}.source_revision")
    if FULL_SHA.fullmatch(revision) is None:
        raise GlossaryViewerError(f"{field}.source_revision is invalid")

    result: dict[str, Any] = {
        "id": term_id,
        "term": preferred,
        "aliases": aliases,
        "origin": origin,
        "provider": provider,
        "source_path": _validate_source_path(
            raw["source_path"], f"{field}.source_path"
        ),
        "source_revision": revision,
    }
    for optional in ("definition", "summary", "repository_usage"):
        if optional in raw:
            result[optional] = _nonempty_string(raw[optional], f"{field}.{optional}")
    if "localized_labels" in raw:
        result["localized_labels"] = _parse_localized_labels(
            raw["localized_labels"], f"{field}.localized_labels"
        )
    if "related_terms" in raw:
        related = _string_array(raw["related_terms"], f"{field}.related_terms")
        for related_id in related:
            if TERM_ID.fullmatch(related_id) is None:
                raise GlossaryViewerError(
                    f"{field}.related_terms contains an invalid term ID: {related_id}"
                )
            if related_id == term_id:
                raise GlossaryViewerError(
                    f"{field}.related_terms must not reference the term itself"
                )
        result["related_terms"] = related
    if "authority" in raw:
        result["authority"] = _parse_authority(
            raw["authority"], f"{field}.authority"
        )

    if origin == "repository":
        if REPOSITORY_TERM_ID.fullmatch(term_id) is None:
            raise GlossaryViewerError(
                f"{field}.id must start with templates- for repository terms"
            )
        if "definition" not in result:
            raise GlossaryViewerError(f"{field}.definition is required")
        if "authority" in result:
            raise GlossaryViewerError(
                f"{field}.authority is not allowed for repository terms"
            )
    else:
        if EXTERNAL_TERM_ID.fullmatch(term_id) is None:
            raise GlossaryViewerError(
                f"{field}.id must use external-<domain>-<slug> for external terms"
            )
        if "summary" not in result or "authority" not in result:
            raise GlossaryViewerError(
                f"{field} external terms require summary and authority"
            )
        if "definition" in result:
            raise GlossaryViewerError(
                f"{field}.definition is not allowed for external terms"
            )
    return result


def load_model(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise GlossaryViewerError(f"input must be a regular file: {path}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GlossaryViewerError(
                    f"input contains duplicate JSON member: {key}"
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlossaryViewerError(
            f"unable to read glossary JSON {path}: {exc}"
        ) from exc
    if not isinstance(value, dict) or set(value) != ROOT_KEYS:
        raise GlossaryViewerError("glossary JSON has invalid top-level fields")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise GlossaryViewerError("glossary JSON schema_version must be integer 1")
    repository = _validate_repository(value["repository"])
    raw_terms = value["terms"]
    if not isinstance(raw_terms, list):
        raise GlossaryViewerError("glossary JSON terms must be an array")
    terms = [_parse_term(raw, index) for index, raw in enumerate(raw_terms)]
    ids = [term["id"] for term in terms]
    if len(ids) != len(set(ids)):
        raise GlossaryViewerError("glossary JSON term IDs must be unique")
    known = set(ids)
    for term in terms:
        for related in term.get("related_terms", []):
            if related not in known:
                raise GlossaryViewerError(
                    f"term {term['id']} references unknown related term {related}"
                )
    return {"schema_version": 1, "repository": repository, "terms": terms}



