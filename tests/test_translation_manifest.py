from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scripts.translation_manifest import (
    TranslationManifestError,
    load_translation_manifest,
)


def blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git object identity


class TranslationManifestTests(unittest.TestCase):
    def write_manifest(self, root: Path, payload: dict[str, object]) -> Path:
        path = root / "manifest.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def entry(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "canonical": "docs/index.md",
            "language": "ja",
            "translation": "translations/ja/docs/index.md",
            "canonical_blob_sha": "1" * 40,
            "surfaces": ["reader", "guided"],
        }
        value.update(overrides)
        return value

    def manifest(self, entries: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schema_version": 2,
            "canonical_language": "en",
            "translations": entries,
        }

    def prepare_bound_manifest(
        self,
        root: Path,
        *,
        recorded_sha: str | None = None,
    ) -> tuple[Path, bytes]:
        canonical = b"# Canonical\n"
        (root / "docs").mkdir(parents=True)
        (root / "translations" / "ja" / "docs").mkdir(parents=True)
        (root / "docs" / "index.md").write_bytes(canonical)
        (root / "translations" / "ja" / "docs" / "index.md").write_text(
            "# 日本語\n\n> **参考訳（非正本）:** test\n",
            encoding="utf-8",
        )
        path = root / "translations" / "manifest.json"
        path.write_text(
            json.dumps(
                self.manifest(
                    [
                        self.entry(
                            canonical_blob_sha=recorded_sha or blob_sha(canonical),
                        )
                    ]
                )
            ),
            encoding="utf-8",
        )
        return path, canonical

    def test_schema_v2_loads_typed_entries_and_surface_views(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(
                Path(directory),
                self.manifest(
                    [
                        self.entry(),
                        self.entry(
                            canonical="docs/reader.md",
                            translation="translations/ja/docs/reader.md",
                            canonical_blob_sha="2" * 40,
                            surfaces=["reader"],
                        ),
                    ]
                ),
            )
            manifest = load_translation_manifest(path, "test manifest")
            self.assertEqual(manifest.canonical_language, "en")
            self.assertEqual(len(manifest.entries), 2)
            self.assertEqual(manifest.entries[0].index, 0)
            self.assertEqual(manifest.entries[0].canonical, PurePosixPath("docs/index.md"))
            self.assertEqual(manifest.entries[0].freshness, "unchecked")
            self.assertEqual(len(manifest.for_surface("reader")), 2)
            self.assertEqual(len(manifest.for_surface("guided")), 1)

    def test_bound_manifest_classifies_current_and_stale_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, canonical = self.prepare_bound_manifest(root)
            manifest = load_translation_manifest(
                path,
                "test manifest",
                publication_root=root,
            )
            entry = manifest.entries[0]
            self.assertEqual(entry.current_blob_sha, blob_sha(canonical))
            self.assertEqual(entry.freshness, "current")
            self.assertTrue(entry.is_current)

            path.write_text(
                json.dumps(
                    self.manifest(
                        [self.entry(canonical_blob_sha="0" * 40)]
                    )
                ),
                encoding="utf-8",
            )
            stale = load_translation_manifest(
                path,
                "test manifest",
                publication_root=root,
            ).entries[0]
            self.assertEqual(stale.freshness, "stale")
            self.assertFalse(stale.is_current)
            self.assertEqual(stale.current_blob_sha, blob_sha(canonical))

    def test_bound_manifest_requires_declared_files_without_symlink_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _ = self.prepare_bound_manifest(root)
            (root / "translations" / "ja" / "docs" / "index.md").unlink()
            with self.assertRaisesRegex(
                TranslationManifestError,
                "must be an existing regular file",
            ):
                load_translation_manifest(
                    path,
                    "test manifest",
                    publication_root=root,
                )

    def test_schema_v1_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            payload = self.manifest([self.entry()])
            payload["schema_version"] = 1
            path = self.write_manifest(Path(directory), payload)
            with self.assertRaisesRegex(TranslationManifestError, "schema_version must be integer 2"):
                load_translation_manifest(path, "test manifest")

    def test_invalid_surface_declarations_fail_closed(self) -> None:
        for value in ([], ["search"], ["guided", "guided"]):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                path = self.write_manifest(
                    Path(directory),
                    self.manifest([self.entry(surfaces=value)]),
                )
                with self.assertRaises(TranslationManifestError):
                    load_translation_manifest(path, "test manifest")

    def test_translation_path_must_mirror_language_and_canonical_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(
                Path(directory),
                self.manifest(
                    [self.entry(translation="translations/ja/index.md")]
                ),
            )
            with self.assertRaisesRegex(TranslationManifestError, "must mirror canonical"):
                load_translation_manifest(path, "test manifest")

    def test_non_markdown_and_unsafe_paths_are_rejected(self) -> None:
        cases = (
            {"canonical": "docs/image.png", "translation": "translations/ja/docs/image.png"},
            {"canonical": "docs/guide", "translation": "translations/ja/docs/guide"},
            {"canonical": "../secret.md", "translation": "translations/ja/../secret.md"},
            {"canonical": "/absolute.md", "translation": "translations/ja/absolute.md"},
            {"canonical": "docs/foo:bar.md", "translation": "translations/ja/docs/foo:bar.md"},
            {"canonical": "docs\\index.md", "translation": "translations/ja/docs\\index.md"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as directory:
                path = self.write_manifest(
                    Path(directory),
                    self.manifest([self.entry(**overrides)]),
                )
                with self.assertRaises(TranslationManifestError):
                    load_translation_manifest(path, "test manifest")

    def test_invalid_language_tags_are_rejected(self) -> None:
        for language in ("JA", "en", "ja_JP", "123"):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                path = self.write_manifest(
                    Path(directory),
                    self.manifest(
                        [
                            self.entry(
                                language=language,
                                translation=f"translations/{language}/docs/index.md",
                            )
                        ]
                    ),
                )
                with self.assertRaises(TranslationManifestError):
                    load_translation_manifest(path, "test manifest")

    def test_duplicate_translation_pair_is_rejected_before_surface_filtering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(
                Path(directory),
                self.manifest(
                    [
                        self.entry(surfaces=["reader"]),
                        self.entry(surfaces=["guided"]),
                    ]
                ),
            )
            with self.assertRaisesRegex(TranslationManifestError, "duplicate translation pair"):
                load_translation_manifest(path, "test manifest")

    def test_duplicate_json_members_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(
                '{"schema_version":2,"schema_version":2,'
                '"canonical_language":"en","translations":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(TranslationManifestError, "duplicate member"):
                load_translation_manifest(path, "test manifest")

    def test_unsupported_surface_query_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_manifest(
                Path(directory),
                self.manifest([self.entry()]),
            )
            manifest = load_translation_manifest(path, "test manifest")
            with self.assertRaisesRegex(TranslationManifestError, "unsupported translation surface"):
                manifest.for_surface("search")


if __name__ == "__main__":
    unittest.main()
