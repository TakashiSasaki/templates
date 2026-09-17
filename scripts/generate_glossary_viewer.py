#!/usr/bin/env python3
"""Render the integrated glossary JSON as a static human-readable page."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
if __package__ in (None, ""):
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

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

from publication_bundle.glossary import *
from site_renderer.github import github_blob_url

PROVIDER_LABELS = {
    "site": "Site",
    "composition": "Composition",
    "policy": "Policy",
}
from publication_bundle.glossary import (
    GlossaryViewerError,
    _reject_control_characters,
    _nonempty_string,
    _string_array,
    _label_key,
    _validate_labels,
    _canonical_language_tag,
    _validate_repository,
    _validate_https_url,
    _validate_source_path,
    _parse_localized_labels,
    _parse_authority,
    _parse_term,
    load_model,
    ROOT_KEYS,
    TERM_KEYS,
    GITHUB_REPOSITORY_COMPONENT,
)




def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()




























def _join_labels(values: list[str], language: str | None = None) -> str:
    attrs = f' lang="{html.escape(language, quote=True)}"' if language else ""
    return ", ".join(
        f"<span{attrs}>{html.escape(value)}</span>" for value in values
    )


def source_url(repository: str, term: dict[str, Any]) -> str:
    repository = _validate_repository(repository)
    return github_blob_url(repository, term["source_revision"], term["source_path"])


def provider_label(provider: str) -> str:
    """Return a friendly label for known providers without inventing unknown names."""
    return PROVIDER_LABELS.get(provider, provider)




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
    provider_order = sorted(repository_providers)
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
