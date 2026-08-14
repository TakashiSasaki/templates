from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_URL = "https://templates.moukaeritai.work/"


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_site_metadata = _load_module(
    "prepare_site_metadata",
    "scripts/prepare_site_metadata.py",
)
finalize_site_metadata = _load_module(
    "finalize_site_metadata",
    "scripts/finalize_site_metadata.py",
)
generate_repository_trees = _load_module(
    "generate_repository_trees_for_metadata",
    "scripts/generate_repository_trees.py",
)


class DeploymentSiteMetadataTests(unittest.TestCase):
    def test_prepare_site_metadata_uses_requested_canonical_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "zensical.toml"
            config.write_text(
                '[project]\nsite_url = "https://example.invalid/"\n',
                encoding="utf-8",
            )

            result = prepare_site_metadata.prepare(
                config,
                "2026-08-06 18:42:10 JST",
                CANONICAL_URL,
            )

            self.assertEqual(
                result,
                "Deploy (JST): 2026-08-06 18:42:10 JST",
            )
            self.assertIn(
                'site_url = "https://templates.moukaeritai.work/"',
                config.read_text(encoding="utf-8"),
            )

    def test_prepare_site_metadata_rejects_non_https_canonical_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "zensical.toml"
            config.write_text('[project]\nsite_url = "https://example.invalid/"\n')

            with self.assertRaises(prepare_site_metadata.SiteMetadataError):
                prepare_site_metadata.prepare(
                    config,
                    "",
                    "http://templates.moukaeritai.work/",
                )

    def test_finalize_site_metadata_rewrites_manifest_and_service_worker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "javascripts").mkdir()
            (root / "index.html").write_text(
                '<link rel="canonical" href="https://old.invalid/templates/">\n'
                '<link rel="manifest" href="/templates/app.webmanifest">\n'
                '<script src="/templates/javascripts/pwa.js"></script>\n',
                encoding="utf-8",
            )
            (root / "app.webmanifest").write_text(
                json.dumps(
                    {
                        "start_url": "/templates/",
                        "scope": "/templates/",
                        "icons": [
                            {"src": "/templates/icon.svg"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "service-worker.js").write_text(
                'const APP_SHELL = ["/templates/", "/templates/icon.svg"];\n'
                'const OFFLINE_FALLBACK = "/templates/";\n',
                encoding="utf-8",
            )
            (root / "javascripts" / "pwa.js").write_text(
                'navigator.serviceWorker.register("/templates/service-worker.js");\n',
                encoding="utf-8",
            )

            finalize_site_metadata.normalize_site_metadata(root, CANONICAL_URL)

            html = (root / "index.html").read_text(encoding="utf-8")
            manifest = json.loads((root / "app.webmanifest").read_text(encoding="utf-8"))
            service_worker = (root / "service-worker.js").read_text(encoding="utf-8")
            pwa = (root / "javascripts" / "pwa.js").read_text(encoding="utf-8")

            self.assertIn(
                '<link rel="canonical" href="https://templates.moukaeritai.work/">',
                html,
            )
            self.assertIn('<link rel="manifest" href="/app.webmanifest">', html)
            self.assertIn('<script src="/javascripts/pwa.js"></script>', html)
            self.assertEqual(manifest["start_url"], "/")
            self.assertEqual(manifest["scope"], "/")
            self.assertEqual(manifest["icons"][0]["src"], "/icon.svg")
            self.assertIn('"/"', service_worker)
            self.assertIn('"/icon.svg"', service_worker)
            self.assertNotIn("/templates/", service_worker)
            self.assertIn(
                'navigator.serviceWorker.register("/service-worker.js")',
                pwa,
            )
            self.assertNotIn("/templates/", pwa)

    def test_guided_metadata_normalization_keeps_root_manifest_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guided = root / "guided"
            guided.mkdir()
            (guided / "index.html").write_text(
                '<link rel="canonical" href="https://old.invalid/guided/">\n'
                '<link rel="manifest" href="/templates/app.webmanifest">\n'
                '<meta name="theme-color" content="#3f51b5">\n',
                encoding="utf-8",
            )

            finalize_site_metadata.normalize_canonical_links(guided, CANONICAL_URL)

            html = (guided / "index.html").read_text(encoding="utf-8")
            self.assertIn(
                '<link rel="canonical" href="https://templates.moukaeritai.work/">',
                html,
            )
            self.assertIn('<link rel="manifest" href="/app.webmanifest">', html)

    def test_repository_tree_url_uses_root_publication_base(self) -> None:
        base_path = generate_repository_trees.publication_base_path(CANONICAL_URL)
        self.assertEqual("/", base_path)
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
        self.assertIn("scripts/finalize_site_metadata.py", build_workflow)
        self.assertIn("scripts/finalize_translation_reader.py", build_workflow)
        self.assertEqual(
            4,
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

        self.assertIn(f'site_url = "{CANONICAL_URL}"', template)


if __name__ == "__main__":
    unittest.main()
