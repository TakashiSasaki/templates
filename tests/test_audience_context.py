from __future__ import annotations

import io
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest.mock import patch

from scripts.assemble_publications import Manifest, load_manifest
from scripts.audience_context import (
    AudienceContextError,
    AudienceContextResolver,
    create_resolver,
    main,
)

ROOT = Path(__file__).resolve().parents[1]


class AudienceContextResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_manifest_data = {
            "schema_version": 3,
            "audiences": ["use", "maintain"],
            "home": {
                "publication": "site",
                "document": "home",
            },
            "documents": [
                {
                    "publication": "site",
                    "document": "home",
                    "title": "Portal Home",
                    "destination": "index.md",
                    "primary_audience": "use",
                    "additional_audiences": ["maintain"],
                },
                {
                    "publication": "composition",
                    "document": "user-guide",
                    "title": "User Guide",
                    "destination": "use/guide.md",
                    "primary_audience": "use",
                    "additional_audiences": [],
                },
                {
                    "publication": "policy",
                    "document": "maintainer-guide",
                    "title": "Maintainer Guide",
                    "destination": "maintain/guide.md",
                    "primary_audience": "maintain",
                    "additional_audiences": [],
                },
                {
                    "publication": "composition",
                    "document": "shared-spec",
                    "title": "Shared Specification",
                    "destination": "specs/shared.md",
                    "primary_audience": "use",
                    "additional_audiences": ["maintain"],
                },
            ],
            "navigation": {
                "use": [
                    {
                        "title": "Portal",
                        "publication": "site",
                        "document": "home",
                        "destination": "index.md",
                    },
                    {
                        "title": "User Guide",
                        "publication": "composition",
                        "document": "user-guide",
                        "destination": "use/guide.md",
                    },
                    {
                        "title": "Shared Specification",
                        "publication": "composition",
                        "document": "shared-spec",
                        "destination": "specs/shared.md",
                    },
                ],
                "maintain": [
                    {
                        "title": "Portal",
                        "publication": "site",
                        "document": "home",
                        "destination": "index.md",
                    },
                    {
                        "title": "Maintainer Guide",
                        "publication": "policy",
                        "document": "maintainer-guide",
                        "destination": "maintain/guide.md",
                    },
                    {
                        "title": "Shared Specification",
                        "publication": "composition",
                        "document": "shared-spec",
                        "destination": "specs/shared.md",
                    },
                ],
            },
        }
        self.temp_dir = tempfile.TemporaryDirectory()
        manifest_path = Path(self.temp_dir.name) / "site-manifest.json"
        manifest_path.write_text(json.dumps(self.mock_manifest_data), encoding="utf-8")
        self.manifest = load_manifest(manifest_path)
        self.resolver = AudienceContextResolver(self.manifest)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_landing_page_renders_neutral_shell(self) -> None:
        """Step 1: Landing page always resolves to None (neutral shell)."""
        landing_targets = [
            "index.md",
            "/index.md",
            "/",
            "",
            "/index.html",
            "index.html",
            PurePosixPath("index.md"),
            "site:home",
        ]
        for target in landing_targets:
            with self.subTest(target=str(target)):
                # Even with explicit candidate or stored journey, landing must be neutral (None)
                self.assertIsNone(
                    self.resolver.resolve_audience(target),
                )
                self.assertIsNone(
                    self.resolver.resolve_audience(target, explicit_audience="use"),
                )
                self.assertIsNone(
                    self.resolver.resolve_audience(target, query_param="maintain"),
                )
                self.assertIsNone(
                    self.resolver.resolve_audience(target, current_journey="maintain"),
                )

    def test_explicit_audience_honored_on_shared_document(self) -> None:
        """Step 2: Explicit audience is honored when the document belongs to it."""
        target = "specs/shared.md"
        # Explicit via explicit_audience parameter
        self.assertEqual(
            self.resolver.resolve_audience(target, explicit_audience="maintain"),
            "maintain",
        )
        self.assertEqual(
            self.resolver.resolve_audience(target, explicit_audience="use"),
            "use",
        )
        # Explicit via query_param parameter
        self.assertEqual(
            self.resolver.resolve_audience(target, query_param="maintain"),
            "maintain",
        )
        self.assertEqual(
            self.resolver.resolve_audience(target, query_param="use"),
            "use",
        )

    def test_explicit_audience_ignored_when_document_does_not_belong(self) -> None:
        """Step 2: Explicit audience is ignored fail-closed if document does not belong."""
        use_only = "use/guide.md"
        # maintain requested on use-only doc falls back to primary audience
        self.assertEqual(
            self.resolver.resolve_audience(use_only, explicit_audience="maintain"),
            "use",
        )

        maintain_only = "maintain/guide.md"
        # use requested on maintain-only doc falls back to primary audience
        self.assertEqual(
            self.resolver.resolve_audience(maintain_only, explicit_audience="use"),
            "maintain",
        )

    def test_preserved_journey_context(self) -> None:
        """Step 3: Stored journey context preserved if document belongs to it."""
        shared = "specs/shared.md"
        self.assertEqual(
            self.resolver.resolve_audience(shared, current_journey="maintain"),
            "maintain",
        )
        self.assertEqual(
            self.resolver.resolve_audience(shared, current_journey="use"),
            "use",
        )

        # But if document does not belong to the stored journey, falls back to primary
        maintain_only = "maintain/guide.md"
        self.assertEqual(
            self.resolver.resolve_audience(maintain_only, current_journey="use"),
            "maintain",
        )

    def test_fallback_to_primary_audience(self) -> None:
        """Step 4: Fallback to document primary audience when no or invalid context."""
        shared = "specs/shared.md"
        self.assertEqual(self.resolver.resolve_audience(shared), "use")

        use_only = "use/guide.md"
        self.assertEqual(self.resolver.resolve_audience(use_only), "use")
        # Invalid / unknown candidates are ignored fail-closed
        self.assertEqual(
            self.resolver.resolve_audience(use_only, explicit_audience="invalid"),
            "use",
        )
        self.assertEqual(
            self.resolver.resolve_audience(use_only, current_journey="bogus"),
            "use",
        )

        maintain_only = "maintain/guide.md"
        self.assertEqual(self.resolver.resolve_audience(maintain_only), "maintain")

    def test_find_document_variations(self) -> None:
        """Resilient document lookup handles path variants, clean URLs, and keys."""
        doc = self.resolver.find_document("specs/shared.md")
        self.assertIsNotNone(doc)
        self.assertEqual(doc["document"], "shared-spec")

        # Strip query string and fragment
        doc_query = self.resolver.find_document("specs/shared.md?audience=maintain#section-2")
        self.assertEqual(doc_query, doc)

        # Leading slash
        doc_slash = self.resolver.find_document("/specs/shared.md")
        self.assertEqual(doc_slash, doc)

        # By publication:document key
        doc_key = self.resolver.find_document("composition:shared-spec")
        self.assertEqual(doc_key, doc)

        # Non-existent target
        self.assertIsNone(self.resolver.find_document("nonexistent/doc.md"))

    def test_switch_audience_shared_document(self) -> None:
        """Switching audience on shared doc stays on doc and preserves fragment."""
        route, audience = self.resolver.switch_audience(
            "specs/shared.md", "maintain", current_fragment="#schema-details"
        )
        self.assertEqual(route, "specs/shared.md#schema-details")
        self.assertEqual(audience, "maintain")

        # Switching back to use
        route_use, aud_use = self.resolver.switch_audience(
            "specs/shared.md", "use"
        )
        self.assertEqual(route_use, "specs/shared.md")
        self.assertEqual(aud_use, "use")

    def test_switch_audience_single_audience_redirects_to_overview(self) -> None:
        """Switching audience on single-audience doc redirects to target overview."""
        # On use-only doc, switching to maintain redirects to maintain overview
        route, audience = self.resolver.switch_audience(
            "use/guide.md", "maintain"
        )
        self.assertEqual(route, "repository-trees/index.md")
        self.assertEqual(audience, "maintain")

        # On maintain-only doc, switching to use redirects to use overview
        route_use, aud_use = self.resolver.switch_audience(
            "maintain/guide.md", "use"
        )
        self.assertEqual(route_use, "web/index.md")
        self.assertEqual(aud_use, "use")

    def test_switch_audience_landing_page_redirects_to_overview(self) -> None:
        """Switching audience on landing page transitions to target overview."""
        route_use, aud_use = self.resolver.switch_audience("index.md", "use")
        self.assertEqual(route_use, "web/index.md")
        self.assertEqual(aud_use, "use")

        route_maint, aud_maint = self.resolver.switch_audience("index.md", "maintain")
        self.assertEqual(route_maint, "repository-trees/index.md")
        self.assertEqual(aud_maint, "maintain")

    def test_switch_audience_invalid_target_raises_error(self) -> None:
        """Invalid desired audience raises AudienceContextError."""
        with self.assertRaises(AudienceContextError):
            self.resolver.switch_audience("specs/shared.md", "unknown_audience")

    def test_export_runtime_map(self) -> None:
        """Export runtime map produces conforming JSON dictionary."""
        runtime_map = self.resolver.export_runtime_map()
        self.assertEqual(runtime_map["schema_version"], 1)
        self.assertEqual(runtime_map["audiences"], ["use", "maintain"])
        self.assertEqual(runtime_map["landing_destination"], "index.md")
        self.assertEqual(runtime_map["overviews"]["use"], "/web/")
        self.assertEqual(runtime_map["overviews"]["maintain"], "/repository-trees/")

        docs = runtime_map["documents"]
        self.assertIn("index.md", docs)
        self.assertTrue(docs["index.md"]["is_landing"])
        self.assertEqual(docs["index.md"]["primary"], "use")

        self.assertIn("specs/shared.md", docs)
        self.assertFalse(docs["specs/shared.md"]["is_landing"])
        self.assertEqual(set(docs["specs/shared.md"]["audiences"]), {"use", "maintain"})

    def test_cli_execution(self) -> None:
        """Test audience_context CLI commands."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_file = Path(tmp_dir) / "manifest.json"
            manifest_file.write_text(json.dumps(self.mock_manifest_data), encoding="utf-8")

            # Test resolve CLI
            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                code = main([
                    "--manifest", str(manifest_file),
                    "--resolve", "specs/shared.md",
                    "--explicit", "maintain",
                ])
            self.assertEqual(code, 0)
            res = json.loads(stdout.getvalue())
            self.assertEqual(res["resolved_audience"], "maintain")

            # Test export-runtime-map CLI
            stdout_map = io.StringIO()
            with patch("sys.stdout", stdout_map):
                code = main([
                    "--manifest", str(manifest_file),
                    "--export-runtime-map",
                ])
            self.assertEqual(code, 0)
            map_res = json.loads(stdout_map.getvalue())
            self.assertEqual(map_res["schema_version"], 1)


class ProductionSiteManifestContextTests(unittest.TestCase):
    """Verifies audience context resolution directly against the production site-manifest.json."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = create_resolver(ROOT / "site-manifest.json")

    def test_production_landing_page(self) -> None:
        self.assertIsNone(self.resolver.resolve_audience("index.md"))
        self.assertIsNone(self.resolver.resolve_audience("/"))
        self.assertIsNone(self.resolver.resolve_audience("site:portal-home"))

    def test_production_promoted_policy_docs(self) -> None:
        # Policy maintainer workflow doc should resolve to maintain
        maint_doc = "policy/policy-maintainer-workflow.md"
        self.assertEqual(self.resolver.resolve_audience(maint_doc), "maintain")
        # Explicit use on maintain-only doc should fail-close to maintain
        self.assertEqual(
            self.resolver.resolve_audience(maint_doc, explicit_audience="use"),
            "maintain",
        )

    def test_production_shared_docs(self) -> None:
        # Composer MVP is shared
        composer_doc = "composition/architecture/composer-mvp.md"
        self.assertEqual(self.resolver.resolve_audience(composer_doc), "use")
        self.assertEqual(
            self.resolver.resolve_audience(composer_doc, explicit_audience="maintain"),
            "maintain",
        )
        self.assertEqual(
            self.resolver.resolve_audience(composer_doc, current_journey="maintain"),
            "maintain",
        )


class AudienceRuntimeIntegrationTests(unittest.TestCase):
    """Verifies that audience runtime assets are properly registered, emitted, and integrated."""

    def test_registration_in_zensical_and_service_worker(self) -> None:
        zensical_cfg = (ROOT / "zensical.template.toml").read_text(encoding="utf-8")
        self.assertIn('"javascripts/audience-context.js"', zensical_cfg)

        sw_code = (ROOT / "assets/service-worker.js").read_text(encoding="utf-8")
        self.assertIn('"/javascripts/audience-context.js"', sw_code)
        self.assertIn('"/audience-runtime.json"', sw_code)

        runtime_map_path = ROOT / "assets/audience-runtime.json"
        self.assertTrue(runtime_map_path.is_file())
        data = json.loads(runtime_map_path.read_text(encoding="utf-8"))
        self.assertEqual(data, create_resolver(ROOT / "site-manifest.json").export_runtime_map())
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["audiences"], ["use", "maintain"])
        self.assertIn("routes", data)
        self.assertIn("/", data["routes"])
        self.assertIn("/web/", data["routes"])

    def test_javascript_runtime_invariants(self) -> None:
        js_code = (ROOT / "assets/javascripts/audience-context.js").read_text(encoding="utf-8")

        # Must load the runtime map
        self.assertIn('const RUNTIME_MAP_URL = "/audience-runtime.json";', js_code)
        self.assertIn("function loadRuntimeMap()", js_code)

        # Must subscribe to instant navigation
        self.assertIn("window.document$", js_code)
        self.assertIn("navigationDocument.subscribe", js_code)

        # Must handle browser popstate and pageshow
        self.assertIn('window.addEventListener("popstate"', js_code)
        self.assertIn('window.addEventListener("pageshow"', js_code)

        # Must NOT hardcode fallback to "use" for unknown routes
        self.assertNotIn('return "use";', js_code)

        # Delegated click listener
        self.assertIn('document.addEventListener("click"', js_code)
        self.assertIn('data-audience-switch', js_code)

    def test_simulated_instant_navigation_lifecycle(self) -> None:
        """Simulate route transitions and verify deterministic audience context resolution."""
        resolver = create_resolver(ROOT / "site-manifest.json")
        runtime_map = resolver.export_runtime_map()
        routes = runtime_map["routes"]
        docs = runtime_map["documents"]

        def simulate_route(path: str, *, explicit: str | None = None, stored: str | None = None) -> str | None:
            # Replicates getDocumentMetadata + resolveAudienceWithMetadata in audience-context.js
            dest = routes.get(path)
            if not dest and path.endswith("/"):
                dest = routes.get(path.rstrip("/"))
            if not dest and not path.endswith("/"):
                dest = routes.get(path + "/")
            if not dest and (path in ("/", "/index.html", "")):
                dest = "index.md"
            if not dest or dest not in docs:
                return None
            doc = docs[dest]
            if doc.get("is_landing"):
                return None
            doc_audiences = set(doc.get("audiences", []))
            primary = doc.get("primary")
            if explicit and explicit in doc_audiences:
                return explicit
            if stored and stored in doc_audiences:
                return stored
            if primary:
                return primary
            return None

        # 1. Landing route -> neutral shell (None)
        self.assertIsNone(simulate_route("/"))
        self.assertIsNone(simulate_route("/index.html"))

        # 2. Navigate from Landing to Use-only page -> "use"
        curr = simulate_route("/web/")
        self.assertEqual(curr, "use")
        stored_journey = curr

        # 3. Instant navigation: Use-only -> Maintain-only page -> "maintain"
        curr = simulate_route("/policy/policy-maintainer-workflow/", stored=stored_journey)
        self.assertEqual(curr, "maintain")
        stored_journey = curr

        # 4. Instant navigation: Maintain-only -> Use-only page -> "use"
        curr = simulate_route("/web/", stored=stored_journey)
        self.assertEqual(curr, "use")
        stored_journey = curr

        # 5. Instant navigation: Use -> shared doc -> preserves "use"
        curr = simulate_route("/composition/architecture/composer-mvp/", stored=stored_journey)
        self.assertEqual(curr, "use")

        # 6. Instant navigation: Maintain -> shared doc -> preserves "maintain"
        stored_journey = "maintain"
        curr = simulate_route("/composition/architecture/composer-mvp/", stored=stored_journey)
        self.assertEqual(curr, "maintain")

        # 7. Explicit switcher on shared doc -> switches to "use"
        curr = simulate_route("/composition/architecture/composer-mvp/", explicit="use", stored=stored_journey)
        self.assertEqual(curr, "use")

        # 8. Unknown route -> fails safe to None (neutral)
        self.assertIsNone(simulate_route("/unknown/unregistered/route/"))


if __name__ == "__main__":
    unittest.main()
