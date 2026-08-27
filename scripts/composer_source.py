#!/usr/bin/env python3
"""Source identity, authority, and revision-transition services for Composition."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_REPOSITORY = "TakashiSasaki/templates"
SOURCE_CONTEXT_ENV = "COMPOSITION_SOURCE_CONTEXT"
COMPARE_RESPONSE_LIMIT = 1024 * 1024


class SourceContextError(RuntimeError):
    """Fail-closed source-context diagnostic independent of Composer presentation."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class Response(Protocol):
    def __enter__(self) -> Response: ...

    def __exit__(self, *args: object) -> None: ...

    def read(self, amount: int = -1) -> bytes: ...


class Opener(Protocol):
    def __call__(
        self,
        request: urllib.request.Request,
        *,
        timeout: int,
    ) -> Response: ...


def _validate_revision(revision: str, *, label: str) -> str:
    if FULL_SHA.fullmatch(revision) is None or revision == "0" * 40:
        raise SourceContextError(
            "INVALID_SOURCE_REVISION",
            f"invalid {label}: {revision!r}",
        )
    return revision


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def verify_github_descendant(
    repository: str,
    old_revision: str,
    new_revision: str,
    *,
    opener: Opener = urllib.request.urlopen,
) -> None:
    """Verify old -> new ancestry through GitHub without requiring local Git history."""

    if repository != CANONICAL_REPOSITORY:
        raise SourceContextError(
            "UNSUPPORTED_SOURCE_IDENTITY",
            f"unsupported composition source identity: {repository}",
        )
    if FULL_SHA.fullmatch(old_revision) is None:
        raise SourceContextError(
            "OLD_SOURCE_REVISION_UNAVAILABLE",
            "old composition source revision is invalid or unavailable: "
            f"{old_revision}",
        )
    _validate_revision(new_revision, label="source revision")
    if old_revision == new_revision:
        return

    url = (
        f"https://api.github.com/repos/{repository}/compare/"
        f"{old_revision}...{new_revision}"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "composition-source-context/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(request, timeout=30) as response:
            data = response.read(COMPARE_RESPONSE_LIMIT + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise SourceContextError(
                "OLD_SOURCE_REVISION_UNAVAILABLE",
                "old composition source revision is unavailable from the canonical "
                f"GitHub history: {old_revision}",
            ) from exc
        raise SourceContextError(
            "SOURCE_TRANSITION_UNAVAILABLE",
            f"cannot verify Composition source ancestry through GitHub: HTTP {exc.code}",
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SourceContextError(
            "SOURCE_TRANSITION_UNAVAILABLE",
            f"cannot verify Composition source ancestry through GitHub: {exc}",
        ) from exc

    if len(data) > COMPARE_RESPONSE_LIMIT:
        raise SourceContextError(
            "SOURCE_TRANSITION_UNAVAILABLE",
            "GitHub compare response exceeds the size limit",
        )
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise SourceContextError(
            "SOURCE_TRANSITION_UNAVAILABLE",
            f"GitHub compare response is invalid: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise SourceContextError(
            "SOURCE_TRANSITION_UNAVAILABLE",
            "GitHub compare response must be a JSON object",
        )
    status = payload.get("status")
    if status in {"ahead", "identical"}:
        return
    if status in {"behind", "diverged"}:
        raise SourceContextError(
            "SOURCE_REVISION_NOT_DESCENDANT",
            "target composition source revision "
            f"{new_revision} is not a descendant of old revision {old_revision}",
        )
    raise SourceContextError(
        "SOURCE_TRANSITION_UNAVAILABLE",
        f"GitHub compare response returned unsupported status: {status!r}",
    )


@dataclass(frozen=True)
class GitSourceContext:
    """Reviewed-checkout source context used by Composition authority maintainers."""

    root: Path

    def run_git(
        self,
        *arguments: str,
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), *arguments],
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise SourceContextError(
                "GIT_UNAVAILABLE",
                f"cannot execute git: {exc}",
            ) from exc
        if result.returncode != 0 and not allow_failure:
            raise SourceContextError(
                "GIT_FAILED",
                f"git {' '.join(arguments)} failed: {result.stderr.strip()}",
            )
        return result

    def revision(self) -> str:
        revision = self.run_git("rev-parse", "HEAD").stdout.strip()
        _validate_revision(revision, label="source revision")
        dirty = self.run_git(
            "status",
            "--porcelain",
            "--untracked-files=no",
        ).stdout.strip()
        if dirty:
            raise SourceContextError(
                "DIRTY_SOURCE",
                "composition source checkout has tracked modifications; "
                "commit or discard them before composing",
            )
        return revision

    def assert_authority(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise SourceContextError(
                "SOURCE_OUTSIDE_REPOSITORY",
                f"source authority is outside the composition checkout: {path}",
            ) from exc
        if path.is_symlink() or not path.is_file():
            raise SourceContextError(
                "INVALID_SOURCE_AUTHORITY",
                f"source authority must be a regular non-symlink file: {relative}",
            )
        tracked = self.run_git(
            "ls-files",
            "--error-unmatch",
            "--",
            relative,
            allow_failure=True,
        )
        if tracked.returncode != 0:
            raise SourceContextError(
                "UNTRACKED_SOURCE_AUTHORITY",
                "source authority is not tracked by the bound Git revision: "
                f"{relative}",
            )

    def verify_descendant(self, old_revision: str, new_revision: str) -> None:
        if FULL_SHA.fullmatch(old_revision) is None:
            raise SourceContextError(
                "OLD_SOURCE_REVISION_UNAVAILABLE",
                "old composition source revision is invalid or unavailable: "
                f"{old_revision}",
            )
        _validate_revision(new_revision, label="source revision")
        exists = self.run_git(
            "cat-file",
            "-e",
            f"{old_revision}^{{commit}}",
            allow_failure=True,
        )
        if exists.returncode != 0:
            raise SourceContextError(
                "OLD_SOURCE_REVISION_UNAVAILABLE",
                "old composition source revision is not available in the local "
                f"source history: {old_revision}",
            )
        ancestry = self.run_git(
            "merge-base",
            "--is-ancestor",
            old_revision,
            new_revision,
            allow_failure=True,
        )
        if ancestry.returncode == 1:
            raise SourceContextError(
                "SOURCE_REVISION_NOT_DESCENDANT",
                "target composition source revision "
                f"{new_revision} is not a descendant of old revision {old_revision}",
            )
        if ancestry.returncode != 0:
            raise SourceContextError(
                "GIT_FAILED",
                "cannot establish source revision ancestry for managed operation",
            )


@dataclass(frozen=True)
class SnapshotSourceContext:
    """Immutable archive-backed source context for normal Composition consumers."""

    root: Path
    repository: str
    pinned_revision: str
    files: dict[str, str]

    def revision(self) -> str:
        if self.repository != CANONICAL_REPOSITORY:
            raise SourceContextError(
                "UNSUPPORTED_SOURCE_IDENTITY",
                f"unsupported composition source identity: {self.repository}",
            )
        return _validate_revision(self.pinned_revision, label="source revision")

    def _assert_authority_parent_chain(self, relative: str) -> None:
        if self.root.is_symlink() or not self.root.is_dir():
            raise SourceContextError(
                "INVALID_SOURCE_CONTEXT",
                "source snapshot root must remain a regular non-symlink directory",
            )
        current = self.root
        for part in PurePosixPath(relative).parts[:-1]:
            current = current / part
            if current.is_symlink() or not current.is_dir():
                raise SourceContextError(
                    "INVALID_SOURCE_AUTHORITY",
                    "source authority parent must remain a regular non-symlink "
                    f"directory: {relative}",
                )

    def assert_authority(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise SourceContextError(
                "SOURCE_OUTSIDE_REPOSITORY",
                f"source authority is outside the composition snapshot: {path}",
            ) from exc
        expected = self.files.get(relative)
        if expected is None:
            raise SourceContextError(
                "UNTRACKED_SOURCE_AUTHORITY",
                "source authority is not present in the immutable source snapshot: "
                f"{relative}",
            )
        self._assert_authority_parent_chain(relative)
        if path.is_symlink() or not path.is_file():
            raise SourceContextError(
                "INVALID_SOURCE_AUTHORITY",
                f"source authority must be a regular non-symlink file: {relative}",
            )
        try:
            resolved_root = self.root.resolve(strict=True)
            resolved_path = path.resolve(strict=True)
            resolved_path.relative_to(resolved_root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise SourceContextError(
                "INVALID_SOURCE_AUTHORITY",
                f"source authority must remain inside the immutable snapshot: {relative}",
            ) from exc
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise SourceContextError(
                "INVALID_SOURCE_AUTHORITY",
                f"cannot read source authority {relative}: {exc}",
            ) from exc
        self._assert_authority_parent_chain(relative)
        if actual != expected:
            raise SourceContextError(
                "DIRTY_SOURCE",
                "immutable source snapshot bytes changed after acquisition: "
                f"{relative}",
            )

    def verify_descendant(self, old_revision: str, new_revision: str) -> None:
        if new_revision != self.revision():
            raise SourceContextError(
                "INVALID_SOURCE_REVISION",
                "managed transition target does not match the acquired immutable "
                f"source revision: {new_revision}",
            )
        verify_github_descendant(self.repository, old_revision, new_revision)


def _validate_snapshot_path(path: str) -> None:
    value = PurePosixPath(path)
    if (
        value.is_absolute()
        or not value.parts
        or any(part in {"", ".", ".."} or "\\" in part for part in value.parts)
    ):
        raise SourceContextError(
            "INVALID_SOURCE_CONTEXT",
            f"invalid source snapshot path: {path!r}",
        )


def load_snapshot_context(root: Path, metadata_path: Path) -> SnapshotSourceContext:
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise SourceContextError(
            "INVALID_SOURCE_CONTEXT",
            "source snapshot metadata must be a regular non-symlink file",
        )
    try:
        payload = json.loads(
            metadata_path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise SourceContextError(
            "INVALID_SOURCE_CONTEXT",
            f"cannot read source snapshot metadata: {exc}",
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "repository",
        "revision",
        "files",
    }:
        raise SourceContextError(
            "INVALID_SOURCE_CONTEXT",
            "source snapshot metadata has unsupported members",
        )
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise SourceContextError(
            "INVALID_SOURCE_CONTEXT",
            "unsupported source snapshot metadata schema",
        )
    repository = payload["repository"]
    revision = payload["revision"]
    files = payload["files"]
    if repository != CANONICAL_REPOSITORY:
        raise SourceContextError(
            "UNSUPPORTED_SOURCE_IDENTITY",
            f"unsupported composition source identity: {repository}",
        )
    if not isinstance(revision, str):
        raise SourceContextError(
            "INVALID_SOURCE_CONTEXT",
            "source snapshot revision must be a string",
        )
    _validate_revision(revision, label="source revision")
    if not isinstance(files, dict) or not files:
        raise SourceContextError(
            "INVALID_SOURCE_CONTEXT",
            "source snapshot file inventory must be a non-empty object",
        )
    normalized: dict[str, str] = {}
    for path, digest in files.items():
        if not isinstance(path, str) or not isinstance(digest, str):
            raise SourceContextError(
                "INVALID_SOURCE_CONTEXT",
                "source snapshot inventory entries must map paths to SHA-256 strings",
            )
        _validate_snapshot_path(path)
        if SHA256.fullmatch(digest) is None:
            raise SourceContextError(
                "INVALID_SOURCE_CONTEXT",
                f"invalid source snapshot digest for {path}",
            )
        normalized[path] = digest
    return SnapshotSourceContext(
        root=root,
        repository=repository,
        pinned_revision=revision,
        files=normalized,
    )


def context_from_environment(root: Path) -> GitSourceContext | SnapshotSourceContext:
    metadata = os.environ.get(SOURCE_CONTEXT_ENV)
    if not metadata:
        return GitSourceContext(root)
    return load_snapshot_context(root, Path(metadata).expanduser().resolve())
