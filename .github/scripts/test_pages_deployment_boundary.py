#!/usr/bin/env python3
"""Ensure the skill branch has no GitHub Pages deployment route."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
COMPATIBILITY = WORKFLOWS / "pages.yml"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"


def abort(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if not COMPATIBILITY.is_file():
        abort("build-only documentation compatibility workflow is missing")
    if not CONTRIBUTING.is_file():
        abort("contributor guidance is missing")

    workflow_files = [
        path
        for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    ]
    forbidden = {
        "Pages deployment action": "actions/deploy-pages@",
        "Pages configuration action": "actions/configure-pages@",
        "Pages artifact action": "actions/upload-pages-artifact@",
        "Pages write permission": "pages: write",
        "Pages environment": "name: github-pages",
        "deployment-enabling input": "deploy: true",
    }
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        for description, token in forbidden.items():
            if token in text:
                abort(f"{description} remains in {path.relative_to(ROOT)}")

    compatibility = COMPATIBILITY.read_text(encoding="utf-8")
    required = [
        "uses: TakashiSasaki/templates/.github/workflows/build-pages.yml@site",
        "site_ref: site",
        "source_ref: ${{ github.event_name == 'pull_request' && github.sha || 'skill' }}",
        "contents: read",
        "- README.md",
        "- docs/**",
        "- template/**",
    ]
    for token in required:
        if token not in compatibility:
            abort(f"compatibility workflow is missing {token!r}")

    for removed_filter in ("CLI_INTERFACE.md", "MCP_INTERFACE.md", "assets/**"):
        if any(
            line.strip() == f"- {removed_filter}"
            for line in compatibility.splitlines()
        ):
            abort(
                "compatibility workflow retains removed root path filter "
                f"{removed_filter!r}"
            )

    trigger_block = compatibility.split("\npermissions:\n", 1)[0]
    if "\n  push:\n" in trigger_block:
        abort("skill push still triggers documentation workflow")
    if "\n      - skill\n" not in trigger_block:
        abort("compatibility workflow does not target skill pull requests")
    if "\n      - main\n" in trigger_block:
        abort("compatibility workflow still targets the removed main branch")
    if "\n  schedule:\n" in trigger_block:
        abort("skill workflow incorrectly claims a scheduled run")
    if "\n  workflow_dispatch:\n" not in trigger_block:
        abort("skill workflow lacks manual drift-check dispatch")
    if re.search(r"^\s+deploy:", compatibility, re.MULTILINE):
        abort("compatibility workflow still passes a deploy input")
    if "id-token: write" in compatibility:
        abort("compatibility workflow retains OIDC write permission")

    contributing = CONTRIBUTING.read_text(encoding="utf-8")
    if "Publish template documentation" in contributing:
        abort("contributor guidance still names the removed skill publication workflow")
    if "No workflow on `skill` deploys GitHub Pages" not in contributing:
        abort("contributor guidance does not state the skill deployment boundary")
    if (
        "this `skill`-branch workflow does not claim a weekly scheduled run"
        not in contributing
    ):
        abort("contributor guidance incorrectly claims a weekly skill schedule")

    print("skill workflows and contributor guidance contain no GitHub Pages deployment route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
