from __future__ import annotations

import cProfile
import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import site_build_profile


class SiteBuildProfileTests(unittest.TestCase):
    def test_inventory_attributes_repository_browser_costs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reader = root / "docs" / "index.html"
            browser = root / "files" / "site" / "content" / "a.html"
            reader.parent.mkdir(parents=True)
            browser.parent.mkdir(parents=True)
            reader.write_text(
                '<html><head><meta name="templates-site-revision" content="' + 'a' * 40 + '"></head>'
                '<body><main><a href="/target/">target</a></main></body></html>',
                encoding="utf-8",
            )
            browser.write_text(
                '<html><body><main><div id="L1"><a class="line-number" href="#L1">1</a></div>'
                '<div id="L2"><a class="line-number" href="#L2">2</a></div></main></body></html>',
                encoding="utf-8",
            )

            inventory = site_build_profile.collect_inventory(root)

            self.assertEqual(inventory["html_pages"], 2)
            self.assertEqual(inventory["effective_links"], 3)
            self.assertEqual(inventory["fragment_links"], 2)
            self.assertEqual(inventory["line_anchors"], 2)
            self.assertEqual(inventory["buckets"]["files"]["html_pages"], 1)
            self.assertEqual(inventory["buckets"]["files"]["line_anchors"], 2)
            self.assertEqual(inventory["buckets"]["reader"]["freshness_meta_pages"], 1)

    def test_prepare_freshness_input_preserves_sandbox_previews(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "prepared"
            normal = source / "index.html"
            preview = source / "repository-trees" / "previews" / "composition" / "x.html"
            normal.parent.mkdir(parents=True)
            preview.parent.mkdir(parents=True)
            meta = '<meta name="templates-site-revision" content="' + 'b' * 40 + '">\n'
            normal.write_text(f"<html><head>{meta}</head></html>", encoding="utf-8")
            preview.write_text(f"<html><head>{meta}</head></html>", encoding="utf-8")
            (source / "site-version.json").write_text("{}\n", encoding="utf-8")
            (source / "build-provenance.json").write_text("{}\n", encoding="utf-8")

            record = site_build_profile.prepare_freshness_input(source, destination)

            self.assertEqual(record["html_files_touched"], 1)
            self.assertEqual(record["meta_tags_removed"], 1)
            self.assertEqual(record["metadata_files_removed"], 2)
            self.assertNotIn("templates-site-revision", (destination / "index.html").read_text())
            self.assertIn(
                "templates-site-revision",
                (destination / "repository-trees" / "previews" / "composition" / "x.html").read_text(),
            )

    def test_empty_translation_map_is_valid_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "translation.json"
            site_build_profile.write_empty_translation_map(output)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                payload,
                {"schema_version": 1, "canonical_language": "en", "translations": []},
            )

    def test_profile_summary_records_cpu_totals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            profile_path = Path(temporary_directory) / "sample.prof"
            profiler = cProfile.Profile()
            profiler.runcall(sum, range(10))
            profiler.dump_stats(profile_path)

            record = site_build_profile.summarize_profile(profile_path, "sample", 5)

            self.assertEqual(record["label"], "sample")
            self.assertGreater(record["total_calls"], 0)
            self.assertGreaterEqual(record["profiled_cpu_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
