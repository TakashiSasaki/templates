#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "c0c8b9430437759f99604ab005e6c04b24218c23"


def original(path: str) -> str:
    return subprocess.run(
        ["git", "show", f"{BASE}:{path}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected one anchor, found {text.count(old)}")
    return text.replace(old, new, 1)


def main() -> None:
    manifest_anchor = '        {"title": "Publication boundary", "publication": "composition", "document": "publication-boundary", "destination": "composition/docs/publication-catalog.md"},\n'
    manifest_insert = (
        manifest_anchor
        + '        {"title": "Composition maintainer overview", "publication": "composition", "document": "provider-maintenance", "destination": "composition/authorities/provider-maintenance.md"},\n'
        + '        {"title": "Installer release", "publication": "composition", "document": "installer-release", "destination": "composition/authorities/installer-release.md"},\n'
    )
    manifest = replace_once(original("site-manifest.json"), manifest_anchor, manifest_insert, "site manifest")
    (ROOT / "site-manifest.json").write_text(manifest, encoding="utf-8")

    locale_anchor = '        {"id": "publication-boundary", "canonical": "Publication boundary", "localized": "公開境界"},\n'
    locale_insert = (
        locale_anchor
        + '        {"id": "composition-provider-maintenance", "canonical": "Composition maintainer overview", "localized": "Composition メンテナー概要"},\n'
        + '        {"id": "composition-installer-release", "canonical": "Installer release", "localized": "インストーラーリリース"},\n'
    )
    locales = replace_once(original("reader-navigation-locales.json"), locale_anchor, locale_insert, "reader locale")
    (ROOT / "reader-navigation-locales.json").write_text(locales, encoding="utf-8")


if __name__ == "__main__":
    main()
