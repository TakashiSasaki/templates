"""Immutable repository read-model records and public URL conventions."""
from __future__ import annotations
import hashlib
import json
import re
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


def entry_label(entry: TreeEntry) -> str:
    if entry.is_directory:
        return "directory"
    if entry.mode == "120000":
        return "symlink"
    if entry.mode == "160000" or entry.kind == "commit":
        return "gitlink"
    return "file"

PREVIEW_ROOT = Path("repository-trees/previews")

MAX_PREVIEW_BYTES = 256 * 1024


MAX_CANDIDATE_BYTES = 32 * 1024 * 1024


MAX_TOTAL_PREVIEW_BYTES = 16 * 1024 * 1024


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

MAX_TEXT_BYTES = 1024 * 1024


MAX_TOTAL_TEXT_BYTES = 64 * 1024 * 1024


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

