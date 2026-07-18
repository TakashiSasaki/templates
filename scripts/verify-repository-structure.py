#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

DOCUMENT_PATH = Path("docs/repository-structure.md")
MANIFEST_PATH = Path("docs/generated/repository-preview/index.json")
REMOTE_BOOTSTRAP_REF = "refs/remotes/origin/bootstrap-agent-policy"
BRANCH_REFS = {
    "main": "HEAD",
    "bootstrap-agent-policy": REMOTE_BOOTSTRAP_REF,
}


def tracked_paths(ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", ref],
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def tree_placeholder(branch: str) -> str:
    return (
        f'<div class="repository-tree" data-repository-branch="{branch}">\n'
        '<p class="repository-tree__loading" role="status">'
        "ツリーを読み込んでいます…</p>\n"
        "</div>"
    )


def markers(branch: str) -> tuple[str, str]:
    return (
        f"<!-- BEGIN VERIFIED TREE: {branch} -->",
        f"<!-- END VERIFIED TREE: {branch} -->",
    )


def tree_block(branch: str) -> str:
    start, end = markers(branch)
    return f"{start}\n{tree_placeholder(branch)}\n{end}"


def replace_block(document: str, branch: str) -> str:
    start, end = markers(branch)
    start_index = document.find(start)
    end_index = document.find(end)
    if start_index < 0 or end_index < 0 or end_index < start_index:
        raise ValueError(f"Missing or invalid tree markers for {branch}")
    end_index += len(end)
    return document[:start_index] + tree_block(branch) + document[end_index:]


def extract_tree(document: str, branch: str) -> str:
    start, end = markers(branch)
    start_index = document.find(start)
    end_index = document.find(end)
    if start_index < 0 or end_index < 0 or end_index < start_index:
        raise ValueError(f"Missing or invalid tree markers for {branch}")
    return document[start_index + len(start) : end_index].strip()


def check_placeholder(document: str, branch: str) -> bool:
    expected = tree_placeholder(branch)
    actual = extract_tree(document, branch)
    if actual == expected:
        print(f"Documented tree placeholder matches {branch}.")
        return True
    print(f"Documented tree placeholder does not match {branch}.", file=sys.stderr)
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=f"documented/{branch}",
        tofile=f"expected/{branch}",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    return False


def check_manifest() -> bool:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    success = True
    for branch, ref in BRANCH_REFS.items():
        expected = sorted(tracked_paths(ref))
        branch_data = manifest.get("branches", {}).get(branch, {})
        actual = sorted(branch_data.get("files", {}))
        if actual == expected:
            print(f"Published preview tree matches {branch}.")
            continue
        success = False
        print(f"Published preview tree does not match {branch}.", file=sys.stderr)
        diff = difflib.unified_diff(
            actual,
            expected,
            fromfile=f"preview-manifest/{branch}",
            tofile=f"git/{branch}",
            lineterm="",
        )
        print("\n".join(diff), file=sys.stderr)
    return success


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify published repository trees against Git tree objects."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail when publication is stale.")
    mode.add_argument("--update", action="store_true", help="Rewrite documented placeholders.")
    args = parser.parse_args()

    document = DOCUMENT_PATH.read_text(encoding="utf-8")
    if args.update:
        updated = document
        for branch in BRANCH_REFS:
            updated = replace_block(updated, branch)
        DOCUMENT_PATH.write_text(updated, encoding="utf-8")
        print(f"Updated {DOCUMENT_PATH}.")
        return 0

    placeholders_match = all(check_placeholder(document, branch) for branch in BRANCH_REFS)
    manifest_matches = check_manifest()
    return 0 if placeholders_match and manifest_matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
