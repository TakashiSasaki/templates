"""Render repository tree records; no Git or provider source inputs."""
from __future__ import annotations
import html
from pathlib import Path
from publication_bundle.repository import *

def render_entry(
    entry: TreeEntry,
    repository: str,
    revision: str,
    tree_destination: str,
    site_base_path: str,
    published: dict[bytes, str],
    depth: int,
) -> list[str]:
    indent = "  " * depth
    name = html.escape(display_bytes(entry.name), quote=False)
    path = entry.path

    if entry.is_directory:
        source = html.escape(
            github_url(repository, revision, "tree", path),
            quote=True,
        )
        values = [
            f'{indent}<details>',
            f'{indent}  <summary><code>{name}/</code> '
            f'<a href="{source}">GitHub</a></summary>',
            f'{indent}  <ul>',
        ]
        for child in sorted(
            entry.children.values(),
            key=lambda item: (not item.is_directory, item.name),
        ):
            values.append(f"{indent}    <li>")
            values.extend(
                render_entry(
                    child,
                    repository,
                    revision,
                    tree_destination,
                    site_base_path,
                    published,
                    depth + 3,
                )
            )
            values.append(f"{indent}    </li>")
        values.extend([f"{indent}  </ul>", f"{indent}</details>"])
        return values

    label = entry_label(entry)
    external_kind = "tree" if label == "gitlink" else "blob"
    source = html.escape(
        github_url(repository, revision, external_kind, path),
        quote=True,
    )
    type_suffix = "" if label == "file" else f" <small>({label})</small>"
    destination = published.get(path)
    if destination is not None and label == "file":
        internal = html.escape(
            published_url(site_base_path, destination),
            quote=True,
        )
        return [
            f'{indent}<code><a href="{internal}">{name}</a></code>'
            f'{type_suffix} <small><a href="{source}">source</a></small>'
        ]
    return [f'{indent}<code><a href="{source}">{name}</a></code>{type_suffix}']


def render_tree(
    publication: str,
    repository: str,
    revision: str,
    root: TreeEntry,
    tree_destination: str,
    site_base_path: str,
    published: dict[bytes, str],
) -> tuple[str, dict[str, int]]:
    entries: list[TreeEntry] = []

    def collect(node: TreeEntry) -> None:
        for child in node.children.values():
            entries.append(child)
            if child.is_directory:
                collect(child)

    collect(root)
    counts = {
        "directories": sum(entry.is_directory for entry in entries),
        "files": sum(entry_label(entry) == "file" for entry in entries),
        "symlinks": sum(entry_label(entry) == "symlink" for entry in entries),
        "gitlinks": sum(entry_label(entry) == "gitlink" for entry in entries),
        "published_documents": sum(
            entry.path in published and entry_label(entry) == "file"
            for entry in entries
        ),
    }

    root_url = html.escape(
        github_url(repository, revision, "tree"),
        quote=True,
    )

    def quantity(value: int, singular: str) -> str:
        suffix = "" if value == 1 else "s"
        return f"{value} {singular}{suffix}"

    values = [
        f"**Rendered revision:** [`{revision}`]({root_url})",
        "",
        (
            "Tracked tree: "
            f"{quantity(counts['directories'], 'directory')}, "
            f"{quantity(counts['files'], 'regular file')}, "
            f"{quantity(counts['symlinks'], 'symlink')}, and "
            f"{quantity(counts['gitlinks'], 'gitlink')}. "
            f"Documentation pages: {counts['published_documents']}."
        ),
        "",
        "File names link to the human-readable documentation page when the file is "
        "cataloged; otherwise they link to the immutable GitHub source view. "
        "The adjacent **source** link always opens GitHub at the same revision.",
        "",
        '<div class="repository-tree">',
        "<ul>",
    ]
    for child in sorted(
        root.children.values(),
        key=lambda item: (not item.is_directory, item.name),
    ):
        values.append("  <li>")
        values.extend(
            render_entry(
                child,
                repository,
                revision,
                tree_destination,
                site_base_path,
                published,
                2,
            )
        )
        values.append("  </li>")
    values.extend(["</ul>", "</div>"])
    return "\n".join(values) + "\n", counts


def replace_marker(path: Path, marker: str, content: str) -> None:
    try:
        template = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RepositoryTreeError(f"unable to read tree template {path}: {exc}") from exc
    if template.count(marker) != 1:
        raise RepositoryTreeError(
            f"{path} must contain {marker!r} exactly once"
        )
    path.write_text(template.replace(marker, content.rstrip()), encoding="utf-8")

