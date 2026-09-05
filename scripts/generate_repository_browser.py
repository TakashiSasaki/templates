#!/usr/bin/env python3
"""Generate a standalone static browser for immutable repository revisions."""

from __future__ import annotations

import argparse
import hashlib
import html
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_from_bytes

from pygments import lex
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

try:
    from scripts.generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        TreeEntry,
        build_tree,
        checked_revision,
        display_bytes,
        entry_label,
        read_entries,
    )
    from scripts.generate_repository_file_previews import (
        BIDIRECTIONAL_CONTROLS,
        RepositoryFilePreviewError,
        object_contents,
        object_sizes,
    )
except ModuleNotFoundError:
    from generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        TreeEntry,
        build_tree,
        checked_revision,
        display_bytes,
        entry_label,
        read_entries,
    )
    from generate_repository_file_previews import (
        BIDIRECTIONAL_CONTROLS,
        RepositoryFilePreviewError,
        object_contents,
        object_sizes,
    )


BRANCH_ORDER = ("site", "composition", "policy")
MAX_TEXT_BYTES = 1024 * 1024
MAX_TOTAL_TEXT_BYTES = 64 * 1024 * 1024
BROWSER_ROOT = Path("files")
MANAGED_MARKER = ".repository-browser-root"
MANAGED_MARKER_CONTENT = "managed by scripts/generate_repository_browser.py\n"
CONTROLLER_NAME = "repository-browser.js"
CONTROLLER_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "javascripts"
    / CONTROLLER_NAME
)


class RepositoryBrowserError(RuntimeError):
    """Raised when the static repository browser cannot be generated safely."""


@dataclass(frozen=True)
class FileRecord:
    path: bytes
    object_id: str
    size: int
    viewer_url: str
    source_url: str
    viewable: bool
    reason: str | None
    text: str | None


def decode_browser_text(content: bytes) -> tuple[str | None, str | None]:
    if len(content) > MAX_TEXT_BYTES:
        return None, f"larger than {MAX_TEXT_BYTES // 1024} KiB browser limit"
    if b"\0" in content:
        return None, "binary content (NUL byte)"
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None, "not strict UTF-8 text"
    for character in text:
        value = ord(character)
        if (
            (value < 32 and character not in "\t\n\f\r")
            or value == 127
            or character in BIDIRECTIONAL_CONTROLS
        ):
            return None, "contains disallowed control characters"
    return text, None


def source_url(repository: str, revision: str, path: bytes) -> str:
    suffix = quote_from_bytes(path, safe="/")
    return f"https://github.com/{repository}/blob/{revision}/{suffix}"


def viewer_relative_url(branch: str, revision: str, path: bytes) -> str:
    digest = hashlib.sha256(
        branch.encode("ascii") + b"\0" + revision.encode("ascii") + b"\0" + path
    ).hexdigest()
    return f"content/{digest}.html"


def collect_records(
    branch: str,
    repository: str,
    revision: str,
    root: Path,
) -> tuple[TreeEntry, dict[bytes, FileRecord]]:
    entries = read_entries(root)
    tree = build_tree(entries)
    regular = [entry for entry in entries if entry_label(entry) == "file"]
    sizes = object_sizes(root, (entry.object_id for entry in regular))
    candidates = [
        entry for entry in regular if sizes[entry.object_id] <= MAX_TEXT_BYTES
    ]
    contents = object_contents(root, (entry.object_id for entry in candidates))
    total = sum(len(contents[entry.object_id]) for entry in candidates)
    if total > MAX_TOTAL_TEXT_BYTES:
        raise RepositoryBrowserError(
            f"{branch} text candidates exceed "
            f"{MAX_TOTAL_TEXT_BYTES // (1024 * 1024)} MiB"
        )

    records: dict[bytes, FileRecord] = {}
    for entry in regular:
        size = sizes[entry.object_id]
        text: str | None = None
        reason: str | None
        if size > MAX_TEXT_BYTES:
            reason = f"larger than {MAX_TEXT_BYTES // 1024} KiB browser limit"
        else:
            text, reason = decode_browser_text(contents[entry.object_id])
        records[entry.path] = FileRecord(
            path=entry.path,
            object_id=entry.object_id,
            size=size,
            viewer_url=viewer_relative_url(branch, revision, entry.path),
            source_url=source_url(repository, revision, entry.path),
            viewable=text is not None,
            reason=reason,
            text=text,
        )
    return tree, records


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


def branch_nav(active: str, prefix: str = "") -> str:
    links = []
    for branch in BRANCH_ORDER:
        href = f"{prefix}{branch}/"
        current = ' aria-current="page"' if branch == active else ""
        links.append(
            f'<a class="branch-tab" href="{href}"{current}>'
            f"{html.escape(branch)}</a>"
        )
    return "\n".join(links)


def render_tree_entry(
    entry: TreeEntry,
    records: dict[bytes, FileRecord],
    depth: int,
) -> list[str]:
    indent = "  " * depth
    label = html.escape(display_bytes(entry.name), quote=False)
    if entry.is_directory:
        values = [
            f"{indent}<details>",
            f'{indent}  <summary><span class="tree-icon">▸</span>'
            f"<code>{label}/</code></summary>",
            f"{indent}  <ul>",
        ]
        for child in sorted(
            entry.children.values(),
            key=lambda item: (not item.is_directory, item.name),
        ):
            values.append(f"{indent}    <li>")
            values.extend(render_tree_entry(child, records, depth + 3))
            values.append(f"{indent}    </li>")
        values.extend([f"{indent}  </ul>", f"{indent}</details>"])
        return values

    kind = entry_label(entry)
    if kind != "file":
        suffix = html.escape(kind)
        return [
            f'{indent}<span class="tree-disabled"><code>{label}</code> '
            f"<small>{suffix}</small></span>"
        ]

    record = records[entry.path]
    display_path = display_bytes(entry.path)
    title = html.escape(
        f"{display_path} — {human_size(record.size)}",
        quote=True,
    )
    data_path = html.escape(display_path, quote=True)
    viewer = html.escape(record.viewer_url, quote=True)
    source = html.escape(record.source_url, quote=True)
    state = "" if record.viewable else " tree-file--fallback"
    return [
        f'{indent}<span class="tree-file-row">'
        f'<a class="tree-file{state}" href="{viewer}" '
        f'target="repository-file-viewer" title="{title}" '
        f'data-repository-file data-file-path="{data_path}"><code>{label}</code></a>'
        f'<a class="tree-source" href="{source}" target="_blank" rel="noopener" '
        f'title="Open immutable GitHub source for {title}" '
        f'aria-label="Open immutable GitHub source for {title}">↗</a>'
        f"</span>"
    ]


def render_browser_page(
    branch: str,
    revision: str,
    tree: TreeEntry,
    records: dict[bytes, FileRecord],
) -> str:
    items: list[str] = []
    for child in sorted(
        tree.children.values(),
        key=lambda item: (not item.is_directory, item.name),
    ):
        items.append("      <li>")
        items.extend(render_tree_entry(child, records, 4))
        items.append("      </li>")
    viewable = sum(record.viewable for record in records.values())
    total = len(records)
    escaped_revision = html.escape(revision, quote=False)
    placeholder = html.escape(
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<style>body{font-family:system-ui,sans-serif;padding:1rem;"
        "color-scheme:light dark}</style>"
        "<p>Select a file from the tree.</p></html>",
        quote=True,
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src 'self'; script-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{html.escape(branch)} files · templates</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: Canvas; color: CanvasText; }}
.browser {{ display: grid; grid-template-columns: minmax(18rem, 30vw) 1fr; min-height: 100vh; }}
aside {{ min-width: 0; border-right: 1px solid color-mix(in srgb, CanvasText 22%, transparent); display: flex; flex-direction: column; max-height: 100vh; }}
.browser-header {{ padding: .85rem 1rem .65rem; border-bottom: 1px solid color-mix(in srgb, CanvasText 18%, transparent); }}
.browser-header h1 {{ margin: 0 0 .35rem; font-size: 1rem; }}
.browser-meta {{ margin: 0; font: .74rem/1.35 ui-monospace, SFMono-Regular, Consolas, monospace; opacity: .72; overflow-wrap: anywhere; }}
.branch-tabs {{ display: flex; gap: .35rem; padding: .65rem 1rem; overflow-x: auto; border-bottom: 1px solid color-mix(in srgb, CanvasText 18%, transparent); }}
.branch-tab {{ border: 1px solid color-mix(in srgb, CanvasText 24%, transparent); border-radius: 999px; padding: .28rem .62rem; text-decoration: none; color: inherit; font: .78rem/1.2 ui-monospace, SFMono-Regular, Consolas, monospace; }}
.branch-tab[aria-current="page"] {{ background: color-mix(in srgb, CanvasText 10%, Canvas); font-weight: 700; }}
.tree {{ overflow: auto; padding: .7rem .65rem 1.5rem; flex: 1; }}
.tree ul {{ list-style: none; margin: 0; padding-left: .9rem; }}
.tree > ul {{ padding-left: 0; }}
.tree li {{ margin: .08rem 0; }}
.tree details > summary {{ cursor: pointer; user-select: none; list-style: none; padding: .18rem .35rem; border-radius: .3rem; }}
.tree details > summary::-webkit-details-marker {{ display: none; }}
.tree details[open] > summary .tree-icon {{ transform: rotate(90deg); }}
.tree-icon {{ display: inline-block; width: 1rem; transition: transform .1s linear; }}
.tree code {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .78rem; overflow-wrap: anywhere; }}
.tree-file-row {{ display: flex; align-items: center; min-width: 0; }}
.tree-file, .tree-disabled {{ display: block; padding: .18rem .35rem .18rem 1.35rem; border-radius: .3rem; color: inherit; text-decoration: none; }}
.tree-file {{ min-width: 0; flex: 1; }}
.tree-file:hover {{ background: color-mix(in srgb, CanvasText 8%, transparent); }}
.tree-file[aria-current="true"] {{ background: color-mix(in srgb, CanvasText 10%, Canvas); font-weight: 700; }}
.tree-file--fallback {{ opacity: .68; text-decoration: underline dotted; }}
.tree-source {{ flex: none; padding: .1rem .35rem; border-radius: .3rem; color: inherit; opacity: .52; text-decoration: none; font-size: .72rem; }}
.tree-source:hover {{ opacity: 1; background: color-mix(in srgb, CanvasText 8%, transparent); }}
.tree-disabled {{ opacity: .55; }}
.viewer {{ min-width: 0; min-height: 100vh; background: Canvas; }}
.viewer iframe {{ display: block; width: 100%; height: 100vh; border: 0; background: Canvas; }}
.viewer-mobile-toolbar {{ display: none; min-width: 0; align-items: center; gap: .6rem; padding: max(.55rem, env(safe-area-inset-top)) .7rem .55rem; border-bottom: 1px solid color-mix(in srgb, CanvasText 18%, transparent); background: Canvas; }}
.viewer-mobile-toolbar button {{ flex: none; min-height: 2.3rem; border: 1px solid color-mix(in srgb, CanvasText 24%, transparent); border-radius: .45rem; padding: .35rem .65rem; color: inherit; background: color-mix(in srgb, CanvasText 6%, Canvas); font: inherit; cursor: pointer; }}
.viewer-mobile-path {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font: .76rem/1.3 ui-monospace, SFMono-Regular, Consolas, monospace; }}
@media (max-width: 800px) {{
  .browser {{ grid-template-columns: 1fr; grid-template-rows: minmax(16rem, 42vh) 58vh; }}
  aside {{ max-height: 42vh; border-right: 0; border-bottom: 1px solid color-mix(in srgb, CanvasText 22%, transparent); }}
  .viewer, .viewer iframe {{ min-height: 58vh; height: 58vh; }}
  .repository-browser-enhanced body {{ height: 100vh; height: 100dvh; overflow: hidden; }}
  .repository-browser-enhanced .browser {{ display: block; width: 100%; height: 100vh; height: 100dvh; min-height: 0; }}
  .repository-browser-enhanced .browser > aside,
  .repository-browser-enhanced .browser > .viewer {{ width: 100%; height: 100%; max-height: none; min-height: 0; border: 0; }}
  .repository-browser-enhanced .browser[data-mobile-view="files"] > aside {{ display: flex; }}
  .repository-browser-enhanced .browser[data-mobile-view="files"] > .viewer {{ display: none; }}
  .repository-browser-enhanced .browser[data-mobile-view="content"] > aside {{ display: none; }}
  .repository-browser-enhanced .browser[data-mobile-view="content"] > .viewer {{ display: flex; flex-direction: column; }}
  .repository-browser-enhanced .viewer-mobile-toolbar {{ display: flex; flex: none; }}
  .repository-browser-enhanced .viewer iframe {{ flex: 1 1 auto; min-height: 0; height: auto; }}
}}
</style>
<script src="../{CONTROLLER_NAME}" defer></script>
</head>
<body>
<div class="browser" data-repository-browser data-mobile-view="files">
  <aside id="repository-tree" aria-label="Repository tree" data-repository-tree>
    <div class="browser-header">
      <h1>{html.escape(branch)} branch file browser</h1>
      <p class="browser-meta">revision {escaped_revision}<br>{viewable}/{total} regular files available as bounded UTF-8 text</p>
    </div>
    <nav class="branch-tabs" aria-label="Branches">
{branch_nav(branch, prefix='../')}
    </nav>
    <div class="tree">
      <ul>
{chr(10).join(items)}
      </ul>
    </div>
  </aside>
  <main id="repository-content" class="viewer" data-repository-content>
    <div class="viewer-mobile-toolbar" aria-label="File viewer navigation">
      <button type="button" data-show-files aria-controls="repository-tree">← Files</button>
      <span class="viewer-mobile-path" data-selected-file aria-live="polite">Selected file</span>
    </div>
    <iframe id="repository-file-frame" name="repository-file-viewer" title="Repository file viewer" sandbox="" referrerpolicy="no-referrer" srcdoc="{placeholder}"></iframe>
  </main>
</div>
</body>
</html>
"""


def lexer_for(path: bytes, text: str):
    filename = display_bytes(path)
    try:
        return get_lexer_for_filename(filename, text)
    except ClassNotFound:
        return TextLexer()


def highlighted_lines(path: bytes, text: str) -> tuple[list[str], str]:
    lexer = lexer_for(path, text)
    formatter = HtmlFormatter(nowrap=True)
    lines: list[list[str]] = [[]]
    for token_type, value in lex(text, lexer):
        css_class = formatter._get_css_class(token_type)
        pieces = value.split("\n")
        for index, piece in enumerate(pieces):
            if piece:
                escaped = html.escape(piece, quote=False)
                lines[-1].append(
                    f'<span class="{css_class}">{escaped}</span>'
                    if css_class
                    else escaped
                )
            if index != len(pieces) - 1:
                lines.append([])
    if text.endswith("\n") and lines and not lines[-1]:
        lines.pop()
    rendered = ["".join(parts) for parts in lines] or [""]
    return rendered, lexer.name


def pygments_css() -> str:
    return HtmlFormatter().get_style_defs(".line-code")


def validate_line_anchor_invariant(rendered: str, expected_lines: int) -> None:
    """Validate deterministic source-line anchors owned by this generator."""
    ids = tuple(
        int(value)
        for value in re.findall(r'<div class="source-line" id="L(\d+)">', rendered)
    )
    hrefs = tuple(
        int(value)
        for value in re.findall(r'class="line-number" href="#L(\d+)"', rendered)
    )
    expected = tuple(range(1, expected_lines + 1))
    if ids != expected or hrefs != expected:
        raise RepositoryBrowserError(
            "source viewer line-anchor invariant failed: "
            f"expected {expected_lines} contiguous anchors"
        )


def render_file_page(branch: str, revision: str, record: FileRecord) -> str:
    path_label = html.escape(display_bytes(record.path), quote=False)
    object_id = html.escape(record.object_id, quote=False)
    escaped_revision = html.escape(revision, quote=False)
    if record.viewable and record.text is not None:
        lines, lexer_name = highlighted_lines(record.path, record.text)
        body_lines = []
        for number, fragment in enumerate(lines, start=1):
            body_lines.append(
                f'<div class="source-line" id="L{number}">'
                f'<a class="line-number" href="#L{number}" '
                f'aria-label="Line {number}">{number}</a>'
                f'<code class="line-code">{fragment}</code></div>'
            )
        body = "\n".join(body_lines)
        detail = f"{html.escape(lexer_name)} · {human_size(record.size)}"
    else:
        reason = html.escape(
            record.reason or "not available as text",
            quote=False,
        )
        body = (
            '<div class="unavailable"><h2>Text view unavailable</h2>'
            f"<p>{reason}.</p>"
            "<p>Use the source arrow beside the file name in the tree to open "
            "the immutable GitHub object.</p></div>"
        )
        detail = human_size(record.size)

    controls = "" if not record.viewable else """
    <label class="toggle-label" for="show-lines"><span>Line numbers</span></label>
    <label class="toggle-label" for="wrap-lines"><span>Wrap lines</span></label>"""
    rendered = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{path_label} · {html.escape(branch)}</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: Canvas; color: CanvasText; }}
#show-lines, #wrap-lines {{ position: absolute; inline-size: 1px; block-size: 1px; opacity: 0; pointer-events: none; }}
.viewer-header {{ position: sticky; top: 0; z-index: 5; display: flex; gap: .7rem 1rem; align-items: center; flex-wrap: wrap; padding: .7rem 1rem; border-bottom: 1px solid color-mix(in srgb, CanvasText 20%, transparent); background: color-mix(in srgb, Canvas 94%, transparent); backdrop-filter: blur(8px); }}
.viewer-title {{ min-width: min(24rem, 100%); flex: 1; }}
.viewer-title strong, .viewer-title small {{ display: block; }}
.viewer-title strong {{ font: .84rem/1.35 ui-monospace, SFMono-Regular, Consolas, monospace; overflow-wrap: anywhere; }}
.viewer-title small {{ margin-top: .16rem; font-size: .7rem; opacity: .68; overflow-wrap: anywhere; }}
.viewer-controls {{ display: flex; gap: .45rem; align-items: center; flex-wrap: wrap; }}
.toggle-label {{ border: 1px solid color-mix(in srgb, CanvasText 24%, transparent); border-radius: .35rem; padding: .28rem .5rem; font-size: .72rem; color: inherit; cursor: pointer; }}
#show-lines:checked ~ .viewer-header label[for="show-lines"], #wrap-lines:checked ~ .viewer-header label[for="wrap-lines"] {{ background: color-mix(in srgb, CanvasText 10%, Canvas); font-weight: 700; }}
.source {{ min-width: 100%; width: max-content; padding: .6rem 0 2rem; font: 13px/1.55 ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; }}
.source-line {{ display: grid; grid-template-columns: max-content minmax(0, 1fr); min-height: 1.55em; }}
.line-number {{ grid-column: 1; position: sticky; left: 0; z-index: 2; min-width: 4.2rem; padding: 0 .75rem 0 .6rem; text-align: right; user-select: none; text-decoration: none; color: color-mix(in srgb, CanvasText 45%, transparent); background: Canvas; border-right: 1px solid color-mix(in srgb, CanvasText 12%, transparent); }}
.line-code {{ display: block; grid-column: 2; min-width: 0; padding: 0 .9rem; white-space: pre; tab-size: 4; unicode-bidi: plaintext; }}
#show-lines:not(:checked) ~ main .source-line {{ grid-template-columns: minmax(0, 1fr); }}
#show-lines:not(:checked) ~ main .line-number {{ display: none; }}
#show-lines:not(:checked) ~ main .line-code {{ grid-column: 1; }}
#wrap-lines:checked ~ main .source {{ width: 100%; }}
#wrap-lines:checked ~ main .line-code {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.unavailable {{ max-width: 48rem; margin: 3rem auto; padding: 0 1.25rem; }}
{pygments_css()}
</style>
</head>
<body>
<input id="show-lines" type="checkbox" checked>
<input id="wrap-lines" type="checkbox">
<header class="viewer-header">
  <div class="viewer-title">
    <strong>{path_label}</strong>
    <small>{html.escape(branch)} · {escaped_revision} · blob {object_id} · {detail}</small>
  </div>
  <div class="viewer-controls">
{controls}
  </div>
</header>
<main>
  <div class="source">{body}</div>
</main>
</body>
</html>
"""

    validate_line_anchor_invariant(rendered, expected_lines)
    return rendered

def prepare_browser_root(output_root: Path) -> Path:
    if output_root.is_symlink() or not output_root.is_dir():
        raise RepositoryBrowserError(
            "output root must be an existing regular directory"
        )
    browser_root = output_root / BROWSER_ROOT
    if browser_root.exists() or browser_root.is_symlink():
        raise RepositoryBrowserError(
            f"browser destination already exists: {browser_root}"
        )
    browser_root.mkdir(parents=True)
    (browser_root / MANAGED_MARKER).write_text(
        MANAGED_MARKER_CONTENT,
        encoding="utf-8",
    )
    return browser_root


def write_root_index(browser_root: Path) -> None:
    links = "".join(
        f'<li><a href="{branch}/">{html.escape(branch)}</a></li>'
        for branch in BRANCH_ORDER
    )
    (browser_root / "index.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Repository file browser</title><style>:root{{color-scheme:light dark;font-family:system-ui,sans-serif}}body{{max-width:48rem;margin:4rem auto;padding:0 1rem}}a{{color:LinkText}}code{{font-family:ui-monospace,monospace}}</style></head>
<body><h1>Repository file browser</h1><p>Browse immutable build-time snapshots of the Site, Composition, and Policy authorities.</p><ul>{links}</ul></body></html>\n""",
        encoding="utf-8",
    )


def write_browser_controller(browser_root: Path) -> None:
    if CONTROLLER_SOURCE.is_symlink() or not CONTROLLER_SOURCE.is_file():
        raise RepositoryBrowserError(
            f"repository browser controller is unavailable: {CONTROLLER_SOURCE}"
        )
    controller = CONTROLLER_SOURCE.read_text(encoding="utf-8")
    if "\0" in controller:
        raise RepositoryBrowserError("repository browser controller contains NUL")
    (browser_root / CONTROLLER_NAME).write_text(controller, encoding="utf-8")


def generate_browser(
    repository: str,
    output_root: Path,
    branches: dict[str, Path],
) -> list[str]:
    if not REPOSITORY.fullmatch(repository):
        raise RepositoryBrowserError("repository must use owner/name form")
    if tuple(branches) != BRANCH_ORDER:
        raise RepositoryBrowserError(
            "branches must be supplied exactly in site, composition, policy order"
        )
    browser_root = prepare_browser_root(output_root)
    write_root_index(browser_root)
    write_browser_controller(browser_root)
    messages: list[str] = []
    for branch in BRANCH_ORDER:
        root = branches[branch].resolve(strict=True)
        revision = checked_revision(root)
        if not FULL_SHA.fullmatch(revision):
            raise RepositoryBrowserError(
                f"{branch} did not resolve to a full SHA"
            )
        tree, records = collect_records(
            branch,
            repository,
            revision,
            root,
        )
        branch_root = browser_root / branch
        content_root = branch_root / "content"
        content_root.mkdir(parents=True)
        branch_root.joinpath("index.html").write_text(
            render_browser_page(branch, revision, tree, records),
            encoding="utf-8",
        )
        for record in records.values():
            destination = branch_root / record.viewer_url
            destination.write_text(
                render_file_page(branch, revision, record),
                encoding="utf-8",
            )
        messages.append(
            f"{branch}: {sum(record.viewable for record in records.values())}/"
            f"{len(records)} regular files browser-viewable at {revision}"
        )
    return messages


def parse_branch(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("branch must use name=path form")
    name, raw_path = value.split("=", 1)
    if name not in BRANCH_ORDER or not raw_path:
        raise argparse.ArgumentTypeError(
            "branch name must be site, composition, or policy"
        )
    return name, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--branch",
        action="append",
        type=parse_branch,
        required=True,
    )
    args = parser.parse_args()
    branches: dict[str, Path] = {}
    for name, path in args.branch:
        if name in branches:
            parser.error(f"duplicate branch: {name}")
        branches[name] = path
    try:
        messages = generate_browser(
            args.repository,
            args.output_root,
            branches,
        )
    except (
        RepositoryBrowserError,
        RepositoryTreeError,
        RepositoryFilePreviewError,
        OSError,
    ) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())