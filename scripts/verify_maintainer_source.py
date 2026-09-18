#!/usr/bin/env python3
"""Verify the Site maintainer Skill against its immutable Policy snapshot.

The ``--local`` mode reads an exact Git object already present in the local
object store.  The explicit ``--remote`` mode performs the network-backed
confirmation against the full commit SHA.  The normal Site source-ready
preflight deliberately does not invoke either network retrieval or a mutable
fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REVISION = "a878da560c5286634b21671b54793e26ed8167b2"
CANONICAL_SKILL_PATH = "repository-skills/land-templates-stack/SKILL.md"
CANONICAL_SKILL_BLOB = "b433bdf781eb1fd0f32a525bfd68bac2563316d7"
CANONICAL_RULE_PATH = "repository-policy/stacked-pr-landing.md"
CANONICAL_RULE_BLOB = "9dd1c5498dd9b37ef91afd65ad400fbdee13ee29"
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def git_blob_sha(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def verify_source_reference(
    source: dict,
    fetch_file,
    *,
    expected_revision: str | None = None,
    expected_skill_blob: str | None = None,
    expected_rule_blob: str | None = None,
) -> dict[str, str]:
    """Validate metadata and both immutable source objects."""

    if source.get("schema_version") != 1:
        raise ValueError("unsupported source reference schema")
    if source.get("kind") != "repository-maintainer-skill-reference":
        raise ValueError("unsupported source reference kind")
    repository = source.get("repository")
    revision = source.get("revision")
    path = source.get("path")
    blob = source.get("blob_sha")
    if repository != "TakashiSasaki/templates":
        raise ValueError("unexpected source repository")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise ValueError("source revision must be an immutable full SHA")
    if path != CANONICAL_SKILL_PATH:
        raise ValueError("unexpected canonical Skill path")
    if not isinstance(blob, str) or FULL_SHA.fullmatch(blob) is None:
        raise ValueError("source blob must be a full Git blob SHA")
    for name, actual, expected in (
        ("revision", revision, expected_revision),
        ("Skill blob", blob, expected_skill_blob),
    ):
        if expected is not None and actual != expected:
            raise ValueError(f"unexpected canonical {name}: {actual}")

    skill = fetch_file(repository, revision, path)
    observed_skill = git_blob_sha(skill)
    if observed_skill != blob:
        raise ValueError(f"canonical Skill blob mismatch: {observed_skill}")
    if expected_skill_blob is not None and observed_skill != expected_skill_blob:
        raise ValueError(f"canonical Skill object mismatch: {observed_skill}")

    rule = fetch_file(repository, revision, CANONICAL_RULE_PATH)
    observed_rule = git_blob_sha(rule)
    if expected_rule_blob is not None and observed_rule != expected_rule_blob:
        raise ValueError(f"canonical rule blob mismatch: {observed_rule}")
    return {"skill_blob": observed_skill, "rule_blob": observed_rule}


def fetch_local_file(repository: str, revision: str, path: str) -> bytes:
    """Read only an exact object already present in this checkout's Git store."""

    if repository != "TakashiSasaki/templates":
        raise ValueError("unexpected source repository")
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)


def fetch_remote_file(repository: str, revision: str, path: str) -> bytes:
    """Read a file at an exact commit URL; never resolve a branch or tag."""

    url = (
        f"https://raw.githubusercontent.com/{repository}/"
        f"{quote(revision, safe='')}/{quote(path, safe='/')}"
    )
    request = Request(url, headers={"User-Agent": "templates-maintainer-source-check"})
    with urlopen(request, timeout=15) as response:
        return response.read()


def load_source(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-json",
        type=Path,
        default=ROOT / ".agents/skills/land-templates-stack/source.json",
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--local", action="store_true", help="use an existing exact Git object")
    modes.add_argument("--remote", action="store_true", help="confirm exact bytes over HTTPS")
    args = parser.parse_args(argv)
    source = load_source(args.source_json)
    fetch_file = fetch_local_file if args.local else fetch_remote_file
    result = verify_source_reference(
        source,
        fetch_file,
        expected_revision=CANONICAL_REVISION,
        expected_skill_blob=CANONICAL_SKILL_BLOB,
        expected_rule_blob=CANONICAL_RULE_BLOB,
    )
    print(json.dumps({"revision": source["revision"], **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
