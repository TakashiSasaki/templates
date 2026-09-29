"""Canonical edits do not require synchronized Japanese section links."""
from pathlib import Path
import tempfile
import unittest

from site_renderer.reference_links import repair_reference_fragments


class ReferenceLinkTests(unittest.TestCase):
    def test_removed_sections_fall_back_without_changing_sources_or_valid_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            docs = Path(temporary)
            english = docs / 'use/provider/guide.md'
            english.parent.mkdir(parents=True)
            canonical = '# Guide\n\n## New section\n\n[broken canonical](#gone)\n'
            english.write_text(canonical)
            japanese = docs / 'ja/use/provider/guide.md'
            japanese.parent.mkdir(parents=True)
            japanese.write_text(
                '# 参考訳\n\n## そのまま {#explicit}\n\n'
                '[old](/use/provider/guide/#removed)\n'
                '[valid](/use/provider/guide/#new-section)\n'
                '[explicit](#explicit)\n[missing](#gone)\n'
                '[relative][ref]\n[ref]: ../../../use/provider/guide.md?mode=full#removed\n'
                '[external](https://example.org/#removed)\n'
                '`[example](/use/provider/guide/#removed)`\n'
                '```md\n[example](/use/provider/guide/#removed)\n```\n')
            records = {'translations': [{'translation_destination': 'ja/use/provider/guide.md'}]}
            self.assertEqual(repair_reference_fragments(docs, records), 3)
            result = japanese.read_text()
            self.assertIn('[old](/use/provider/guide/)', result)
            self.assertIn('[valid](/use/provider/guide/#new-section)', result)
            self.assertIn('[explicit](#explicit)', result)
            self.assertIn('[missing](/ja/use/provider/guide/)', result)
            self.assertIn('[ref]: ../../../use/provider/guide.md?mode=full\n', result)
            self.assertIn('[external](https://example.org/#removed)', result)
            self.assertIn('`[example](/use/provider/guide/#removed)`', result)
            self.assertIn('```md\n[example](/use/provider/guide/#removed)\n```', result)
            self.assertEqual(english.read_text(), canonical)
            self.assertEqual(repair_reference_fragments(docs, records), 0)
