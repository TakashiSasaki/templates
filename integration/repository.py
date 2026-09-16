"""Upstream-only immutable Git inspection and bounded source read models."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Iterable
from publication_bundle.repository import *
from integration.publication_model import AssemblyError, load_manifest

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


def read_entries(root: Path) -> list[TreeEntry]:
    return parse_ls_tree(
        git(root, "ls-tree", "--full-tree", "-r", "-t", "-z", "HEAD")
    )


def manifest_destinations(site_root: Path) -> dict[tuple[str, str], str]:
    try:
        manifest = load_manifest(site_root / "site-manifest.json")
    except AssemblyError as exc:
        raise RepositoryTreeError(str(exc)) from exc
    return {
        (document["publication"], document["document"]): document["destination"].as_posix()
        for document in manifest.documents
    }


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

