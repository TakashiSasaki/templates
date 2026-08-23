#!/usr/bin/env python3
"""Normalize deployment metadata in generated HTML before Pages upload."""

from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from site_chrome_locales import (
    SITE_CHROME_LOCALES,
    SiteChromeLocaleError,
    guided_copy_strings,
    load_site_chrome_locales,
)


LINK_TAG_PATTERN = re.compile(r"<link\b[^>]*>", re.IGNORECASE | re.DOTALL)
HEAD_CLOSE_PATTERN = re.compile(r"</head\s*>", re.IGNORECASE)
BODY_CLOSE_PATTERN = re.compile(r"</body\s*>", re.IGNORECASE)
HREF_ATTRIBUTE_PATTERN = re.compile(
    r"(?<![-:\w])href\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
PAGE_PATH_PATTERN = re.compile(
    r'<p class="page-path"><span class="page-path-label">Page path:</span>\s*'
    r'<code>(?P<path>[^<]+)</code></p>'
)
PAGE_PATH_ROUTE_PATTERN = re.compile(
    r'<p class="page-path"><span class="page-path-label">[^<]+</span>\s*'
    r'<code>(?P<path>[^<]+)</code></p>'
)
IMMUTABLE_GITHUB_SOURCE_PATTERN = re.compile(
    r'<a\b[^>]*\bhref="(?P<href>[^"]+)"[^>]*>\s*'
    r'immutable GitHub source\s*</a>',
    re.IGNORECASE,
)
CSP_META_PATTERN = re.compile(
    r'(?P<prefix><meta http-equiv="Content-Security-Policy" content=")'
    r'(?P<policy>[^"]*)'
    r'(?P<suffix>">)',
    re.IGNORECASE,
)
MANIFEST_HREF = "/app.webmanifest"
THEME_COLOR = "#3f51b5"
GUIDED_COPY_SCRIPT = "/javascripts/guided-copy.js"
GUIDED_COPY_SCRIPT_TAG = f'<script src="{GUIDED_COPY_SCRIPT}" defer></script>'


class SiteMetadataError(RuntimeError):
    """Raised when generated HTML metadata is ambiguous or cannot be normalized."""


class HeadElementParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str | None]] = []
        self.metas: list[dict[str, str | None]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        if tag.lower() == "link":
            self.links.append(attributes)
        elif tag.lower() == "meta":
            self.metas.append(attributes)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--canonical-url", required=True)
    parser.add_argument(
        "--site-chrome-locales",
        type=Path,
        default=SITE_CHROME_LOCALES,
    )
    return parser.parse_args()


def validate_canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.path.endswith("/")
        or parsed.query
        or parsed.fragment
    ):
        raise SiteMetadataError(
            "canonical URL must be an HTTPS directory URL without query or fragment"
        )
    return value


def validate_page_path_route(value: str, path: Path) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not value.startswith("/")
        or not value.endswith("/")
        or "\\" in value
        or "//" in value[1:]
    ):
        raise SiteMetadataError(f"{path}: invalid page path route: {value!r}")
    return value


def validate_guided_page_path(value: str, path: Path) -> str:
    validate_page_path_route(value, path)
    if not value.startswith("/guided/"):
        raise SiteMetadataError(f"{path}: invalid guided page path: {value!r}")
    return value


def validate_github_source_url(value: str, path: Path) -> str:
    parsed = urlsplit(value)
    try:
        parsed.port
    except ValueError as exc:
        raise SiteMetadataError(f"{path}: invalid immutable GitHub source URL") from exc
    parts = parsed.path.split("/")
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or len(parts) < 6
        or parts[0] != ""
        or not parts[1]
        or not parts[2]
        or parts[3] != "blob"
        or re.fullmatch(r"[0-9a-f]{40}", parts[4]) is None
        or any(not part for part in parts[5:])
    ):
        raise SiteMetadataError(f"{path}: invalid immutable GitHub source URL")
    return value


def parse_head_elements(source: str) -> HeadElementParser:
    parser = HeadElementParser()
    parser.feed(source)
    parser.close()
    return parser


def canonical_links(source: str) -> list[dict[str, str | None]]:
    return [
        link
        for link in parse_head_elements(source).links
        if "canonical" in (link.get("rel") or "").lower().split()
    ]


def manifest_links(source: str) -> list[dict[str, str | None]]:
    return [
        link
        for link in parse_head_elements(source).links
        if "manifest" in (link.get("rel") or "").lower().split()
    ]


def theme_color_metas(source: str) -> list[dict[str, str | None]]:
    return [
        meta
        for meta in parse_head_elements(source).metas
        if (meta.get("name") or "").casefold() == "theme-color"
    ]


def rewrite_canonical_link(source: str, canonical_url: str, path: Path) -> str:
    canonical_tags: list[str] = []
    for match in LINK_TAG_PATTERN.finditer(source):
        tag = match.group(0)
        if canonical_links(tag):
            canonical_tags.append(tag)
    if len(canonical_tags) > 1:
        raise SiteMetadataError(
            f"{path}: expected at most one canonical link, found {len(canonical_tags)}"
        )

    escaped_url = html.escape(canonical_url, quote=True)
    if not canonical_tags:
        head_closes = list(HEAD_CLOSE_PATTERN.finditer(source))
        if len(head_closes) != 1:
            raise SiteMetadataError(
                f"{path}: expected exactly one closing head tag, found {len(head_closes)}"
            )
        insertion = f'<link rel="canonical" href="{escaped_url}">\n'
        position = head_closes[0].start()
        updated = source[:position] + insertion + source[position:]
    else:

        def replace_tag(match: re.Match[str]) -> str:
            tag = match.group(0)
            if not canonical_links(tag):
                return tag
            replacement = f'href="{escaped_url}"'
            if HREF_ATTRIBUTE_PATTERN.search(tag) is not None:
                return HREF_ATTRIBUTE_PATTERN.sub(replacement, tag, count=1)
            closing = "/>" if tag.endswith("/>") else ">"
            return tag[: -len(closing)] + " " + replacement + closing

        updated = LINK_TAG_PATTERN.sub(replace_tag, source)

    links = canonical_links(updated)
    if len(links) != 1 or links[0].get("href") != canonical_url:
        raise SiteMetadataError(f"{path}: canonical URL normalization failed")
    return updated


def ensure_pwa_metadata(source: str, path: Path) -> str:
    manifests = manifest_links(source)
    if len(manifests) > 1:
        raise SiteMetadataError(
            f"{path}: expected at most one web app manifest link, found {len(manifests)}"
        )
    if manifests and manifests[0].get("href") != MANIFEST_HREF:
        raise SiteMetadataError(
            f"{path}: web app manifest link must target {MANIFEST_HREF}"
        )

    themes = theme_color_metas(source)
    if len(themes) > 1:
        raise SiteMetadataError(
            f"{path}: expected at most one theme-color meta element, found {len(themes)}"
        )
    if themes and themes[0].get("content") != THEME_COLOR:
        raise SiteMetadataError(f"{path}: theme-color must be {THEME_COLOR}")

    additions: list[str] = []
    if not manifests:
        additions.append(f'<link rel="manifest" href="{MANIFEST_HREF}">\n')
    if not themes:
        additions.append(f'<meta name="theme-color" content="{THEME_COLOR}">\n')
    if not additions:
        return source

    head_closes = list(HEAD_CLOSE_PATTERN.finditer(source))
    if len(head_closes) != 1:
        raise SiteMetadataError(
            f"{path}: expected exactly one closing head tag, found {len(head_closes)}"
        )
    position = head_closes[0].start()
    updated = source[:position] + "".join(additions) + source[position:]

    updated_manifests = manifest_links(updated)
    updated_themes = theme_color_metas(updated)
    if (
        len(updated_manifests) != 1
        or updated_manifests[0].get("href") != MANIFEST_HREF
        or len(updated_themes) != 1
        or updated_themes[0].get("content") != THEME_COLOR
    ):
        raise SiteMetadataError(f"{path}: PWA metadata normalization failed")
    return updated


def allow_guided_copy_script(source: str, path: Path) -> str:
    matches = list(CSP_META_PATTERN.finditer(source))
    if len(matches) != 1:
        raise SiteMetadataError(
            f"{path}: guided page must contain exactly one Content-Security-Policy meta element"
        )
    match = matches[0]
    policy = html.unescape(match.group("policy"))
    directives = [directive.strip() for directive in policy.split(";") if directive.strip()]
    script_directives = [
        directive
        for directive in directives
        if directive.split(maxsplit=1)[0].casefold() == "script-src"
    ]
    if len(script_directives) > 1:
        raise SiteMetadataError(f"{path}: duplicate script-src directives")
    if script_directives and script_directives[0] != "script-src 'self'":
        raise SiteMetadataError(
            f"{path}: guided script-src must be exactly script-src 'self'"
        )
    if not script_directives:
        directives.append("script-src 'self'")
    updated_policy = "; ".join(directives)
    escaped_policy = html.escape(updated_policy, quote=True).replace("&#x27;", "'")
    replacement = match.group("prefix") + escaped_policy + match.group("suffix")
    return source[: match.start()] + replacement + source[match.end() :]


def guided_copy_button(kind: str, url: str, strings: dict[str, str]) -> str:
    if kind not in {"github_url", "public_url"}:
        raise SiteMetadataError(f"unsupported guided copy kind: {kind}")
    name = strings[f"{kind}_name"]
    label = strings[f"copy_{kind}"]
    success = strings[f"copied_{kind}"]
    failure = strings[f"copy_failed_{kind}"]
    return (
        f'<button type="button" data-copy-name="{html.escape(name, quote=True)}" '
        f'data-copy-url="{html.escape(url, quote=True)}" '
        f'data-copy-success="{html.escape(success, quote=True)}" '
        f'data-copy-failure="{html.escape(failure, quote=True)}">'
        f"{html.escape(label)}</button>"
    )


def discover_page_path_routes(html_files: list[Path]) -> set[str]:
    """Return the public directory routes declared by generated Page path markers."""
    routes: dict[str, Path] = {}
    for path in html_files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SiteMetadataError(f"unable to read generated HTML {path}: {exc}") from exc
        matches = list(PAGE_PATH_ROUTE_PATTERN.finditer(source))
        if len(matches) > 1:
            raise SiteMetadataError(f"{path}: multiple page path markers")
        if not matches:
            continue
        route = validate_page_path_route(
            html.unescape(matches[0].group("path")),
            path,
        )
        previous = routes.get(route)
        if previous is not None:
            raise SiteMetadataError(
                f"{path}: page path route {route!r} is also declared by {previous}"
            )
        routes[route] = path
    return set(routes)


def render_page_path_breadcrumb(page_path: str, page_routes: set[str]) -> str:
    """Render Home plus only generated route prefixes as links, leaving gaps as text."""
    segments = page_path.strip("/").split("/")
    pieces = ['<a class="page-path-home" href="/" aria-label="Home">/</a><wbr>']
    prefix: list[str] = []
    for segment in segments:
        prefix.append(segment)
        target = "/" + "/".join(prefix) + "/"
        escaped_segment = html.escape(segment)
        escaped_target = html.escape(target, quote=True)
        if target == page_path:
            pieces.append(
                f'<span class="page-path-segment" aria-current="page">{escaped_segment}</span>'
            )
        elif target in page_routes:
            pieces.append(
                f'<a class="page-path-segment" href="{escaped_target}">{escaped_segment}</a>'
            )
        else:
            pieces.append(f'<span class="page-path-segment">{escaped_segment}</span>')
        pieces.append(
            '<span class="page-path-separator" aria-hidden="true">/</span><wbr>'
        )
    return "".join(pieces)


def enhance_guided_copy_controls(
    source: str,
    canonical_url: str,
    path: Path,
    copy_strings: dict[str, str],
    page_routes: set[str] | None = None,
) -> str:
    page_path_matches = list(PAGE_PATH_PATTERN.finditer(source))
    if not page_path_matches:
        return source
    if len(page_path_matches) != 1:
        raise SiteMetadataError(f"{path}: multiple guided page path markers")

    canonical_url = validate_canonical_url(canonical_url)
    page_path_match = page_path_matches[0]
    escaped_page_path = page_path_match.group("path")
    page_path = validate_guided_page_path(html.unescape(escaped_page_path), path)
    if page_routes is None:
        page_routes = {page_path}
    if page_path not in page_routes:
        raise SiteMetadataError(
            f"{path}: guided page path is not declared by a generated page: {page_path!r}"
        )
    public_url = urljoin(canonical_url, page_path.lstrip("/"))

    github_matches = list(IMMUTABLE_GITHUB_SOURCE_PATTERN.finditer(source))
    if len(github_matches) > 1:
        raise SiteMetadataError(f"{path}: multiple immutable GitHub sources")

    buttons: list[str] = []
    if github_matches:
        github_url = validate_github_source_url(
            html.unescape(github_matches[0].group("href")),
            path,
        )
        buttons.append(guided_copy_button("github_url", github_url, copy_strings))
    buttons.append(guided_copy_button("public_url", public_url, copy_strings))

    replacement = (
        '<nav class="page-path" aria-label="Page path">'
        '<span class="page-path-label">Page path:</span> '
        f'<code>{render_page_path_breadcrumb(page_path, page_routes)}</code> '
        '<span class="page-path-actions">'
        + " ".join(buttons)
        + ' <span class="copy-status" role="status" aria-live="polite"></span>'
        "</span></nav>"
    )
    updated = (
        source[: page_path_match.start()]
        + replacement
        + source[page_path_match.end() :]
    )
    updated = allow_guided_copy_script(updated, path)

    if GUIDED_COPY_SCRIPT_TAG not in updated:
        body_closes = list(BODY_CLOSE_PATTERN.finditer(updated))
        if len(body_closes) != 1:
            raise SiteMetadataError(
                f"{path}: expected exactly one closing body tag, found {len(body_closes)}"
            )
        position = body_closes[0].start()
        updated = (
            updated[:position]
            + GUIDED_COPY_SCRIPT_TAG
            + "\n"
            + updated[position:]
        )
    return updated


def generated_html_files(site_root: Path) -> tuple[Path, list[Path]]:
    resolved_root = site_root.resolve(strict=True)
    html_files = sorted(
        path for path in resolved_root.rglob("*.html") if path.is_file()
    )
    if not html_files:
        raise SiteMetadataError(f"no generated HTML files found under {resolved_root}")
    return resolved_root, html_files


def is_inline_preview(path: Path, site_root: Path) -> bool:
    relative = path.relative_to(site_root)
    return relative.parts[:2] == ("repository-trees", "previews")


def normalize_canonical_links(site_root: Path, canonical_url: str) -> int:
    canonical_url = validate_canonical_url(canonical_url)
    _, html_files = generated_html_files(site_root)

    updates: dict[Path, str] = {}
    for path in html_files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SiteMetadataError(f"unable to read generated HTML {path}: {exc}") from exc
        updates[path] = rewrite_canonical_link(source, canonical_url, path)

    for path, source in updates.items():
        path.write_text(source, encoding="utf-8")
    return len(updates)


def normalize_site_metadata(
    site_root: Path,
    canonical_url: str,
    chrome_path: Path = SITE_CHROME_LOCALES,
) -> tuple[int, int]:
    canonical_url = validate_canonical_url(canonical_url)
    chrome = load_site_chrome_locales(chrome_path)
    canonical_copy_strings = guided_copy_strings(
        chrome,
        chrome["canonical_language"],
    )
    resolved_root, html_files = generated_html_files(site_root)
    page_routes = discover_page_path_routes(html_files)

    updates: dict[Path, str] = {}
    pwa_pages = 0
    for path in html_files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SiteMetadataError(f"unable to read generated HTML {path}: {exc}") from exc
        updated = rewrite_canonical_link(source, canonical_url, path)
        if not is_inline_preview(path, resolved_root):
            updated = ensure_pwa_metadata(updated, path)
            pwa_pages += 1
        updated = enhance_guided_copy_controls(
            updated,
            canonical_url,
            path,
            canonical_copy_strings,
            page_routes,
        )
        updates[path] = updated

    for path, source in updates.items():
        path.write_text(source, encoding="utf-8")
    return len(updates), pwa_pages


def main() -> int:
    args = parse_args()
    try:
        canonical_count, pwa_count = normalize_site_metadata(
            args.site_root,
            args.canonical_url,
            args.site_chrome_locales,
        )
    except (OSError, SiteChromeLocaleError, SiteMetadataError) as exc:
        print(f"finalize_site_metadata.py: {exc}", file=sys.stderr)
        return 1
    print(
        f"normalized canonical URL in {canonical_count} generated HTML file(s) "
        f"and PWA metadata in {pwa_count} installable page(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())