#!/usr/bin/env python3
"""Validate local hyperlinks and fragments in a generated documentation site."""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
import tomllib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import SplitResult, unquote, urlsplit, urlunsplit

import idna


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
        values: dict[str, str | None] = {}
        for name, value in attrs:
            values.setdefault(name.lower(), value)
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


def _parse_ipv4_number(component: str) -> int | None:
    radix = 10
    digits = component
    if len(component) >= 2 and component[:2].lower() == "0x":
        radix = 16
        digits = component[2:]
    elif len(component) >= 2 and component.startswith("0"):
        radix = 8
        digits = component[1:]
    if not digits:
        return 0
    valid = {
        8: re.compile(r"^[0-7]+$"),
        10: re.compile(r"^[0-9]+$"),
        16: re.compile(r"^[0-9a-fA-F]+$"),
    }[radix]
    if not valid.fullmatch(digits):
        return None
    return int(digits, radix)


def _canonical_ipv4(hostname: str) -> str | None:
    components = hostname.split(".")
    if components and components[-1] == "":
        components.pop()
    if not components or len(components) > 4 or any(not part for part in components):
        return None
    numbers = [_parse_ipv4_number(part) for part in components]
    if any(number is None for number in numbers):
        return None
    values = [int(number) for number in numbers]
    if any(number > 255 for number in values[:-1]):
        return None
    if values[-1] >= 256 ** (5 - len(values)):
        return None
    ipv4_value = values[-1]
    for index, number in enumerate(values[:-1]):
        ipv4_value += number << (8 * (3 - index))
    return ".".join(str((ipv4_value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def _canonical_domain(hostname: str) -> str:
    mapped = idna.uts46_remap(hostname, std3_rules=False, transitional=False)
    labels: list[str] = []
    for label in mapped.split("."):
        if label.isascii():
            labels.append(label.lower())
        else:
            labels.append("xn--" + label.encode("punycode").decode("ascii").lower())
    return ".".join(labels)


def normalized_origin(parts: SplitResult, description: str) -> tuple[str, str, int]:
    scheme = parts.scheme.lower()
    hostname = parts.hostname
    if scheme not in {"http", "https"} or hostname is None:
        raise SiteLinkError(f"{description} must contain a valid HTTP or HTTPS origin")
    try:
        explicit_port = parts.port
    except ValueError as exc:
        raise SiteLinkError(f"{description} contains an invalid port") from exc
    try:
        decoded_hostname = unquote(hostname)
        if ":" in decoded_hostname:
            canonical_hostname = ipaddress.IPv6Address(decoded_hostname).compressed
        else:
            canonical_hostname = _canonical_domain(decoded_hostname)
            canonical_hostname = _canonical_ipv4(canonical_hostname) or canonical_hostname
    except (idna.IDNAError, UnicodeError, ValueError, ipaddress.AddressValueError) as exc:
        raise SiteLinkError(f"{description} contains an invalid hostname") from exc
    effective_port = (
        explicit_port
        if explicit_port is not None
        else (443 if scheme == "https" else 80)
    )
    return scheme, canonical_hostname, effective_port


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

    path = parts.path or "/"
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


_ENCODED_PATH_SEPARATOR = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
_SCHEME_PREFIX = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")
_C0_CONTROL_OR_SPACE = "".join(chr(value) for value in range(0x21))
_EMBEDDED_ASCII_URL_WHITESPACE = str.maketrans("", "", "\t\r\n")


def preprocess_url_input(raw_url: str) -> str:
    """Apply browser URL preprocessing while preserving non-ASCII whitespace."""
    return raw_url.strip(_C0_CONTROL_OR_SPACE).translate(
        _EMBEDDED_ASCII_URL_WHITESPACE
    )


def normalize_special_url_backslashes(raw_url: str) -> str:
    """Treat literal backslashes as path separators before query or fragment data."""
    boundary = len(raw_url)
    for delimiter in ("?", "#"):
        position = raw_url.find(delimiter)
        if position >= 0:
            boundary = min(boundary, position)
    return raw_url[:boundary].replace("\\", "/") + raw_url[boundary:]


def _split_reference(raw_url: str) -> tuple[str, str, str]:
    before_fragment, fragment_separator, fragment = raw_url.partition("#")
    before_query, query_separator, query = before_fragment.partition("?")
    return (
        before_query,
        query if query_separator else "",
        fragment if fragment_separator else "",
    )


def _special_absolute_parts(
    scheme: str, remainder: str, query: str, fragment: str
) -> SplitResult:
    """Parse a special-scheme authority after one or more leading slashes."""
    authority_and_path = remainder.lstrip("/")
    if not authority_and_path:
        return SplitResult(scheme, "", "", query, fragment)
    authority, separator, tail = authority_and_path.partition("/")
    path = f"/{tail}" if separator else "/"
    return SplitResult(scheme, authority, path, query, fragment)


def _combine_relative_path(base_path: str, reference_path: str) -> str:
    if reference_path.startswith("/"):
        return reference_path
    if not reference_path:
        return base_path
    base_directory = base_path[: base_path.rfind("/") + 1]
    return base_directory + reference_path


def _resolve_http_reference_normalized(
    base_parts: SplitResult,
    normalized_raw: str,
) -> tuple[SplitResult, bool]:
    """Resolve a normalized reference against an already parsed base URL."""
    reference, query, fragment = _split_reference(normalized_raw)
    base_scheme = base_parts.scheme.lower()
    scheme_match = _SCHEME_PREFIX.match(reference)
    scheme = scheme_match.group(1).lower() if scheme_match else ""

    if scheme and scheme not in {"http", "https"}:
        return SplitResult(scheme, "", reference, query, fragment), False

    if scheme:
        remainder = reference[scheme_match.end() :]
        if scheme != base_scheme:
            return _special_absolute_parts(scheme, remainder, query, fragment), False
        if remainder.startswith("//"):
            return _special_absolute_parts(scheme, remainder, query, fragment), False
        combined_path = _combine_relative_path(base_parts.path, remainder)
        return SplitResult(
            base_parts.scheme,
            base_parts.netloc,
            combined_path,
            query,
            fragment,
        ), True

    if reference.startswith("//"):
        return _special_absolute_parts(base_scheme, reference, query, fragment), False

    combined_path = _combine_relative_path(base_parts.path, reference)
    return SplitResult(
        base_parts.scheme,
        base_parts.netloc,
        combined_path,
        query,
        fragment,
    ), True


def resolve_http_reference(base_url: str, raw_url: str) -> tuple[SplitResult, bool]:
    """Resolve HTTP(S) references using browser-like special-scheme semantics."""
    return _resolve_http_reference_normalized(
        urlsplit(base_url),
        normalize_special_url_backslashes(raw_url),
    )


def _decode_path_preserving(
    encoded_path: str, protected_pattern: re.Pattern[str]
) -> str:
    protected: list[str] = []

    def preserve_delimiter(match: re.Match[str]) -> str:
        protected.append(match.group(0).upper())
        return f"\ue000{len(protected) - 1}\ue001"

    decoded = unquote(protected_pattern.sub(preserve_delimiter, encoded_path))
    for index, value in enumerate(protected):
        decoded = decoded.replace(f"\ue000{index}\ue001", value)
    return decoded


def _decode_path_without_separators(encoded_path: str) -> str:
    """Decode path data while keeping encoded separators in-segment."""
    return _decode_path_preserving(encoded_path, _ENCODED_PATH_SEPARATOR)


def _remove_dot_segments_preserving_empty(path: str) -> str:
    """Remove dot segments while preserving repeated slash separators."""
    segments = path.split("/")
    normalized_segments: list[str] = []
    for index, segment in enumerate(segments):
        if segment == ".":
            if index == len(segments) - 1:
                normalized_segments.append("")
            continue
        if segment == "..":
            if normalized_segments and not (
                len(normalized_segments) == 1 and normalized_segments[0] == ""
            ):
                normalized_segments.pop()
            if index == len(segments) - 1:
                normalized_segments.append("")
            continue
        normalized_segments.append(segment)

    normalized = "/".join(normalized_segments)
    if path.startswith("/") and not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized or ("/" if path.startswith("/") else "")


def normalized_public_path(encoded_path: str) -> str:
    """Decode URL path segments and remove dots without collapsing empty segments."""
    decoded_path = _decode_path_without_separators(encoded_path)
    return _remove_dot_segments_preserving_empty(decoded_path)


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

    if relative:
        segments = relative.split("/")
        material_segments = segments[:-1] if relative.endswith("/") else segments
        if any(segment == "" for segment in material_segments):
            return None

    requires_directory = public_path.endswith("/")
    candidate = site_root.joinpath(*PurePosixPath(relative).parts).resolve()
    try:
        candidate.relative_to(site_root)
    except ValueError:
        return None
    if requires_directory:
        if not candidate.is_dir():
            return None
        candidate = candidate / "index.html"
    elif candidate.is_dir():
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
    base_path = normalized_public_path(base_parts.path)
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
        if not source.links:
            continue
        source_parts = urlsplit(source.public_url)
        for reference in source.links:
            raw = preprocess_url_input(reference.href)
            normalized_raw = normalize_special_url_backslashes(raw)
            raw_parts = urlsplit(normalized_raw)
            if raw_parts.scheme and raw_parts.scheme.lower() not in {"http", "https"}:
                continue

            resolved, authored_local = _resolve_http_reference_normalized(
                source_parts,
                normalized_raw,
            )
            if authored_local:
                # Local references are constructed with the source page's scheme and
                # authority, which in turn come from the already validated Site URL.
                # Re-normalizing that inherited origin for every local link repeats
                # IDNA/IP parsing without adding a new trust boundary.
                resolved_origin = origin
            else:
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
