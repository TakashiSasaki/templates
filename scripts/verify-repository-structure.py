#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from pathlib import Path
from typing import TypeAlias

DOCUMENT_PATH = Path("docs/repository-structure.md")
REMOTE_BOOTSTRAP_REF = "refs/remotes/origin/bootstrap-agent-policy"
BRANCH_REFS = {
    "main": "HEAD",
    "bootstrap-agent-policy": REMOTE_BOOTSTRAP_REF,
}

TreeNode: TypeAlias = dict[str, "TreeNode | None"]


def tracked_paths(ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", ref],
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def build_tree(paths: list[str]) -> TreeNode:
    root: TreeNode = {}
    for path in paths:
        parts = path.split("/")
        current = root
        for part in parts[:-1]:
            child = current.setdefault(part, {})
            if child is None:
                raise ValueError(f"Path collision while rendering tree: {path}")
            current = child
        current[parts[-1]] = None
    return root


def sorted_items(node: TreeNode) -> list[tuple[str, TreeNode | None]]:
    return sorted(
        node.items(),
        key=lambda item: (item[1] is None, item[0].casefold(), item[0]),
    )


def render_node(node: TreeNode, prefix: str = "") -> list[str]:
    lines: list[str] = []
    items = sorted_items(node)
    for index, (name, child) in enumerate(items):
        last = index == len(items) - 1
        connector = "└── " if last else "├── "
        suffix = "/" if child is not None else ""
        lines.append(f"{prefix}{connector}{name}{suffix}")
        if child is not None:
            continuation = "    " if last else "│   "
            lines.extend(render_node(child, prefix + continuation))
    return lines


def render_tree(ref: str) -> str:
    lines = ["."]
    lines.extend(render_node(build_tree(tracked_paths(ref))))
    return "\n".join(lines)


def markers(branch: str) -> tuple[str, str]:
    return (
        f"<!-- BEGIN VERIFIED TREE: {branch} -->",
        f"<!-- END VERIFIED TREE: {branch} -->",
    )


def tree_block(branch: str, tree: str) -> str:
    start, end = markers(branch)
    return f"{start}\n```text\n{tree}\n```\n{end}"


def replace_block(document: str, branch: str, tree: str) -> str:
    start, end = markers(branch)
    start_index = document.find(start)
    end_index = document.find(end)
    if start_index < 0 or end_index < 0 or end_index < start_index:
        raise ValueError(f"Missing or invalid tree markers for {branch}")
    end_index += len(end)
    return document[:start_index] + tree_block(branch, tree) + document[end_index:]


def extract_tree(document: str, branch: str) -> str:
    start, end = markers(branch)
    start_index = document.find(start)
    end_index = document.find(end)
    if start_index < 0 or end_index < 0 or end_index < start_index:
        raise ValueError(f"Missing or invalid tree markers for {branch}")
    fenced = document[start_index + len(start) : end_index].strip()
    if not fenced.startswith("```text\n") or not fenced.endswith("\n```"):
        raise ValueError(f"Tree block for {branch} must be a fenced text block")
    return fenced[len("```text\n") : -len("\n```")]


def check(document: str, rendered: dict[str, str]) -> int:
    failures = 0
    for branch, expected in rendered.items():
        actual = extract_tree(document, branch)
        if actual == expected:
            print(f"Documented tree matches {branch}.")
            continue
        failures += 1
        print(f"Documented tree does not match {branch}.", file=sys.stderr)
        diff = difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            fromfile=f"documented/{branch}",
            tofile=f"git/{branch}",
            lineterm="",
        )
        print("\n".join(diff), file=sys.stderr)
    if failures:
        print(
            "Run `python scripts/verify-repository-structure.py --update` and review the result.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify documented repository trees against Git tree objects."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Fail when documentation is stale.")
    mode.add_argument("--update", action="store_true", help="Rewrite documented tree blocks.")
    args = parser.parse_args()

    document = DOCUMENT_PATH.read_text(encoding="utf-8")
    rendered = {branch: render_tree(ref) for branch, ref in BRANCH_REFS.items()}

    if args.update:
        updated = document
        for branch, tree in rendered.items():
            updated = replace_block(updated, branch, tree)
        DOCUMENT_PATH.write_text(updated, encoding="utf-8")
        print(f"Updated {DOCUMENT_PATH}.")
        return 0

    return check(document, rendered)


if __name__ == "__main__":
    raise SystemExit(main())
