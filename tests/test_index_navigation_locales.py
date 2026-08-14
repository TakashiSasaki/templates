from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_index_navigation_locales import (
    IndexNavigationLocaleError,
    generate_locale_overlays,
)

SHA = "a" * 40


def graph() -> dict[str, object]:
    providers = []
    for name in ("skill", "policy", "webapp"):
        if name == "policy":
            indexes = [
                {
                    "path": "docs/index.md",
                    "title": "Policy navigation",
                    "sections": [{"title": "Orientation", "level": 2}],
                    "depth": 0,
                    "object_id": SHA,
                }
            ]
            edges = [
                {
                    "source": "docs/index.md",
                    "section": "Orientation",
                    "label": "Overview",
                    "description": "Canonical description.",
                    "line": 5,
                    "raw_target": "overview.md",
                    "kind": "file",
                    "target": "docs/overview.md",
                    "fragment": None,
                }
            ]
        else:
            indexes = []
            edges = []
        providers.append(
            {
                "name": name,
                "revision": (name[0] * 40),
                "root_index": "docs/index.md",
                "indexes": indexes,
                "edges": edges,
                "diagnostics": {},
            }
        )
    return {
        "schema_version": 1,
        "repository": "TakashiSasaki/templates",
        "providers": providers,
    }


def prepare_roots(base: Path, *, target: str = "overview.md", blob_sha: str = SHA) -> dict[str, Path]:
    roots = {name: base / name for name in ("skill", "policy", "webapp")}
    for root in roots.values():
        root.mkdir()
    policy = roots["policy"]
    (policy / "translations" / "ja" / "docs").mkdir(parents=True)
    (policy / "translations" / "ja" / "docs" / "index.md").write_text(
        "# ポリシーナビゲーション\n\n"
        "> **参考訳（非正本）:** test\n\n"
        "## オリエンテーション\n\n"
        f"* [概要]({target}) - 正本の説明の日本語訳です。\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 2,
        "canonical_language": "en",
        "translations": [
            {
                "canonical": "docs/index.md",
                "language": "ja",
                "translation": "translations/ja/docs/index.md",
                "canonical_blob_sha": blob_sha,
                "surfaces": ["guided"],
            }
        ],
    }
    (policy / "translations" / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return roots


class IndexNavigationLocaleTests(unittest.TestCase):
    def test_overlay_localizes_prose_without_replacing_graph_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = prepare_roots(Path(directory))
            payload = generate_locale_overlays(graph(), roots)
            locale = payload["locales"][0]
            self.assertEqual(locale["language"], "ja")
            provider = locale["providers"][0]
            self.assertEqual(provider["name"], "policy")
            overlay = provider["indexes"][0]
            self.assertEqual(overlay["path"], "docs/index.md")
            self.assertEqual(overlay["title"], "ポリシーナビゲーション")
            self.assertEqual(overlay["sections"][0]["title"], "オリエンテーション")
            self.assertEqual(overlay["links"][0]["label"], "概要")
            self.assertNotIn("target", overlay["links"][0])

    def test_translation_target_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = prepare_roots(Path(directory), target="different.md")
            with self.assertRaisesRegex(IndexNavigationLocaleError, "target differs"):
                generate_locale_overlays(graph(), roots)

    def test_stale_blob_binding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = prepare_roots(Path(directory), blob_sha="b" * 40)
            with self.assertRaisesRegex(IndexNavigationLocaleError, "stale guided translation"):
                generate_locale_overlays(graph(), roots)

    def test_guided_canonical_must_be_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = prepare_roots(Path(directory))
            manifest_path = roots["policy"] / "translations" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = manifest["translations"][0]
            entry["canonical"] = "docs/hidden/index.md"
            entry["translation"] = "translations/ja/docs/hidden/index.md"
            hidden = roots["policy"] / "translations" / "ja" / "docs" / "hidden"
            hidden.mkdir()
            (hidden / "index.md").write_text(
                "# 非表示\n\n> **参考訳（非正本）:** test\n", encoding="utf-8"
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(IndexNavigationLocaleError, "not reachable"):
                generate_locale_overlays(graph(), roots)


if __name__ == "__main__":
    unittest.main()
