#!/usr/bin/env python3
"""Validate a maintainer Skill reference against immutable local Git objects.

This is deliberately a read-only source-reference check.  It is not a landing
engine and it never resolves a branch, tag, or consumer-worktree path.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

EXPECTED_REPOSITORY = "TakashiSasaki/templates"
CANONICAL_SKILL_PATH = "repository-skills/land-templates-stack/SKILL.md"
CANONICAL_RULE_PATH = "repository-policy/stacked-pr-landing.md"
CANONICAL_PLANNER_PATH = (
    "repository-skills/land-templates-stack/scripts/plan_review_scope.py"
)
CANONICAL_OBSERVER_PATH = (
    "repository-skills/land-templates-stack/scripts/observe_pr_state.py"
)
CANONICAL_OBSERVER_LIBRARY_PATH = (
    "repository-skills/land-templates-stack/scripts/pr_state_observation.py"
)
BASE_SOURCE_CLOSURE_PATHS = (CANONICAL_RULE_PATH, CANONICAL_PLANNER_PATH)
OPTIONAL_SOURCE_CLOSURE_PATHS = (
    CANONICAL_OBSERVER_PATH,
    CANONICAL_OBSERVER_LIBRARY_PATH,
)
SOURCE_CLOSURE_PATHS = BASE_SOURCE_CLOSURE_PATHS + OPTIONAL_SOURCE_CLOSURE_PATHS
FULL_SHA = re.compile(r"[0-9a-f]{40}")


class SourceReferenceError(ValueError):
    """Raised when a source reference cannot be proven immutable and exact."""


@dataclass(frozen=True)
class VerifiedBlob:
    """One immutable source file retained with its verified Git identity."""

    repository: str
    revision: str
    path: str
    blob_sha: str
    content: bytes


@dataclass(frozen=True)
class VerifiedSource:
    revision: str
    skill: bytes
    rule: bytes
    skill_blob: str
    rule_blob: str
    closure: dict[str, bytes]


def git_blob_sha(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _git(repo: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=repo,
            env=environment,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        raise SourceReferenceError("immutable Git object is unavailable") from exc


def _git_bytes(repo: Path, *arguments: str) -> bytes:
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        return subprocess.check_output(
            ["git", *arguments], cwd=repo, env=environment, stderr=subprocess.PIPE
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise SourceReferenceError("immutable Git object is unavailable") from exc


def _require_blob(repo: Path, revision: str, path: str) -> tuple[str, bytes]:
    object_id = _git(repo, "rev-parse", "--verify", f"{revision}:{path}")
    if FULL_SHA.fullmatch(object_id) is None or _git(repo, "cat-file", "-t", object_id) != "blob":
        raise SourceReferenceError(f"canonical path is not a blob: {path}")
    payload = _git_bytes(repo, "show", f"{revision}:{path}")
    if git_blob_sha(payload) != object_id:
        raise SourceReferenceError(f"canonical blob changed while reading: {path}")
    return object_id, payload


def verify_blob_source(
    source: Mapping[str, object],
    *,
    repo: Path,
    expected_path: str,
) -> VerifiedBlob:
    """Read one declared source only from its exact immutable Git revision."""

    if source.get("repository") != EXPECTED_REPOSITORY:
        raise SourceReferenceError("unexpected source repository")
    revision = source.get("revision")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise SourceReferenceError("source revision must be a full lowercase SHA")
    path = source.get("path")
    if path != expected_path:
        raise SourceReferenceError(f"unexpected source path: {path}")
    declared_blob = source.get("blob_sha")
    if not isinstance(declared_blob, str) or FULL_SHA.fullmatch(declared_blob) is None:
        raise SourceReferenceError("source blob must be a full lowercase SHA")
    if source.get("trusted") is not True:
        raise SourceReferenceError("source must explicitly identify a trusted source")
    if _git(repo, "cat-file", "-t", revision) != "commit":
        raise SourceReferenceError("source revision must name a commit object")
    actual_blob, content = _require_blob(repo, revision, expected_path)
    if actual_blob != declared_blob:
        raise SourceReferenceError("declared source blob does not match the snapshot")
    return VerifiedBlob(EXPECTED_REPOSITORY, revision, expected_path, actual_blob, content)


def verify_blob_payload(
    source: Mapping[str, object],
    *,
    content: bytes,
    actual_blob: str | None = None,
    expected_path: str,
) -> VerifiedBlob:
    """Verify bytes fetched through another transport against a source binding."""

    if source.get("repository") != EXPECTED_REPOSITORY:
        raise SourceReferenceError("unexpected source repository")
    revision = source.get("revision")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise SourceReferenceError("source revision must be a full lowercase SHA")
    path = source.get("path")
    if path != expected_path:
        raise SourceReferenceError(f"unexpected source path: {path}")
    declared_blob = source.get("blob_sha")
    if not isinstance(declared_blob, str) or FULL_SHA.fullmatch(declared_blob) is None:
        raise SourceReferenceError("source blob must be a full lowercase SHA")
    if source.get("trusted") is not True:
        raise SourceReferenceError("source must explicitly identify a trusted source")
    computed_blob = git_blob_sha(content)
    if actual_blob is not None and actual_blob != computed_blob:
        raise SourceReferenceError("transport source blob does not match its content")
    if computed_blob != declared_blob:
        raise SourceReferenceError("declared source blob does not match transport content")
    return VerifiedBlob(EXPECTED_REPOSITORY, revision, expected_path, computed_blob, content)


def load_python_module(source: VerifiedBlob, module_name: str) -> ModuleType:
    """Execute already-verified source bytes as an isolated Python module."""

    module = ModuleType(module_name)
    module.__file__ = f"{source.revision}:{source.path}"
    code = compile(source.content, module.__file__, "exec")
    exec(code, module.__dict__)
    return module


def required_source_closure_paths(skill: bytes) -> tuple[str, ...]:
    """Require only the support files referenced by the candidate Skill."""

    required = list(BASE_SOURCE_CLOSURE_PATHS)
    if CANONICAL_OBSERVER_PATH.encode("utf-8") in skill:
        required.extend(OPTIONAL_SOURCE_CLOSURE_PATHS)
    return tuple(required)


def verify_source_reference(
    source: dict[str, object],
    *,
    repo: Path,
    expected_skill_blob: str | None = None,
    expected_rule_blob: str | None = None,
    expected_planner_blob: str | None = None,
) -> VerifiedSource:
    """Resolve both canonical files through one exact immutable revision."""

    schema_version = source.get("schema_version")
    if type(schema_version) is not int or schema_version != 2:
        raise SourceReferenceError("source reference must use schema version 2")
    if (
        not isinstance(expected_planner_blob, str)
        or FULL_SHA.fullmatch(expected_planner_blob) is None
    ):
        raise SourceReferenceError(
            "an expected planner blob is required for the adopted source"
        )
    if source.get("kind") != "repository-maintainer-skill-reference":
        raise SourceReferenceError("unsupported source reference kind")
    if source.get("repository") != EXPECTED_REPOSITORY:
        raise SourceReferenceError("unexpected source repository")
    revision = source.get("revision")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise SourceReferenceError("source revision must be a full lowercase SHA")
    path = source.get("path")
    if path != CANONICAL_SKILL_PATH:
        raise SourceReferenceError("unexpected canonical Skill path")
    declared_skill_blob = source.get("blob_sha")
    if not isinstance(declared_skill_blob, str) or FULL_SHA.fullmatch(declared_skill_blob) is None:
        raise SourceReferenceError("source blob must be a full lowercase SHA")

    if _git(repo, "cat-file", "-t", revision) != "commit":
        raise SourceReferenceError("source revision must name a commit object")
    _git(repo, "cat-file", "-e", f"{revision}^{{commit}}")
    skill_blob, skill = _require_blob(repo, revision, CANONICAL_SKILL_PATH)
    rule_blob, rule = _require_blob(repo, revision, CANONICAL_RULE_PATH)
    if skill_blob != declared_skill_blob:
        raise SourceReferenceError("declared Skill blob does not match the snapshot")
    if expected_skill_blob is not None and skill_blob != expected_skill_blob:
        raise SourceReferenceError("Skill blob does not match the adopted pin")
    if expected_rule_blob is not None and rule_blob != expected_rule_blob:
        raise SourceReferenceError("rule blob does not match the adopted pin")
    closure: dict[str, bytes] = {CANONICAL_RULE_PATH: rule}
    declared_closure = source.get("closure")
    if not isinstance(declared_closure, list):
        raise SourceReferenceError("schema version 2 requires an explicit source closure")
    entries: dict[str, str] = {}
    for item in declared_closure:
        if not isinstance(item, dict):
            raise SourceReferenceError("source closure entries must be objects")
        path = item.get("path")
        blob = item.get("blob_sha")
        if not isinstance(path, str) or path not in SOURCE_CLOSURE_PATHS:
            raise SourceReferenceError("source closure contains an unexpected path")
        if not isinstance(blob, str) or FULL_SHA.fullmatch(blob) is None:
            raise SourceReferenceError("source closure blob must be a full lowercase SHA")
        if path in entries:
            raise SourceReferenceError("source closure contains a duplicate path")
        entries[path] = blob
    required_paths = required_source_closure_paths(skill)
    if set(entries) != set(required_paths):
        raise SourceReferenceError("source closure is incomplete")
    for path, expected_blob in entries.items():
        actual_blob, payload = _require_blob(repo, revision, path)
        if actual_blob != expected_blob:
            raise SourceReferenceError(f"declared closure blob does not match: {path}")
        closure[path] = payload
    if entries[CANONICAL_PLANNER_PATH] != expected_planner_blob:
        raise SourceReferenceError("planner blob does not match the adopted pin")
    return VerifiedSource(revision, skill, rule, skill_blob, rule_blob, closure)
