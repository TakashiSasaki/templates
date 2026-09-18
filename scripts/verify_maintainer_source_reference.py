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
from dataclasses import dataclass
from pathlib import Path

EXPECTED_REPOSITORY = "TakashiSasaki/templates"
CANONICAL_SKILL_PATH = "repository-skills/land-templates-stack/SKILL.md"
CANONICAL_RULE_PATH = "repository-policy/stacked-pr-landing.md"
FULL_SHA = re.compile(r"[0-9a-f]{40}")


class SourceReferenceError(ValueError):
    """Raised when a source reference cannot be proven immutable and exact."""


@dataclass(frozen=True)
class VerifiedSource:
    revision: str
    skill: bytes
    rule: bytes
    skill_blob: str
    rule_blob: str


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


def verify_source_reference(
    source: dict[str, object],
    *,
    repo: Path,
    expected_skill_blob: str | None = None,
    expected_rule_blob: str | None = None,
) -> VerifiedSource:
    """Resolve both canonical files through one exact immutable revision."""

    if source.get("schema_version") != 1:
        raise SourceReferenceError("unsupported source reference schema")
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
    return VerifiedSource(revision, skill, rule, skill_blob, rule_blob)
