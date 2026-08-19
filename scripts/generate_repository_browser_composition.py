#!/usr/bin/env python3
"""Run the static repository browser with the composition-era branch set."""

from __future__ import annotations

import html

try:
    from scripts import generate_repository_browser as base
except ModuleNotFoundError:
    import generate_repository_browser as base

BRANCH_ORDER = ("site", "composition", "policy")


def write_root_index(browser_root):
    links = "".join(
        f'<li><a href="{branch}/">{html.escape(branch)}</a></li>'
        for branch in BRANCH_ORDER
    )
    (browser_root / "index.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Repository file browser</title><style>:root{{color-scheme:light dark;font-family:system-ui,sans-serif}}body{{max-width:48rem;margin:4rem auto;padding:0 1rem}}a{{color:LinkText}}code{{font-family:ui-monospace,monospace}}</style></head>
<body><h1>Repository file browser</h1><p>Browse immutable build-time snapshots of the Site, Composition, and Policy authorities.</p><ul>{links}</ul></body></html>\n""",
        encoding="utf-8",
    )


def main() -> int:
    base.BRANCH_ORDER = BRANCH_ORDER
    base.write_root_index = write_root_index
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
