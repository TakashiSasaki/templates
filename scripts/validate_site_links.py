#!/usr/bin/env python3
"""Validate local hyperlinks and fragments in a generated documentation site."""

from __future__ import annotations

import argparse
import posixpath
import sys
import tomllib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import SplitResult, unquote, urljoin, urlsplit, urlunsplit


class SiteLinkError(RuntimeError):
    """Raised when the generated site or its configuration cannot be validated."""


@dataclass(frozen=True)
class LinkReference:
    href: str
    line: int
    column: int


@dataclass(frozen=True)
class HtmlPage:
    path: Path
    relative_path: PurePosixPath
    public_url: str
    ids: frozenset[str]
    links: tuple[LinkReference, ...]


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self._all_links: list[LinkReference] = []
        self._main_links: list[LinkReference] = []
        self._main_depth = 0
        self._saw_main = False

    @property
    def links(self) -> list[LinkReference]:
        return self._main_links if self._saw_main else self._all_links

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "main":
            self._saw_main = True
            self._main_depth += 1
        self._handle_tag(tag, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        is_main = tag.lower() == "main"
        if is_main:
            self._saw_main = True
            self._main_depth += 1
        self._handle_tag(tag, attrs)
        if is_main:
            self._main_depth -= 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "main" and self._main_depth > 0:
            self._main_depth -= 1

    def _handle_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value for name, value in attrs}
        element_id = values.get("id")
        if element_id:
            self.ids.add(element_id)
        anchor_name = values.get("name")
        if tag.lower() == "a" and anchor_name:
            self.ids.add(anchor_name)
        if tag.lower() not in {"a", "area"}:
            return
        href = values.get("href")
        if href is None:
            return
        line, column = self.getpos()
        reference = LinkReference(href=href, line=line, column=column)
        self._all_links.append(reference)
        if self._main_depth > 0:
            self._main_links.append(reference)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", required=True, type=Path)
    parser.add_argument("--config-file", required=True, type=Path)
    return parser.parse_args()


def normalized_origin(parts: SplitResult, description: str) -> tuple[str, str, int]:
    scheme = parts.scheme.lower()
    hostname = parts.hostname
    if scheme not in {"http", "https"} or hostname is None:
        raise SiteLinkError(f"{description} must contain a valid HTTP or HTTPS origin")
    try:
        explicit_port = parts.port
    except ValueError as exc:
        raise SiteLinkError(f"{description} contains an invalid port") from exc
    effective_port = (
        explicit_port
        if explicit_port is not None
        else (443 if scheme == "https" else 80)
    )
    return scheme, unquote(hostname).lower(), effective_port


def load_site_url(config_file: Path) -> str:
    try:
        with config_file.open("rb") as handle:
            config = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SiteLinkError(f"Unable to read site configuration {config_file}: {exc}") from exc

    project = config.get("project")
    site_url = project.get("site_url") if isinstance(project, dict) else None
    if not isinstance(site_url, str) or not site_url.strip():
        raise SiteLinkError("Site configuration must define a non-empty project.site_url")

    parts = urlsplit(site_url.strip())
    normalized_origin(parts, "project.site_url")
    if parts.query or parts.fragment:
        raise SiteLinkError("project.site_url must not contain a query or fragment")

    path = unquote(parts.path or "/")
    if not path.startswith("/"):
        raise SiteLinkError("project.site_url must contain an absolute URL path")
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc, path, "", ""))


def canonical_public_path(relative_path: PurePosixPath, base_path: str) -> str:
    value = relative_path.as_posix()
    if value == "index.html":
        return base_path
    if value.endswith("/index.html"):
        return base_path + value[: -len("index.html")]
    return base_path + value


def aliases_for_page(relative_path: PurePosixPath, base_path: str) -> tuple[str, ...]:
    value = relative_path.as_posix()
    if value == "index.html":
        no_slash = base_path.rstrip("/") or "/"
        return tuple(dict.fromkeys((base_path, no_slash, base_path + "index.html")))
    if value.endswith("/index.html"):
        directory = base_path + value[: -len("index.html")]
        return (directory, directory.rstrip("/"), base_path + value)
    return (base_path + value,)


def normalized_public_path(encoded_path: str) -> str:
    """Decode a URL path and normalize dot segments before public-path lookup."""
    decoded_path = unquote(encoded_path)
    normalized = posixpath.normpath(decoded_path)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    if decoded_path.endswith("/") and normalized != "/":
        normalized += "/"
    return normalized


def parse_page(path: Path, site_root: Path, base_url: str) -> HtmlPage:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SiteLinkError(f"Unable to read generated HTML {path}: {exc}") from exc

    parser = PageParser()
    parser.feed(text)
    parser.close()

    relative_path = PurePosixPath(path.relative_to(site_root).as_posix())
    base_parts = urlsplit(base_url)
    public_path = canonical_public_path(relative_path, base_parts.path)
    public_url = urlunsplit(
        (base_parts.scheme, base_parts.netloc, public_path, "", "")
    )
    return HtmlPage(
        path=path,
        relative_path=relative_path,
        public_url=public_url,
        ids=frozenset(parser.ids),
        links=tuple(parser.links),
    )


def local_asset_path(site_root: Path, base_path: str, public_path: str) -> Path | None:
    if public_path == base_path.rstrip("/"):
        relative = ""
    elif public_path.startswith(base_path):
        relative = public_path[len(base_path) :]
    else:
        return None

    candidate = site_root.joinpath(*PurePosixPath(relative).parts).resolve()
    try:
        candidate.relative_to(site_root)
    except ValueError:
        return None
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate if candidate.is_file() else None


def validate_site(site_root: Path, config_file: Path) -> tuple[int, int, list[str]]:
    try:
        site_root = site_root.resolve(strict=True)
    except OSError as exc:
        raise SiteLinkError(f"Unable to resolve generated site root {site_root}: {exc}") from exc
    if not site_root.is_dir():
        raise SiteLinkError(f"Generated site root is not a directory: {site_root}")

    base_url = load_site_url(config_file)
    base_parts = urlsplit(base_url)
    base_path = base_parts.path
    origin = normalized_origin(base_parts, "project.site_url")

    html_paths = sorted(site_root.rglob("*.html"))
    if not html_paths:
        raise SiteLinkError(f"Generated site contains no HTML files: {site_root}")
    for path in site_root.rglob("*"):
        if path.is_symlink():
            raise SiteLinkError(f"Generated site must not contain symlinks: {path}")

    pages = tuple(parse_page(path, site_root, base_url) for path in html_paths)
    aliases: dict[str, HtmlPage] = {}
    for page in pages:
        for alias in aliases_for_page(page.relative_path, base_path):
            previous = aliases.get(alias)
            if previous is not None and previous.path != page.path:
                raise SiteLinkError(f"Generated pages share public URL {alias}")
            aliases[alias] = page

    diagnostics: set[str] = set()
    checked_links = 0
    for source in pages:
        for reference in source.links:
            raw = reference.href.strip()
            raw_parts = urlsplit(raw)
            if raw_parts.scheme and raw_parts.scheme.lower() not in {"http", "https"}:
                continue

            resolved = urlsplit(urljoin(source.public_url, raw))
            try:
                resolved_origin = normalized_origin(
                    resolved,
                    f"{source.relative_path}:{reference.line}:{reference.column}: "
                    f"link {reference.href!r}",
                )
            except SiteLinkError as exc:
                diagnostics.add(str(exc))
                continue
            if resolved_origin != origin:
                continue

            decoded_path = normalized_public_path(resolved.path)
            authored_local = not raw_parts.scheme and not raw_parts.netloc
            inside_site = decoded_path == base_path.rstrip("/") or decoded_path.startswith(
                base_path
            )
            if not inside_site:
                if authored_local:
                    diagnostics.add(
                        f"{source.relative_path}:{reference.line}:{reference.column}: "
                        f"{reference.href!r} resolves outside project.site_url"
                    )
                continue

            checked_links += 1
            target_page = aliases.get(decoded_path)
            target_file: Path | None = target_page.path if target_page else None
            if target_file is None:
                target_file = local_asset_path(site_root, base_path, decoded_path)
            if target_file is None:
                diagnostics.add(
                    f"{source.relative_path}:{reference.line}:{reference.column}: "
                    f"{reference.href!r} has no generated target"
                )
                continue

            decoded_fragment = unquote(resolved.fragment)
            fragment = decoded_fragment.partition(":~:")[0]
            if not fragment:
                continue
            if target_page is None:
                diagnostics.add(
                    f"{source.relative_path}:{reference.line}:{reference.column}: "
                    f"{reference.href!r} uses a fragment on a non-HTML target"
                )
                continue
            if fragment not in target_page.ids:
                diagnostics.add(
                    f"{source.relative_path}:{reference.line}:{reference.column}: "
                    f"{reference.href!r} references missing fragment {fragment!r} "
                    f"in {target_page.relative_path}"
                )

    return len(pages), checked_links, sorted(diagnostics)


def main() -> int:
    args = parse_args()
    try:
        page_count, link_count, diagnostics = validate_site(
            args.site_root, args.config_file
        )
    except SiteLinkError as exc:
        print(f"Site link validation failed: {exc}", file=sys.stderr)
        return 1

    if diagnostics:
        print("Generated site contains invalid local links:", file=sys.stderr)
        for diagnostic in diagnostics:
            print(f"- {diagnostic}", file=sys.stderr)
        return 1

    print(f"Validated {link_count} local links across {page_count} generated HTML pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
