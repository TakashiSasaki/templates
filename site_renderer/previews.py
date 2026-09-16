"""Render bounded immutable source previews."""
from __future__ import annotations
import html
from pathlib import Path
from publication_bundle.repository import *

TREE_CONTAINER = '<div class="repository-tree">'


def render_preview_page(
    publication: str,
    revision: str,
    path: bytes,
    object_id: str,
    text: str,
) -> str:
    label = html.escape(display_bytes(path), quote=False)
    escaped_revision = html.escape(revision, quote=False)
    escaped_object = html.escape(object_id, quote=False)
    content = html.escape(text, quote=False)
    title = html.escape(
        f"{publication}: {display_bytes(path)}",
        quote=False,
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{title}</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ margin: 0; font-family: system-ui, sans-serif; }}
header {{ border-bottom: 1px solid CanvasText; padding: .75rem 1rem; }}
header code {{ overflow-wrap: anywhere; }}
p {{ margin: .35rem 0 0; font-size: .8rem; opacity: .75; }}
pre {{ box-sizing: border-box; margin: 0; min-height: calc(100vh - 5rem); overflow: auto; padding: 1rem; tab-size: 4; }}
code {{ font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; white-space: pre; unicode-bidi: plaintext; }}
</style>
</head>
<body>
<header>
<strong><code>{label}</code></strong>
<p>Publication: {html.escape(publication)} · revision <code>{escaped_revision}</code> · blob <code>{escaped_object}</code></p>
</header>
<pre><code>{content}</code></pre>
</body>
</html>
"""


def viewer_panel(publication: str, repository: str, revision: str) -> str:
    frame_name = f"repository-file-preview-{publication}"
    root_source = html.escape(
        github_url(repository, revision, "tree"),
        quote=True,
    )
    placeholder = html.escape(
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<style>body{font-family:system-ui,sans-serif;padding:1rem}</style>"
        "<p>Select a <strong>preview</strong> link from the repository tree.</p>"
        "</html>",
        quote=True,
    )
    return f"""<div class="repository-file-viewer" data-repository-file-viewer data-preview-target="{frame_name}">
  <div class="repository-file-viewer__toolbar">
    <strong data-preview-label>Inline file preview</strong>
    <a href="{root_source}" data-preview-source target="_blank" rel="noopener">Open source on GitHub</a>
  </div>
  <iframe
    name="{frame_name}"
    title="Inline file preview"
    sandbox=""
    referrerpolicy="no-referrer"
    loading="lazy"
    srcdoc="{placeholder}"
  ></iframe>
</div>

"""


def inject_preview_links(
    publication: str,
    repository: str,
    revision: str,
    site_base_path: str,
    output_root: Path,
    published: dict[bytes, str],
    records: list[PreviewRecord],
) -> None:
    tree_path = output_root / "docs/repository-trees" / f"{publication}.md"
    try:
        source = tree_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RepositoryFilePreviewError(
            f"unable to read generated repository tree {tree_path}: {exc}"
        ) from exc
    if source.count(TREE_CONTAINER) != 1:
        raise RepositoryFilePreviewError(
            f"{tree_path} must contain exactly one repository-tree container"
        )
    frame_name = f"repository-file-preview-{publication}"
    for record in records:
        source_url = html.escape(record.source_url, quote=True)
        preview_url = html.escape(
            site_base_path + record.relative_url,
            quote=True,
        )
        preview_path = html.escape(display_bytes(record.path), quote=True)
        preview_link = (
            f'<a class="repository-file-preview-link" href="{preview_url}" '
            f'target="{frame_name}" data-preview-path="{preview_path}" '
            f'data-preview-source="{source_url}">preview</a>'
        )
        if record.path in published:
            needle = f'<small><a href="{source_url}">source</a></small>'
            replacement = (
                f"<small>{preview_link} · "
                f'<a href="{source_url}">source</a></small>'
            )
        else:
            name = html.escape(
                display_bytes(record.path.rsplit(b"/", 1)[-1]),
                quote=False,
            )
            needle = f'<code><a href="{source_url}">{name}</a></code>'
            replacement = f"{needle} <small>{preview_link}</small>"
        if source.count(needle) != 1:
            raise RepositoryFilePreviewError(
                "unable to locate immutable source link for "
                f"{publication}:{display_bytes(record.path)}"
            )
        source = source.replace(needle, replacement, 1)
    panel = viewer_panel(publication, repository, revision)
    source = source.replace(TREE_CONTAINER, panel + TREE_CONTAINER, 1)
    tree_path.write_text(source, encoding="utf-8")


def write_preview_pages(
    output_root: Path,
    records: Iterable[PreviewRecord],
    publication: str,
    revision: str,
) -> int:
    count = 0
    for record in records:
        destination = output_root / "docs" / record.relative_url
        if destination.exists() or destination.is_symlink():
            raise RepositoryFilePreviewError(
                f"preview destination already exists: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render_preview_page(
                publication,
                revision,
                record.path,
                record.object_id,
                record.text,
            ),
            encoding="utf-8",
        )
        count += 1
    return count

