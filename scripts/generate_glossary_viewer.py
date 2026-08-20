#!/usr/bin/env python3
"""Render the integrated glossary JSON as a static human-readable page."""

from __future__ import annotations

import argparse
import html
import ipaddress
import json
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit

import idna

try:
    from scripts.glossary import (
        ALLOWED_TEXT_CONTROLS,
        AUTHORITY_KINDS,
        EXTERNAL_TERM_ID,
        FULL_SHA,
        LANGUAGE_TAG,
        PROVIDER_NAME,
        REPOSITORY_TERM_ID,
        TERM_ID,
    )
except ModuleNotFoundError:
    from glossary import (  # type: ignore[no-redef]
        ALLOWED_TEXT_CONTROLS,
        AUTHORITY_KINDS,
        EXTERNAL_TERM_ID,
        FULL_SHA,
        LANGUAGE_TAG,
        PROVIDER_NAME,
        REPOSITORY_TERM_ID,
        TERM_ID,
    )

PROVIDER_ORDER = ("site", "composition", "policy")
PROVIDER_LABELS = {
    "site": "Site",
    "composition": "Composition",
    "policy": "Policy",
}
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


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


def source_url(repository: str, term: dict[str, Any]) -> str:
    repository = _validate_repository(repository)
    owner, name = repository.split("/", 1)
    source = "/".join(
        quote(part, safe="") for part in term["source_path"].split("/")
    )
    return (
        f"https://github.com/{quote(owner, safe='')}/{quote(name, safe='')}/blob/"
        f"{term['source_revision']}/{source}"
    )


def provider_label(provider: str) -> str:
    """Return a friendly label for known providers without inventing unknown names."""
    return PROVIDER_LABELS.get(provider, provider)


def _join_labels(values: list[str], language: str | None = None) -> str:
    attrs = f' lang="{html.escape(language, quote=True)}"' if language else ""
    return ", ".join(
        f"<span{attrs}>{html.escape(value)}</span>" for value in values
    )


def render_localized_labels(term: dict[str, Any]) -> str:
    rows: list[str] = []
    for language, labels in term.get("localized_labels", {}).items():
        aliases = labels["aliases"]
        alias_html = ""
        if aliases:
            alias_html = (
                '<span class="localized-aliases">aliases: '
                + _join_labels(aliases, language)
                + "</span>"
            )
        rows.append(
            '<p class="localized-label">'
            f'<span class="language-tag">{html.escape(language)}</span> '
            f'<strong lang="{html.escape(language, quote=True)}">'
            f'{html.escape(labels["term"])}</strong>{alias_html}</p>'
        )
    return "".join(rows)


def render_authority(term: dict[str, Any]) -> str:
    authority = term.get("authority")
    if not authority:
        return ""
    items = []
    for source in authority["sources"]:
        details = [source.get("version"), source.get("locator")]
        suffix = " · ".join(html.escape(value) for value in details if value)
        if suffix:
            suffix = f' <span class="authority-detail">{suffix}</span>'
        items.append(
            '<li><a href="'
            + html.escape(source["url"], quote=True)
            + '" target="_blank" rel="noopener">'
            + html.escape(source["title"])
            + "</a>"
            + suffix
            + "</li>"
        )
    return (
        '<div class="authority"><p><strong>External authority:</strong> '
        f'<span class="badge">{html.escape(authority["kind"])}</span></p>'
        f'<ul>{"".join(items)}</ul></div>'
    )


def render_related(term: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> str:
    related = term.get("related_terms", [])
    if not related:
        return ""
    links = ", ".join(
        f'<a href="#{html.escape(term_id, quote=True)}">'
        f'{html.escape(by_id[term_id]["term"])}</a>'
        for term_id in related
    )
    return f'<p class="term-related"><strong>Related:</strong> {links}</p>'


def render_term(
    repository: str,
    term: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    *,
    heading_level: int,
) -> str:
    if heading_level not in {3, 4}:
        raise GlossaryViewerError("term heading level must be 3 or 4")
    aliases_html = ""
    if term["aliases"]:
        aliases_html = (
            '<p class="term-aliases"><strong>English aliases:</strong> '
            + _join_labels(term["aliases"])
            + "</p>"
        )
    if term["origin"] == "repository":
        explanation_html = (
            '<p class="term-definition">'
            + html.escape(term["definition"])
            + "</p>"
        )
        if "summary" in term:
            explanation_html += (
                '<p class="term-summary"><strong>Summary:</strong> '
                + html.escape(term["summary"])
                + "</p>"
            )
    else:
        explanation_html = (
            '<p class="term-definition">'
            + html.escape(term["summary"])
            + "</p>"
        )
    usage = ""
    if "repository_usage" in term:
        usage = (
            '<p class="repository-usage"><strong>Repository usage:</strong> '
            + html.escape(term["repository_usage"])
            + "</p>"
        )
    immutable = source_url(repository, term)
    origin_label = (
        "Templates-defined" if term["origin"] == "repository" else "External"
    )
    heading = f"h{heading_level}"
    return (
        f'<article class="term-card" id="{html.escape(term["id"], quote=True)}">'
        '<header class="term-header"><div>'
        f'<{heading}>{html.escape(term["term"])}</{heading}>'
        f'{render_localized_labels(term)}</div>'
        '<div class="term-badges">'
        f'<span class="badge">{origin_label}</span>'
        f'<span class="badge">{html.escape(provider_label(term["provider"]))}</span>'
        '</div></header>'
        f'{explanation_html}{aliases_html}{usage}'
        f'{render_related(term, by_id)}{render_authority(term)}'
        '<details class="provenance"><summary>Source and stable identity</summary>'
        f'<p><strong>Term ID:</strong> <code>{html.escape(term["id"])}</code></p>'
        f'<p><strong>Owner/curator:</strong> <code>{html.escape(term["provider"])}</code></p>'
        f'<p><strong>Source:</strong> <a href="{html.escape(immutable, quote=True)}" '
        'target="_blank" rel="noopener">'
        f'<code>{html.escape(term["source_path"])}</code> at '
        f'{html.escape(term["source_revision"][:12])}</a></p>'
        '</details></article>'
    )


def page_shell(title: str, body: str) -> str:
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; manifest-src 'self'; base-uri 'none'; form-action 'none'">
<title>{html.escape(title)} · Templates Documentation Portal</title>
<style>
:root{{color-scheme:light dark;font-family:system-ui,sans-serif}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:Canvas;color:CanvasText}}a{{color:LinkText}}code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}}main{{max-width:76rem;margin:0 auto;padding:1.5rem 1rem 4rem}}.portal-link{{display:inline-block;margin-bottom:1rem;font-size:.9rem}}.glossary-path{{margin:0 0 1rem;padding:.5rem .7rem;border:1px solid color-mix(in srgb,CanvasText 16%,transparent);border-radius:.55rem;background:color-mix(in srgb,CanvasText 3%,Canvas);font-size:.86rem}}.glossary-path-label{{font-weight:650;margin-right:.25rem}}.eyebrow{{margin-bottom:.35rem;font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;opacity:.65}}h1{{margin:0;font-size:clamp(2rem,7vw,3.4rem);letter-spacing:-.035em}}.lead{{max-width:58rem;font-size:1.05rem;line-height:1.65}}.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));gap:.65rem;margin:1.25rem 0}}.summary-card{{padding:.85rem 1rem;border:1px solid color-mix(in srgb,CanvasText 16%,transparent);border-radius:.7rem;background:color-mix(in srgb,CanvasText 2.5%,Canvas)}}.summary-card strong{{display:block;font-size:1.4rem}}.jump-links{{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0 2rem}}.jump-links a{{display:inline-block;border:1px solid color-mix(in srgb,CanvasText 18%,transparent);border-radius:999px;padding:.35rem .65rem;text-decoration:none}}.glossary-section{{margin-top:2.5rem}}.section-intro{{max-width:58rem;margin-top:0;opacity:.8;line-height:1.55}}.provider-section{{margin-top:1.7rem}}.term-list{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,25rem),1fr));gap:.85rem}}.term-card{{scroll-margin-top:1rem;border:1px solid color-mix(in srgb,CanvasText 16%,transparent);border-radius:.75rem;padding:1rem;background:color-mix(in srgb,CanvasText 2%,Canvas)}}.term-header{{display:flex;align-items:flex-start;justify-content:space-between;gap:.75rem}}.term-header h3,.term-header h4{{margin:0;font-size:1.18rem}}.term-badges{{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:.3rem}}.badge{{display:inline-block;border:1px solid color-mix(in srgb,CanvasText 20%,transparent);border-radius:999px;padding:.08rem .45rem;font-size:.72rem;white-space:nowrap}}.localized-label{{margin:.28rem 0 0;font-size:.9rem}}.language-tag{{display:inline-block;margin-right:.25rem;font:.7rem/1.5 ui-monospace,monospace;opacity:.6}}.localized-aliases{{display:block;margin-top:.15rem;font-size:.78rem;opacity:.72}}.term-definition{{margin:.8rem 0;line-height:1.55}}.term-summary{{margin:-.25rem 0 .8rem;font-size:.9rem;line-height:1.5;opacity:.86}}.term-aliases,.repository-usage,.term-related{{margin:.5rem 0;font-size:.88rem;line-height:1.45}}.authority{{margin-top:.75rem;padding-top:.6rem;border-top:1px solid color-mix(in srgb,CanvasText 12%,transparent);font-size:.86rem}}.authority ul{{margin:.4rem 0 0;padding-left:1.2rem}}.provenance{{margin-top:.8rem;font-size:.78rem;opacity:.8}}@media(max-width:600px){{main{{padding:1rem .75rem 3rem}}.term-header{{display:block}}.term-badges{{justify-content:flex-start;margin-top:.55rem}}.term-list{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main><a class="portal-link" href="/">← Documentation portal</a><p class="glossary-path"><span class="glossary-path-label">Page path:</span> <code>/glossary/</code></p>{body}</main></body>
</html>'''


def render(model: dict[str, Any]) -> str:
    terms = model["terms"]
    by_id = {term["id"]: term for term in terms}
    repository_terms = [term for term in terms if term["origin"] == "repository"]
    external_terms = [term for term in terms if term["origin"] == "external"]
    japanese_terms = sum(
        any(
            language.casefold() == "ja" or language.casefold().startswith("ja-")
            for language in term.get("localized_labels", {})
        )
        for term in terms
    )
    repository_providers = {term["provider"] for term in repository_terms}
    provider_order = [
        provider for provider in PROVIDER_ORDER if provider in repository_providers
    ] + sorted(repository_providers - set(PROVIDER_ORDER))
    provider_sections = []
    for provider in provider_order:
        owned = sorted(
            (term for term in repository_terms if term["provider"] == provider),
            key=lambda term: (term["term"].casefold(), term["id"]),
        )
        cards = "".join(
            render_term(
                model["repository"], term, by_id, heading_level=4
            )
            for term in owned
        )
        provider_sections.append(
            f'<section class="provider-section" id="provider-{html.escape(provider, quote=True)}">'
            f'<h3>{html.escape(provider_label(provider))}</h3>'
            f'<div class="term-list">{cards}</div></section>'
        )
    external_cards = "".join(
        render_term(model["repository"], term, by_id, heading_level=3)
        for term in sorted(
            external_terms,
            key=lambda term: (term["term"].casefold(), term["id"]),
        )
    )
    body = f'''<p class="eyebrow">Shared terminology</p><h1>Glossary</h1><p class="lead">English terms and definitions are canonical. Japanese labels shown here are lexical lookup aids that resolve to the same stable concept; they are not translated definitions. Repository-defined terminology is separated from externally defined general terminology so semantic ownership remains explicit.</p><div class="summary-grid" aria-label="Glossary summary"><div class="summary-card"><strong>{len(terms)}</strong>total concepts</div><div class="summary-card"><strong>{len(repository_terms)}</strong>Templates-defined</div><div class="summary-card"><strong>{len(external_terms)}</strong>externally defined</div><div class="summary-card"><strong>{japanese_terms}</strong>with Japanese labels</div></div><nav class="jump-links" aria-label="Glossary sections"><a href="#repository-terms">Templates-defined terms</a><a href="#external-terms">External terms</a><a href="/glossary/index.json">Machine-readable JSON</a></nav><section class="glossary-section" id="repository-terms"><h2>Templates-defined terms</h2><p class="section-intro">These meanings are defined by this repository. The provider shown on each card owns the canonical concept; Site only integrates the read model.</p>{''.join(provider_sections)}</section><section class="glossary-section" id="external-terms"><h2>Externally defined terms</h2><p class="section-intro">These concepts are not redefined by Templates. The local summary explains repository usage while the listed external authority remains the semantic source.</p><div class="term-list">{external_cards}</div></section>'''
    return page_shell("Glossary", body)


def generate(input_path: Path, output_path: Path) -> None:
    """Render input into output; the output parent must already be a directory."""
    model = load_model(input_path)
    parent = output_path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise GlossaryViewerError(
            "output parent must be an existing regular directory"
        )
    if output_path.is_symlink() or (
        output_path.exists() and not output_path.is_file()
    ):
        raise GlossaryViewerError("output must be a regular file path")
    try:
        same_file = input_path.resolve(strict=True) == output_path.resolve(strict=False)
        if not same_file and output_path.exists():
            same_file = input_path.samefile(output_path)
    except OSError as exc:
        raise GlossaryViewerError(
            f"unable to compare glossary viewer input and output paths: {exc}"
        ) from exc
    if same_file:
        raise GlossaryViewerError(
            "input and output must refer to different files"
        )
    try:
        output_path.write_text(render(model), encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise GlossaryViewerError(
            f"unable to write glossary viewer {output_path}: {exc}"
        ) from exc


def main() -> int:
    args = parse_args()
    try:
        generate(args.input, args.output)
    except GlossaryViewerError as exc:
        print(f"generate_glossary_viewer.py: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
