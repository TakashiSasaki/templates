from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import scripts.validate_site_links as validate_site_links


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_site_links.py"


class GeneratedSiteLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.site_root = self.root / "site"
        self.site_root.mkdir()
        self.config_file = self.root / "zensical.toml"
        self.config_file.write_text(
            '[project]\nsite_url = "https://example.test/docs/"\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        path = self.site_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--site-root",
                str(self.site_root),
                "--config-file",
                str(self.config_file),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_accepts_pages_fragments_assets_and_external_links(self) -> None:
        self.write(
            "index.html",
            """<!doctype html>
<html><body id="home">
<a href="guide/#details">Guide</a>
<a href="guide/#caf%C3%A9">Unicode fragment</a>
<a href="asset.txt">Asset</a>
<a href="#home">Home fragment</a>
<a href="https://other.example/path">External</a>
<a href="https://example.test/outside/">Same-origin outside project</a>
<a href="mailto:docs@example.test">Mail</a>
</body></html>
""",
        )
        self.write(
            "guide/index.html",
            """<!doctype html>
<html><body><h2 id="details">Details</h2><h2 id="café">Café</h2>
<a href="../">Back</a>
</body></html>
""",
        )
        self.write("asset.txt", "asset\n")

        result = self.run_validator()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 5 local links across 2 generated HTML pages", result.stdout)

    def test_accepts_external_special_scheme_without_slashes(self) -> None:
        self.write("index.html", '<a href="http:external.test/path">External</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 0 local links across 1 generated HTML pages", result.stdout)

    def test_allows_external_hostname_with_underscore(self) -> None:
        self.write("index.html", '<a href="https://docs_test.example/path">External</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 0 local links across 1 generated HTML pages", result.stdout)

    def test_rejects_same_scheme_shorthand_when_local_target_is_missing(self) -> None:
        self.write("index.html", '<a href="https:absent/">Absent</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_accepts_same_scheme_shorthand_path_containing_colon(self) -> None:
        self.write("index.html", '<a href="https:example.test:443/x">Colon path</a>')
        self.write("example.test:443/x/index.html", "<p>Colon path</p>")
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 1 local links across 2 generated HTML pages", result.stdout)

    def test_accepts_triple_slash_same_origin_network_reference(self) -> None:
        self.write("index.html", '<a href="///example.test/docs/guide/">Guide</a>')
        self.write("guide/index.html", "<p>Guide</p>")
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 1 local links across 2 generated HTML pages", result.stdout)

    def test_rejects_network_reference_without_authority(self) -> None:
        self.write("index.html", '<a href="///">Malformed</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("must contain a valid HTTP or HTTPS origin", result.stderr)

    def test_accepts_anchor_followed_by_text_fragment_directive(self) -> None:
        self.write(
            "index.html",
            '<h2 id="details">Details</h2><a href="#details:~:text=example">Text</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 1 local links across 1 generated HTML pages", result.stdout)

    def test_accepts_percent_encoded_parent_segment_with_fragment(self) -> None:
        self.write("index.html", '<h1 id="home">Home</h1>')
        self.write("guide/index.html", '<a href="%2e%2e/#home">Encoded parent</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 1 local links across 2 generated HTML pages", result.stdout)

    def test_rejects_mixed_encoded_and_literal_parent_segments_that_escape(self) -> None:
        self.write("index.html", "<p>Home</p>")
        self.write("guide/index.html", '<a href="%2e%2e/../">Escapes</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("resolves outside project.site_url", result.stderr)

    def test_rejects_encoded_separator_that_only_looks_like_parent_segment(self) -> None:
        self.write("present/index.html", "<p>Present</p>")
        self.write("guide/index.html", '<a href="%2e%2e%2fpresent/">Encoded separator</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)
        self.assertIn("'%2e%2e%2fpresent/'", result.stderr)

    def test_preserves_encoded_separator_in_configured_base_path(self) -> None:
        self.config_file.write_text(
            '[project]\nsite_url = "https://example.test/do%2Fcs/"\n',
            encoding="utf-8",
        )
        self.write(
            "index.html",
            '<a href="https://example.test/do%2Fcs/absent/">Absent</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_rejects_repeated_slash_when_single_slash_page_exists(self) -> None:
        self.write("guide/present/index.html", "<p>Present</p>")
        self.write(
            "index.html",
            '<a href="https://example.test/docs/guide//present/">Repeated slash</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)
        self.assertIn("https://example.test/docs/guide//present/", result.stderr)

    def test_rejects_relative_repeated_slash_when_single_slash_page_exists(self) -> None:
        self.write("present/page/index.html", "<p>Present</p>")
        self.write("guide/index.html", '<a href="../present//page/">Repeated slash</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)
        self.assertIn("../present//page/", result.stderr)

    def test_uses_main_content_links_when_generated_chrome_is_present(self) -> None:
        self.write(
            "index.html",
            """<!doctype html>
<html><body>
<a href="#__skip">Generated skip link without a target</a>
<main><h1 id="content">Content</h1><a href="#content">Content link</a></main>
</body></html>
""",
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 1 local links across 1 generated HTML pages", result.stdout)

    def test_preserves_first_duplicate_href_attribute(self) -> None:
        self.write("index.html", '<a href="missing/" href="present/">Duplicate</a>')
        self.write("present/index.html", "<p>Present</p>")
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'missing/' has no generated target", result.stderr)

    def test_preserves_first_duplicate_id_attribute(self) -> None:
        self.write(
            "index.html",
            '<h2 id="present" id="missing">Heading</h2><a href="#missing">Missing</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("references missing fragment 'missing'", result.stderr)

    def test_rejects_missing_generated_target(self) -> None:
        self.write("index.html", '<a href="missing/">Missing</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)
        self.assertIn("'missing/'", result.stderr)

    def test_rejects_trailing_slash_on_generated_file(self) -> None:
        self.write("index.html", '<a href="asset.txt/">Asset directory</a>')
        self.write("asset.txt", "asset\n")
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)
        self.assertIn("asset.txt/", result.stderr)

    def test_rejects_missing_fragment(self) -> None:
        self.write("index.html", '<a href="guide/#missing">Missing</a>')
        self.write("guide/index.html", '<h2 id="present">Present</h2>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("references missing fragment 'missing'", result.stderr)
        self.assertIn("guide/index.html", result.stderr)

    def test_rejects_explicit_default_port_target_when_missing(self) -> None:
        self.write("index.html", '<a href="https://example.test:443/docs/absent/">Absent</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_rejects_same_origin_absolute_link_with_backslashes_when_missing(self) -> None:
        self.write("index.html", '<a href="https://example.test\\docs\\absent/">Absent</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)
        self.assertIn("https://example.test\\\\docs\\\\absent/", result.stderr)

    def test_rejects_percent_encoded_same_origin_hostname_when_missing(self) -> None:
        self.write("index.html", '<a href="https://%65xample.test/docs/absent/">Absent</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_rejects_idna_equivalent_same_origin_hostname_when_missing(self) -> None:
        self.config_file.write_text(
            '[project]\nsite_url = "https://takashisasaki.github.io/templates/"\n',
            encoding="utf-8",
        )
        self.write(
            "index.html",
            '<a href="https://ｔａｋａｓｈｉｓａｓａｋｉ.github.io/templates/absent/">Absent</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_rejects_numeric_ipv4_same_origin_hostname_when_missing(self) -> None:
        self.config_file.write_text(
            '[project]\nsite_url = "https://127.0.0.1/docs/"\n',
            encoding="utf-8",
        )
        self.write("index.html", '<a href="https://127.1/docs/absent/">Absent</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_preserves_non_ascii_whitespace_in_href(self) -> None:
        self.write("index.html", '<a href="\u00a0https://other.example/path">NBSP path</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_removes_embedded_ascii_whitespace_before_url_parsing(self) -> None:
        self.write(
            "index.html",
            '<a href="https://exa\nmple.test/docs/absent/">Absent</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_trims_complete_c0_control_range_at_url_boundaries(self) -> None:
        self.write("index.html", '<a href="\x0bhttps://other.example/path">External</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 0 local links across 1 generated HTML pages", result.stdout)

    def test_rejects_expanded_ipv6_same_origin_hostname_when_missing(self) -> None:
        self.config_file.write_text(
            '[project]\nsite_url = "https://[::1]/docs/"\n',
            encoding="utf-8",
        )
        self.write(
            "index.html",
            '<a href="https://[0:0:0:0:0:0:0:1]/docs/absent/">Absent</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_uses_nontransitional_idna_for_same_origin_hostname(self) -> None:
        self.config_file.write_text(
            '[project]\nsite_url = "https://xn--fa-hia.de/docs/"\n',
            encoding="utf-8",
        )
        self.write(
            "index.html",
            '<a href="https://faß.de/docs/absent/">Absent</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_applies_uts46_ignored_codepoint_mapping(self) -> None:
        self.write(
            "index.html",
            '<a href="https://ex\u00adample.test/docs/absent/">Absent</a>',
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("has no generated target", result.stderr)

    def test_treats_explicit_zero_port_as_a_distinct_origin(self) -> None:
        self.write("index.html", '<a href="https://example.test:0/docs/absent/">Different port</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validated 0 local links across 1 generated HTML pages", result.stdout)

    def test_rejects_relative_link_that_escapes_site_path(self) -> None:
        self.write("index.html", "<p>Home</p>")
        self.write("guide/index.html", '<a href="../../outside/">Outside</a>')
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("resolves outside project.site_url", result.stderr)

    def test_rejects_fragment_on_non_html_asset(self) -> None:
        self.write("index.html", '<a href="asset.txt#part">Asset fragment</a>')
        self.write("asset.txt", "asset\n")
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("uses a fragment on a non-HTML target", result.stderr)

    def test_rejects_missing_site_url(self) -> None:
        self.write("index.html", "<p>Home</p>")
        self.config_file.write_text("[project]\n", encoding="utf-8")
        result = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertIn("must define a non-empty project.site_url", result.stderr)


class RepositoryBrowserLineAnchorBoundaryTests(unittest.TestCase):
    def test_validator_excludes_only_generator_owned_line_fragments(self) -> None:
        self.assertTrue(
            validate_site_links.REPOSITORY_LINE_FRAGMENT_RE.fullmatch("#L12")
        )
        self.assertFalse(
            validate_site_links.REPOSITORY_LINE_FRAGMENT_RE.fullmatch("#L0")
        )
        self.assertFalse(
            validate_site_links.REPOSITORY_LINE_FRAGMENT_RE.fullmatch("#Lx")
        )


if __name__ == "__main__":
    unittest.main()
