#!/usr/bin/env python3
"""Generate deterministic repository-tree pages for locked publications."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, quote_from_bytes, urlsplit


NAME = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
REPOSITORY = re.compile(r"\A[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
INDEX_MARKER = "<!-- GENERATED_REPOSITORY_TREE_INDEX -->"


class RepositoryTreeError(RuntimeError):
    """Raised when repository-tree generation inputs are invalid."""


@dataclass
class TreeEntry:
    name: bytes
    path: bytes
    mode: str
    kind: str
    object_id: str
    children: dict[bytes, "TreeEntry"] = field(default_factory=dict)

    @property
    def is_directory(self) -> bool:
        return self.kind == "tree"


def parse_name(value: str, field_name: str) -> str:
    if not NAME.fullmatch(value):
        raise RepositoryTreeError(f"{field_name} must be lowercase kebab-case")
    return value


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RepositoryTreeError(f"unable to read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RepositoryTreeError(f"{label} must be an object")
    return value


def git(root: Path, *args: str) -> bytes:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError):
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise RepositoryTreeError(
            f"unable to inspect Git repository {root}{suffix}"
        ) from exc
    return process.stdout


def checked_revision(root: Path) -> str:
    revision = git(root, "rev-parse", "HEAD").decode("ascii", errors="strict").strip()
    if not FULL_SHA.fullmatch(revision):
        raise RepositoryTreeError(f"Git HEAD must resolve to a full lowercase SHA: {root}")
    return revision


def parse_ls_tree(raw: bytes) -> list[TreeEntry]:
    result: list[TreeEntry] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path = record.split(b"\t", maxsplit=1)
            mode, kind, object_id = metadata.decode("ascii").split(" ", maxsplit=2)
        except (ValueError, UnicodeDecodeError) as exc:
            raise RepositoryTreeError("git ls-tree returned malformed output") from exc
        if not path or path.startswith(b"/") or b"\0" in path:
            raise RepositoryTreeError("git ls-tree returned an unsafe path")
        result.append(
            TreeEntry(
                name=path.rsplit(b"/", maxsplit=1)[-1],
                path=path,
                mode=mode,
                kind=kind,
                object_id=object_id,
            )
        )
    return result


def read_entries(root: Path) -> list[TreeEntry]:
    return parse_ls_tree(
        git(root, "ls-tree", "--full-tree", "-r", "-t", "-z", "HEAD")
    )


def build_tree(entries: list[TreeEntry]) -> TreeEntry:
    root = TreeEntry(name=b"", path=b"", mode="040000", kind="tree", object_id="")
    indexed: dict[bytes, TreeEntry] = {b"": root}

    for entry in sorted(entries, key=lambda item: (item.path.count(b"/"), item.path)):
        parent_path = entry.path.rsplit(b"/", maxsplit=1)[0] if b"/" in entry.path else b""
        parent = indexed.get(parent_path)
        if parent is None or not parent.is_directory:
            raise RepositoryTreeError(
                "git ls-tree did not provide a valid parent directory ordering"
            )
        if entry.name in parent.children:
            raise RepositoryTreeError("git ls-tree returned a duplicate path")
        parent.children[entry.name] = entry
        indexed[entry.path] = entry
    return root


def display_bytes(value: bytes) -> str:
    text = value.decode("utf-8", errors="backslashreplace")
    replacements = {"\n": r"\n", "\r": r"\r", "\t": r"\t"}
    return "".join(
        replacements.get(character, character if ord(character) >= 32 and ord(character) != 127 else f"\\x{ord(character):02x}")
        for character in text
    )


def github_url(repository: str, revision: str, kind: str, path: bytes = b"") -> str:
    suffix = quote_from_bytes(path, safe="/")
    base = f"https://github.com/{repository}/{kind}/{revision}"
    return f"{base}/{suffix}" if suffix else base


def markdown_destination_url(destination: str) -> str:
    path = PurePosixPath(destination)
    if path.suffix.lower() != ".md":
        raise RepositoryTreeError(
            f"published document destination must be Markdown: {destination}"
        )
    without_suffix = path.with_suffix("")
    if without_suffix.name == "index":
        output = without_suffix.parent.as_posix()
    else:
        output = without_suffix.as_posix()
    if output in ("", "."):
        return ""
    return "/".join(quote(part, safe="") for part in output.split("/")) + "/"


def configured_base_path(config_path: Path) -> str:
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise RepositoryTreeError(
            f"unable to read site configuration {config_path}: {exc}"
        ) from exc
    project = config.get("project")
    site_url = project.get("site_url") if isinstance(project, dict) else None
    if not isinstance(site_url, str):
        raise RepositoryTreeError("project.site_url must be a URL string")
    parsed = urlsplit(site_url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise RepositoryTreeError(
            "project.site_url must be an absolute HTTP(S) URL without query or fragment"
        )
    path = parsed.path or "/"
    if not path.startswith("/"):
        raise RepositoryTreeError("project.site_url path must be absolute")
    return path if path.endswith("/") else path + "/"


def published_url(base_path: str, document_destination: str) -> str:
    document_url = markdown_destination_url(document_destination)
    return base_path + document_url


def manifest_destinations(site_root: Path) -> dict[tuple[str, str], str]:
    manifest = read_json(site_root / "site-manifest.json", "site manifest")
    navigation = manifest.get("navigation")
    if not isinstance(navigation, list):
        raise RepositoryTreeError("site manifest navigation must be an array")

    result: dict[tuple[str, str], str] = {}

    def visit(nodes: list[Any]) -> None:
        for node in nodes:
            if not isinstance(node, dict):
                raise RepositoryTreeError("site manifest nodes must be objects")
            if "children" in node:
                children = node["children"]
                if not isinstance(children, list):
                    raise RepositoryTreeError("site manifest children must be an array")
                visit(children)
                continue
            publication = node.get("publication")
            document = node.get("document")
            destination = node.get("destination")
            if not all(
                isinstance(value, str)
                for value in (publication, document, destination)
            ):
                raise RepositoryTreeError("site manifest page fields must be strings")
            key = (publication, document)
            if key in result:
                raise RepositoryTreeError("site manifest contains a duplicate document")
            result[key] = destination

    visit(navigation)
    return result


def published_sources(
    publication: str,
    publication_root: Path,
    site_root: Path,
) -> dict[bytes, str]:
    catalog = read_json(
        publication_root / "docs/publication-catalog.json",
        f"{publication} publication catalog",
    )
    documents = catalog.get("documents")
    if not isinstance(documents, list):
        raise RepositoryTreeError(
            f"{publication} publication catalog documents must be an array"
        )
    destinations = manifest_destinations(site_root)
    result: dict[bytes, str] = {}
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            raise RepositoryTreeError(
                f"{publication} publication catalog document {index} must be an object"
            )
        document_id = document.get("id")
        source = document.get("source")
        if not isinstance(document_id, str) or not isinstance(source, str):
            raise RepositoryTreeError(
                f"{publication} publication catalog document {index} is invalid"
            )
        destination = destinations.get((publication, document_id))
        if destination is None:
            raise RepositoryTreeError(
                f"site manifest does not map {publication}:{document_id}"
            )
        result[source.encode("utf-8")] = destination
    return result


def entry_label(entry: TreeEntry) -> str:
    if entry.is_directory:
        return "directory"
    if entry.mode == "120000":
        return "symlink"
    if entry.mode == "160000" or entry.kind == "commit":
        return "gitlink"
    return "file"


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


def generate(
    repository: str,
    site_root: Path,
    output_root: Path,
    publications: dict[str, Path],
) -> list[str]:
    if not REPOSITORY.fullmatch(repository):
        raise RepositoryTreeError("repository must use owner/name form")
    expected = {"skill", "policy", "webapp"}
    if set(publications) != expected:
        raise RepositoryTreeError(
            "repository trees require exactly skill, policy, and webapp"
        )

    docs_root = output_root / "docs" / "repository-trees"
    if not docs_root.is_dir():
        raise RepositoryTreeError(
            f"assembled repository-tree templates are missing: {docs_root}"
        )

    site_base_path = configured_base_path(output_root / "zensical.toml")
    summaries: dict[str, tuple[str, dict[str, int]]] = {}
    messages: list[str] = []
    for publication in ("skill", "policy", "webapp"):
        root = publications[publication].resolve(strict=True)
        revision = checked_revision(root)
        entries = read_entries(root)
        tree = build_tree(entries)
        tree_destination = f"repository-trees/{publication}.md"
        published = published_sources(publication, root, site_root)
        rendered, counts = render_tree(
            publication,
            repository,
            revision,
            tree,
            tree_destination,
            site_base_path,
            published,
        )
        replace_marker(
            docs_root / f"{publication}.md",
            f"<!-- GENERATED_REPOSITORY_TREE:{publication} -->",
            rendered,
        )
        summaries[publication] = (revision, counts)
        messages.append(
            f"{publication}: {counts['files']} files at {revision}"
        )

    table = [
        "| Publication | Rendered revision | Directories | Files | Published documents |",
        "|---|---|---:|---:|---:|",
    ]
    labels = {
        "skill": "Skill",
        "policy": "Policy",
        "webapp": "Web application",
    }
    for publication in ("skill", "policy", "webapp"):
        revision, counts = summaries[publication]
        table.append(
            f"| [{labels[publication]}]({publication}.md) | "
            f"`{revision}` | {counts['directories']} | "
            f"{counts['files'] + counts['symlinks'] + counts['gitlinks']} | "
            f"{counts['published_documents']} |"
        )
    replace_marker(
        docs_root / "index.md",
        INDEX_MARKER,
        "\n".join(table) + "\n",
    )
    return messages


def parse_publications(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for index, value in enumerate(values):
        if "=" not in value:
            raise RepositoryTreeError(
                f"--publication[{index}] must use NAME=PATH"
            )
        name, raw_path = value.split("=", maxsplit=1)
        name = parse_name(name, f"--publication[{index}].name")
        if not raw_path or name in result:
            raise RepositoryTreeError(
                f"--publication[{index}] must have a unique non-empty path"
            )
        result[name] = Path(raw_path)
    return result


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
        messages = generate(
            args.repository,
            args.site_root.resolve(strict=True),
            args.output_root.resolve(strict=True),
            parse_publications(args.publication),
        )
    except RepositoryTreeError as exc:
        parser.error(str(exc))
    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
