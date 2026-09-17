"""Small, immutable GitHub URL helpers shared by Site renderers."""
from __future__ import annotations

import re
from urllib.parse import quote_from_bytes


FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
REPOSITORY = re.compile(r"\A[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


class GitHubUrlError(ValueError):
    """Raised when a canonical GitHub URL input is not immutable and safe."""


def _validate(repository: str, revision: str) -> None:
    if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
        raise GitHubUrlError("repository must be owner/name")
    if not isinstance(revision, str) or not FULL_SHA.fullmatch(revision):
        raise GitHubUrlError("revision must be a lowercase full commit SHA")


def _path(path: str | bytes) -> str:
    raw = path.encode("utf-8") if isinstance(path, str) else path
    if (
        not isinstance(raw, bytes)
        or raw.startswith(b"/")
        or b"\0" in raw
        or (raw and any(part in {b"", b".", b".."} for part in raw.split(b"/")))
    ):
        raise GitHubUrlError("source path must be relative and NUL-free")
    return quote_from_bytes(raw, safe="/@-._~")


def _url(
    kind: str,
    repository: str,
    revision: str,
    path: str | bytes = b"",
    fragment: str | None = None,
) -> str:
    _validate(repository, revision)
    suffix = _path(path)
    result = f"https://github.com/{repository}/{kind}/{revision}"
    if suffix:
        result += "/" + suffix
    if fragment is not None:
        result += "#" + quote_from_bytes(fragment.encode("utf-8"), safe=b"-._~:/")
    return result


def github_commit_url(repository: str, revision: str) -> str:
    """Return the immutable commit page for an exact full SHA."""
    return _url("commit", repository, revision)


def github_blob_url(
    repository: str,
    revision: str,
    path: str | bytes,
    *,
    fragment: str | None = None,
) -> str:
    """Return the immutable file/blob page for an exact full SHA."""
    return _url("blob", repository, revision, path, fragment)


def github_tree_url(
    repository: str,
    revision: str,
    path: str | bytes = b"",
    *,
    fragment: str | None = None,
) -> str:
    """Return the immutable directory/tree page for an exact full SHA."""
    return _url("tree", repository, revision, path, fragment)
