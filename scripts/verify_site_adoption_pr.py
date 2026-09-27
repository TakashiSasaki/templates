#!/usr/bin/env python3
"""Fail-closed identity checks for deterministic Site adoption PRs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
LOCK_PATH = "integration-source.json"
PR_TITLE = "chore(site): adopt qualified Integration Bundle"
TRANSACTION_MARKER = "<!-- site-publication-transaction-v1"
REVIEW_BOUNDARY = "independent_exact_head_review_then_human_merge"


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full lowercase commit SHA")
    return value


def _require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} must be a full lowercase SHA-256 digest")
    return value


def _git_text(repository_root: Path, arguments: list[str], label: str) -> str:
    try:
        value = subprocess.check_output(
            ["git", "-C", str(repository_root), *arguments],
            stderr=subprocess.PIPE,
        ).decode("ascii").strip()
    except (subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        raise ValueError(f"could not resolve {label} from the Site repository") from exc
    return value


def read_live_site_sha(repository: str) -> str:
    """Read the live Site ref through GitHub; API failures are not a fallback."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repository}/git/ref/heads/site", "--jq", ".object.sha"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("could not read the live Site target from GitHub") from exc
    return result.stdout.strip()


def verify_live_site_target(*, expected_base: str, repository_root: Path, repository: str) -> None:
    """Require GitHub's current `site` ref and this exact candidate checkout."""
    expected_base = _require_sha(expected_base, "expected Site consumer base")
    local_head = _git_text(repository_root, ["rev-parse", "HEAD"], "the checked-out Site candidate")
    live_base = _require_sha(read_live_site_sha(repository), "live Site target revision")
    if local_head != expected_base:
        parent_line = _git_text(
            repository_root,
            ["rev-list", "--parents", "-n", "1", local_head],
            "the checked-out Site candidate parent",
        )
        parents = parent_line.split()
        if len(parents) != 2 or parents[1] != expected_base:
            raise ValueError("candidate checkout is not the exact Site base or its single-commit adoption")
    if live_base != expected_base:
        raise ValueError("live Site target differs from the reconciled consumer base")


def find_matching_pr_number(pages: Any, expected_branch: str) -> int | None:
    """Find a unique PR head ref across all paginated PR states and repositories."""
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("GitHub pull request listing is malformed")
    matches: list[dict[str, Any]] = []
    for page in pages:
        for pr in page:
            if not isinstance(pr, dict):
                raise ValueError("GitHub pull request listing contains a malformed entry")
            head = pr.get("head")
            if not isinstance(head, dict):
                raise ValueError("GitHub pull request listing is missing a head binding")
            if head.get("ref") == expected_branch:
                matches.append(pr)
    if len(matches) > 1:
        raise ValueError("multiple pull requests use the deterministic Site adoption branch")
    if not matches:
        return None
    number = matches[0].get("number")
    if type(number) is not int or number <= 0:
        raise ValueError("matching pull request has an invalid number")
    return number


def render_pr_body(*, repository: str, consumer_base: str, idempotency_key: str, candidate_lock: Path) -> str:
    consumer_base = _require_sha(consumer_base, "Site consumer base")
    idempotency_key = _require_digest(idempotency_key, "Site adoption idempotency key")
    transaction = {
        "schema_version": 1,
        "repository": repository,
        "consumer_base": consumer_base,
        "idempotency_key": idempotency_key,
        "candidate_lock_sha256": hashlib.sha256(candidate_lock.read_bytes()).hexdigest(),
        "review_boundary": REVIEW_BOUNDARY,
    }
    return (
        "Guarded deterministic Site lock adoption.\n\n"
        f"Consumer base: {consumer_base}. Idempotency key: {idempotency_key}.\n\n"
        "The controller stops after creating or reconciling this PR. It does not approve, "
        "request auto-merge, or merge. Independent exact-head review and separate human "
        "merge authorization are required before landing. Post-merge automation starts "
        "only after an authorized merge.\n\n"
        f"{TRANSACTION_MARKER}\n"
        f"{json.dumps(transaction, sort_keys=True, separators=(',', ':'))}\n"
        "-->\n"
    )


def write_pr_body(*, repository: str, consumer_base: str, idempotency_key: str, candidate_lock: Path, output: Path) -> None:
    output.write_text(
        render_pr_body(
            repository=repository,
            consumer_base=consumer_base,
            idempotency_key=idempotency_key,
            candidate_lock=candidate_lock,
        ),
        encoding="utf-8",
    )


def _transaction_from_body(body: Any) -> dict[str, Any]:
    if not isinstance(body, str):
        raise ValueError("existing Site adoption PR body is missing")
    start = body.find(TRANSACTION_MARKER)
    if start < 0 or body.find(TRANSACTION_MARKER, start + len(TRANSACTION_MARKER)) >= 0:
        raise ValueError("existing Site adoption PR has no unique transaction binding")
    payload_start = start + len(TRANSACTION_MARKER)
    end = body.find("\n-->", payload_start)
    if end < 0:
        raise ValueError("existing Site adoption PR transaction binding is incomplete")
    try:
        transaction = json.loads(body[payload_start:end].strip())
    except json.JSONDecodeError as exc:
        raise ValueError("existing Site adoption PR transaction binding is malformed") from exc
    if not isinstance(transaction, dict):
        raise ValueError("existing Site adoption PR transaction binding is malformed")
    return transaction


def verify_existing_site_adoption_pr(
    *,
    pr: dict[str, Any],
    repository_root: Path,
    repository: str,
    expected_base: str,
    expected_tree: str,
    expected_branch: str,
    expected_idempotency_key: str,
    candidate_lock: Path,
    remote_head_ref: str,
) -> dict[str, Any]:
    """Prove an existing PR is the exact candidate before it can be reused."""
    expected_base = _require_sha(expected_base, "expected Site consumer base")
    expected_tree = _require_sha(expected_tree, "expected deterministic adoption tree")
    expected_idempotency_key = _require_digest(expected_idempotency_key, "Site adoption idempotency key")
    if expected_branch != f"automation/site-publication-{expected_idempotency_key}":
        raise ValueError("deterministic Site adoption branch does not match the current idempotency key")
    if not isinstance(pr, dict):
        raise ValueError("existing Site adoption PR response is malformed")
    if pr.get("state") != "open":
        raise ValueError("existing Site adoption PR is not open")
    if pr.get("merged") is not False or "merged_at" not in pr or pr.get("merged_at") is not None:
        raise ValueError("existing Site adoption PR is not explicitly unmerged")
    if pr.get("draft") is not False:
        raise ValueError("existing Site adoption PR is a draft or has no explicit draft state")
    if pr.get("title") != PR_TITLE:
        raise ValueError("existing Site adoption PR title is not deterministic")

    base = pr.get("base")
    head = pr.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise ValueError("existing Site adoption PR base or head binding is malformed")
    if base.get("ref") != "site" or base.get("sha") != expected_base:
        raise ValueError("existing Site adoption PR base branch or base SHA is stale")
    if head.get("ref") != expected_branch:
        raise ValueError("existing Site adoption PR head branch is not the expected automation branch")
    head_sha = _require_sha(head.get("sha"), "existing Site adoption PR head SHA")
    for side, binding in (("base", base), ("head", head)):
        repo = binding.get("repo")
        if not isinstance(repo, dict) or repo.get("full_name") != repository:
            raise ValueError(f"existing Site adoption PR {side} repository is not the target repository")

    lock_bytes = candidate_lock.read_bytes()
    expected_transaction = {
        "schema_version": 1,
        "repository": repository,
        "consumer_base": expected_base,
        "idempotency_key": expected_idempotency_key,
        "candidate_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "review_boundary": REVIEW_BOUNDARY,
    }
    if _transaction_from_body(pr.get("body")) != expected_transaction:
        raise ValueError("existing Site adoption PR transaction binding differs from the current candidate")

    remote_head = _git_text(repository_root, ["rev-parse", "--verify", remote_head_ref], "the automation branch tip")
    if remote_head != head_sha:
        raise ValueError("existing Site adoption PR head differs from the remote deterministic branch tip")
    parent_line = _git_text(
        repository_root,
        ["rev-list", "--parents", "-n", "1", head_sha],
        "the existing Site adoption PR head commit",
    )
    parents = parent_line.split()
    if len(parents) != 2 or parents[1] != expected_base:
        raise ValueError("existing Site adoption PR head is not a single commit on the exact Site base")
    actual_tree = _git_text(repository_root, ["rev-parse", f"{head_sha}^{{tree}}"], "the existing Site adoption PR head tree")
    if actual_tree != expected_tree:
        raise ValueError("existing Site adoption PR tree differs from the current candidate tree")
    actual_paths = set(_git_text(
        repository_root,
        ["diff", "--name-only", expected_base, head_sha],
        "the existing Site adoption PR changed paths",
    ).splitlines())
    if actual_paths != {LOCK_PATH}:
        raise ValueError("existing Site adoption PR contains unexpected changed paths")
    committed_lock = subprocess.run(
        ["git", "-C", str(repository_root), "show", f"{head_sha}:{LOCK_PATH}"],
        check=True,
        capture_output=True,
    ).stdout
    if committed_lock != lock_bytes:
        raise ValueError("existing Site adoption PR lock bytes differ from the exact candidate lock")
    return pr


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON input {path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    find = commands.add_parser("find")
    find.add_argument("--pull-requests", type=Path, required=True)
    find.add_argument("--expected-branch", required=True)

    target = commands.add_parser("verify-target")
    target.add_argument("--repository-root", type=Path, required=True)
    target.add_argument("--repository", required=True)
    target.add_argument("--expected-base", required=True)

    verify = commands.add_parser("verify-pr")
    verify.add_argument("--pr-json", type=Path, required=True)
    verify.add_argument("--repository-root", type=Path, required=True)
    verify.add_argument("--repository", required=True)
    verify.add_argument("--expected-base", required=True)
    verify.add_argument("--expected-tree", required=True)
    verify.add_argument("--expected-branch", required=True)
    verify.add_argument("--expected-idempotency-key", required=True)
    verify.add_argument("--candidate-lock", type=Path, required=True)
    verify.add_argument("--remote-head-ref", required=True)

    body = commands.add_parser("write-body")
    body.add_argument("--repository", required=True)
    body.add_argument("--consumer-base", required=True)
    body.add_argument("--idempotency-key", required=True)
    body.add_argument("--candidate-lock", type=Path, required=True)
    body.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "find":
            number = find_matching_pr_number(_load_json(args.pull_requests), args.expected_branch)
            if number is not None:
                print(number)
        elif args.command == "verify-target":
            verify_live_site_target(
                expected_base=args.expected_base,
                repository_root=args.repository_root,
                repository=args.repository,
            )
        elif args.command == "write-body":
            write_pr_body(
                repository=args.repository,
                consumer_base=args.consumer_base,
                idempotency_key=args.idempotency_key,
                candidate_lock=args.candidate_lock,
                output=args.output,
            )
        else:
            verify_existing_site_adoption_pr(
                pr=_load_json(args.pr_json),
                repository_root=args.repository_root,
                repository=args.repository,
                expected_base=args.expected_base,
                expected_tree=args.expected_tree,
                expected_branch=args.expected_branch,
                expected_idempotency_key=args.expected_idempotency_key,
                candidate_lock=args.candidate_lock,
                remote_head_ref=args.remote_head_ref,
            )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
