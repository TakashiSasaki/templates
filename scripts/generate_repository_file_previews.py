#!/usr/bin/env python3
"""Generate sandboxed inline previews for immutable repository-tree files."""

from __future__ import annotations

import argparse
import hashlib
import html
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from scripts.generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        configured_base_path,
        display_bytes,
        entry_label,
        github_url,
        parse_publications,
        published_sources,
        read_entries,
    )
except ModuleNotFoundError:
    from generate_repository_trees import (
        FULL_SHA,
        REPOSITORY,
        RepositoryTreeError,
        checked_revision,
        configured_base_path,
        display_bytes,
        entry_label,
        github_url,
        parse_publications,
        published_sources,
        read_entries,
    )


MAX_PREVIEW_BYTES = 256 * 1024
MAX_CANDIDATE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_PREVIEW_BYTES = 16 * 1024 * 1024
TREE_CONTAINER = '<div class="repository-tree">'
PREVIEW_ROOT = Path("repository-trees/previews")
BIDIRECTIONAL_CONTROLS = frozenset(
    {
        "\u061c",
        "\u200e",
        "\u200f",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)


class RepositoryFilePreviewError(RuntimeError):
    """Raised when immutable inline previews cannot be generated safely."""


@dataclass(frozen=True)
class PreviewRecord:
    path: bytes
    object_id: str
    text: str
    relative_url: str
    source_url: str


def run_git_batch(root: Path, mode: str, object_ids: Iterable[str]) -> bytes:
    identifiers = tuple(dict.fromkeys(object_ids))
    if not identifiers:
        return b""
    payload = b"".join(
        identifier.encode("ascii") + b"\n" for identifier in identifiers
    )
    try:
        process = subprocess.run(
            ["git", "-C", str(root), "cat-file", mode],
            input=payload,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise RepositoryFilePreviewError(
            f"unable to inspect Git objects in {root}{suffix}"
        ) from exc
    return process.stdout


def object_sizes(root: Path, object_ids: Iterable[str]) -> dict[str, int]:
    identifiers = tuple(dict.fromkeys(object_ids))
    raw = run_git_batch(root, "--batch-check", identifiers)
    lines = raw.splitlines()
    if len(lines) != len(identifiers):
        raise RepositoryFilePreviewError(
            "git cat-file --batch-check returned an unexpected record count"
        )
    result: dict[str, int] = {}
    for expected, line in zip(identifiers, lines, strict=True):
        try:
            object_id, kind, raw_size = line.decode("ascii").split(" ")
            size = int(raw_size)
        except (UnicodeDecodeError, ValueError) as exc:
            raise RepositoryFilePreviewError(
                "git cat-file --batch-check returned malformed output"
            ) from exc
        if object_id != expected or kind != "blob" or size < 0:
            raise RepositoryFilePreviewError(
                f"expected immutable blob {expected}, received {line!r}"
            )
        result[object_id] = size
    return result


def object_contents(root: Path, object_ids: Iterable[str]) -> dict[str, bytes]:
    identifiers = tuple(dict.fromkeys(object_ids))
    raw = run_git_batch(root, "--batch", identifiers)
    result: dict[str, bytes] = {}
    offset = 0
    for expected in identifiers:
        line_end = raw.find(b"\n", offset)
        if line_end < 0:
            raise RepositoryFilePreviewError(
                "git cat-file --batch omitted an object header"
            )
        header = raw[offset:line_end]
        offset = line_end + 1
        try:
            object_id, kind, raw_size = header.decode("ascii").split(" ")
            size = int(raw_size)
        except (UnicodeDecodeError, ValueError) as exc:
            raise RepositoryFilePreviewError(
                "git cat-file --batch returned malformed output"
            ) from exc
        if object_id != expected or kind != "blob" or size < 0:
            raise RepositoryFilePreviewError(
                f"expected immutable blob {expected}, received {header!r}"
            )
        end = offset + size
        if end >= len(raw) or raw[end : end + 1] != b"\n":
            raise RepositoryFilePreviewError(
                "git cat-file --batch returned truncated blob data"
            )
        result[object_id] = raw[offset:end]
        offset = end + 1
    if offset != len(raw):
        raise RepositoryFilePreviewError(
            "git cat-file --batch returned trailing data"
        )
    return result


def decode_preview_text(content: bytes) -> str | None:
    if len(content) > MAX_PREVIEW_BYTES or b"\0" in content:
        return None
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    for character in text:
        value = ord(character)
        if (
            (value < 32 and character not in "\t\n\f\r")
            or value == 127
            or character in BIDIRECTIONAL_CONTROLS
        ):
            return None
    return text


def preview_relative_url(publication: str, revision: str, path: bytes) -> str:
    digest = hashlib.sha256(
        publication.encode("ascii")
        + b"\0"
        + revision.encode("ascii")
        + b"\0"
        + path
    ).hexdigest()
    return (
        f"{PREVIEW_ROOT.as_posix()}/{publication}/{revision}/{digest}.html"
    )


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


def build_preview_records(
    publication: str,
    repository: str,
    revision: str,
    root: Path,
) -> list[PreviewRecord]:
    entries = [
        entry
        for entry in read_entries(root)
        if entry_label(entry) == "file" and FULL_SHA.fullmatch(entry.object_id)
    ]
    sizes = object_sizes(root, (entry.object_id for entry in entries))
    candidates = [
        entry
        for entry in entries
        if sizes[entry.object_id] <= MAX_PREVIEW_BYTES
    ]
    candidate_bytes = sum(sizes[entry.object_id] for entry in candidates)
    if candidate_bytes > MAX_CANDIDATE_BYTES:
        raise RepositoryFilePreviewError(
            f"{publication} inline-preview candidates exceed "
            f"{MAX_CANDIDATE_BYTES} bytes"
        )
    contents = object_contents(root, (entry.object_id for entry in candidates))
    records: list[PreviewRecord] = []
    total = 0
    for entry in sorted(candidates, key=lambda value: value.path):
        text = decode_preview_text(contents[entry.object_id])
        if text is None:
            continue
        total += len(contents[entry.object_id])
        if total > MAX_TOTAL_PREVIEW_BYTES:
            raise RepositoryFilePreviewError(
                f"{publication} inline-preview text exceeds "
                f"{MAX_TOTAL_PREVIEW_BYTES} bytes"
            )
        records.append(
            PreviewRecord(
                path=entry.path,
                object_id=entry.object_id,
                text=text,
                relative_url=preview_relative_url(
                    publication,
                    revision,
                    entry.path,
                ),
                source_url=github_url(
                    repository,
                    revision,
                    "blob",
                    entry.path,
                ),
            )
        )
    return records


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


def generate_previews(
    repository: str,
    site_root: Path,
    output_root: Path,
    publications: dict[str, Path],
) -> list[str]:
    if not REPOSITORY.fullmatch(repository):
        raise RepositoryFilePreviewError("repository must use owner/name form")
    expected = {"skill", "policy", "webapp"}
    if set(publications) != expected:
        raise RepositoryFilePreviewError(
            "inline previews require exactly skill, policy, and webapp"
        )
    site_base_path = configured_base_path(output_root / "zensical.toml")
    messages: list[str] = []
    for publication in ("skill", "policy", "webapp"):
        root = publications[publication].resolve(strict=True)
        revision = checked_revision(root)
        records = build_preview_records(
            publication,
            repository,
            revision,
            root,
        )
        published = published_sources(publication, root, site_root)
        inject_preview_links(
            publication,
            repository,
            revision,
            site_base_path,
            output_root,
            published,
            records,
        )
        count = write_preview_pages(
            output_root,
            records,
            publication,
            revision,
        )
        messages.append(
            f"{publication}: {count} inline text previews at {revision}"
        )
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--site-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--publication",
        action="append",
        default=[],
        metavar="NAME=PATH",
    )
    args = parser.parse_args()
    try:
        messages = generate_previews(
            args.repository,
            args.site_root.resolve(strict=True),
            args.output_root.resolve(strict=True),
            parse_publications(args.publication),
        )
    except (OSError, RepositoryTreeError, RepositoryFilePreviewError) as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
