from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from scripts import finalize_site_metadata, generate_repository_trees, prepare_site_metadata

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_URL = "https://templates.moukaeritai.work/"


class DeploymentNoticeTests(unittest.TestCase):
    def test_empty_timestamp_marks_non_deploying_build(self) -> None:
        self.assertEqual(
            "Preview build (not deployed)",
            prepare_site_metadata.deployment_notice(""),
        )

    def test_deployment_timestamp_becomes_footer_notice(self) -> None:
        self.assertEqual(
            "Last deployed: 2026-08-09 14:23:45 JST",
            prepare_site_metadata.deployment_notice("2026-08-09 14:23:45 JST"),
        )

    def test_invalid_timestamp_is_rejected(self) -> None:
        for value in (
            "2026-08-09 14:23 JST",
            "2026-08-09T14:23:45+09:00",
            "2026-08-09 14:23:45 UTC",
            "2026-02-30 14:23:45 JST",
        ):
            with self.subTest(value=value):
                with self.assertRaises(prepare_site_metadata.MetadataError):
                    prepare_site_metadata.deployment_notice(value)

    def test_prepared_config_contains_footer_notice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_file = Path(temporary_directory) / "zensical.toml"
            config_file.write_text(
                "[project]\n"
                'site_name = "templates"\n'
                "[extra]\n"
                'deployment_notice = "old"\n',
                encoding="utf-8",
            )
            notice = prepare_site_metadata.prepare_config(
                config_file,
                "2026-08-09 14:23:45 JST",
                CANONICAL_URL,
            )
            rendered = config_file.read_text(encoding="utf-8")

        self.assertEqual("Last deployed: 2026-08-09 14:23:45 JST", notice)
        self.assertIn('site_url = "https://templates.moukaeritai.work/"', rendered)
        self.assertIn(
            'deployment_notice = "Last deployed: 2026-08-09 14:23:45 JST"',
            rendered,
        )


class CanonicalMetadataTests(unittest.TestCase):
    def test_missing_canonical_link_is_inserted(self) -> None:
        source = "<html><head><title>Test</title></head><body></body></html>"
        rendered = finalize_site_metadata.rewrite_canonical_link(
            source,
            CANONICAL_URL,
            Path("index.html"),
        )
        self.assertIn(
            '<link rel="canonical" href="https://templates.moukaeritai.work/">',
            rendered,
        )

    def test_duplicate_canonical_links_are_rejected(self) -> None:
        source = (
            '<html><head><link rel="canonical" href="https://example.invalid/a">'
            '<link rel="canonical" href="https://example.invalid/b"></head></html>'
        )
        with self.assertRaises(finalize_site_metadata.SiteMetadataError):
            finalize_site_metadata.rewrite_canonical_link(
                source,
                CANONICAL_URL,
                Path("index.html"),
            )

    def test_every_generated_page_uses_the_public_site_canonical_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested = root / "nested"
            nested.mkdir()
            (root / "index.html").write_text(
                '<html><head><link rel="canonical" href="https://old.invalid/"></head></html>',
                encoding="utf-8",
            )
            (nested / "index.html").write_text(
                "<html><head></head><body></body></html>",
                encoding="utf-8",
            )
            updated = finalize_site_metadata.finalize(root, CANONICAL_URL)
            rendered = [
                path.read_text(encoding="utf-8")
                for path in (root / "index.html", nested / "index.html")
            ]

        self.assertEqual(2, updated)
        self.assertTrue(
            all(
                '<link rel="canonical" href="https://templates.moukaeritai.work/">'
                in source
                for source in rendered
            )
        )


class PublicUrlContractTests(unittest.TestCase):
    def test_custom_domain_is_an_https_root_site(self) -> None:
        parsed = urlsplit(CANONICAL_URL)
        self.assertEqual("https", parsed.scheme)
        self.assertEqual("templates.moukaeritai.work", parsed.netloc)
        self.assertEqual("/", parsed.path)
        self.assertFalse(parsed.query)
        self.assertFalse(parsed.fragment)

    def test_production_configuration_generates_root_based_public_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_file = Path(temporary_directory) / "zensical.toml"
            config_file.write_text(
                "[project]\n" f'site_url = "{CANONICAL_URL}"\n',
                encoding="utf-8",
            )
            base_path = generate_repository_trees.configured_base_path(config_file)

        self.assertEqual("/", base_path)
        self.assertEqual(
            "/skill/",
            generate_repository_trees.published_url(base_path, "skill/index.md"),
        )
        self.assertEqual(
            "/repository-trees/skill/",
            generate_repository_trees.published_url(
                base_path,
                "repository-trees/skill.md",
            ),
        )


class DeploymentWorkflowWiringTests(unittest.TestCase):
    def test_deployment_workflow_supplies_timestamp_to_build_before_deploying(self) -> None:
        build_workflow = (ROOT / ".github/workflows/build-pages.yml").read_text(
            encoding="utf-8"
        )
        deploy_workflow = (ROOT / ".github/workflows/deploy-pages.yml").read_text(
            encoding="utf-8"
        )
        template = (ROOT / "zensical.template.toml").read_text(encoding="utf-8")

        self.assertIn(f"PUBLIC_SITE_URL: {CANONICAL_URL}", build_workflow)
        self.assertIn("deployment_timestamp:", build_workflow)
        self.assertIn("scripts/prepare_site_metadata.py", build_workflow)
        self.assertIn(
            '--deployment-timestamp "${{ inputs.deployment_timestamp }}"',
            build_workflow,
        )
        for script in (
            "scripts/finalize_site_metadata.py",
            "scripts/finalize_translation_reader.py",
            "scripts/finalize_guided_locales.py",
        ):
            with self.subTest(script=script):
                self.assertIn(script, build_workflow)
        # prepare_site_metadata, the generic site pass, the canonical guided pass,
        # the reader translation finalizer, and the localized guided finalizer each
        # receive the same production canonical URL.
        self.assertEqual(
            5,
            build_workflow.count('--canonical-url "${PUBLIC_SITE_URL}"'),
        )
        self.assertIn("Verify generated public URL boundary", build_workflow)
        self.assertIn("https://takashisasaki.github.io/templates/", build_workflow)

        self.assertIn(f"PUBLIC_SITE_URL: {CANONICAL_URL}", deploy_workflow)
        self.assertIn("uses: ./.github/workflows/build-pages.yml", deploy_workflow)
        self.assertIn("TZ=Asia/Tokyo", deploy_workflow)
        self.assertIn("deployment_timestamp:", deploy_workflow)
        self.assertIn(
            "${{ needs.deployment_metadata.outputs.deployment_timestamp }}",
            deploy_workflow,
        )
        self.assertIn("actions/configure-pages@v6", deploy_workflow)
        self.assertIn("id: pages", deploy_workflow)
        self.assertIn("${{ steps.pages.outputs.base_url }}", deploy_workflow)
        self.assertIn("${{ steps.pages.outputs.host }}", deploy_workflow)
        self.assertIn("${{ steps.pages.outputs.base_path }}", deploy_workflow)
        self.assertIn('expected_base_url="${PUBLIC_SITE_URL%/}"', deploy_workflow)
        self.assertIn('expected_host="${expected_base_url#https://}"', deploy_workflow)
        self.assertIn('test "$ACTUAL_BASE_URL" = "$expected_base_url"', deploy_workflow)
        self.assertIn('test "$ACTUAL_HOST" = "$expected_host"', deploy_workflow)
        self.assertIn('test -z "$ACTUAL_BASE_PATH"', deploy_workflow)
        self.assertIn("actions/deploy-pages@v5", deploy_workflow)
        self.assertIn(f'site_url = "{CANONICAL_URL}"', template)

        metadata = deploy_workflow.index("  deployment_metadata:")
        build = deploy_workflow.index("  build:")
        deploy = deploy_workflow.index("  deploy:")
        configure = deploy_workflow.index("- name: Configure GitHub Pages")
        validate = deploy_workflow.index("- name: Validate Pages URL contract")
        publish = deploy_workflow.index("- name: Deploy to GitHub Pages")
        self.assertLess(metadata, build)
        self.assertLess(build, deploy)
        self.assertLess(configure, validate)
        self.assertLess(validate, publish)


if __name__ == "__main__":
    unittest.main()
