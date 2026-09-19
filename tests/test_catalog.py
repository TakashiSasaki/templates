"""Boundary regressions through the same checker used by local and remote CI."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", ".git", ".venv"))

    def read(self, path):
        return json.loads((self.root / path).read_text(encoding="utf-8"))

    def write(self, path, obj):
        (self.root / path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def mutate(self, path, edit):
        value = self.read(path)
        edit(value)
        self.write(path, value)

    def rejected(self):
        with self.assertRaises(catalog.CatalogError):
            catalog.load(self.root)

    def test_real_collection_offline(self):
        with patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
            records, collections = catalog.load(self.root)
            self.assertGreaterEqual(len(records), 31)
            self.assertGreaterEqual(sum(r["ownership"] == "external" for r in records), 30)
            self.assertEqual(1, len(collections))
            catalog.project(self.root, check=True)

    def test_canonical_languages_and_reference_only(self):
        records, _ = catalog.load(self.root)
        self.assertEqual("ja", next(r for r in records if r["id"] == "ndc")["canonicalLanguage"])
        self.assertIn("識別と規範的所有者", (self.root / "docs/resources/ndc.md").read_text())
        for r in records:
            if r["id"] == "dcat":
                self.assertEqual("en", r["canonicalLanguage"])
            if r["ownership"] == "external":
                self.assertNotEqual(catalog.OWNER, r["normativeAuthority"]["id"])
                self.assertTrue(all(d["retrieval"]["mode"] == "reference" for d in r["distributions"]))

    def test_unknown_field(self):
        self.mutate("records/dcat.json", lambda r: r.update(inventedOwnership=True))
        self.rejected()

    def test_external_cannot_claim_modeling_owner(self):
        self.mutate("records/dcat.json", lambda r: r["normativeAuthority"].update(id=catalog.OWNER))
        self.rejected()

    def test_local_cannot_claim_external_owner(self):
        self.mutate("records/resource-record.json", lambda r: r["normativeAuthority"].update(id="https://example.org/"))
        self.rejected()

    def test_identity_basis_not_inferred_from_record_location(self):
        self.mutate("records/dcat.json", lambda r: r.update(identityBasis="local-identifier"))
        self.rejected()

    def test_duplicate_resource_identity(self):
        duplicate = self.read("records/dcat.json")
        duplicate["id"] = "duplicate-dcat"
        self.write("records/duplicate-dcat.json", duplicate)
        self.rejected()

    def test_filename_id_mismatch(self):
        self.mutate("records/dcat.json", lambda r: r.update(id="other"))
        self.rejected()

    def test_duplicate_json_keys(self):
        path = self.root / "records/dcat.json"
        path.write_text(path.read_text().replace('{', '{"id":"duplicate",', 1))
        self.rejected()

    def test_non_json_nan(self):
        path = self.root / "records/dcat.json"
        path.write_text(path.read_text().replace('"recordRevision": 2', '"recordRevision": NaN'))
        self.rejected()

    def test_invalid_dates(self):
        self.mutate("records/dcat.json", lambda r: r["provenance"].update(recordedOn="2026-02-30"))
        self.rejected()

    def test_observation_after_record(self):
        self.mutate("records/dcat.json", lambda r: r["provenance"].update(recordedOn="2025-01-01"))
        self.rejected()

    def test_unverified_is_not_observed(self):
        self.mutate("records/dcat.json", lambda r: r["provenance"]["sourceChecks"][0].update(state="reference-not-verified"))
        self.rejected()

    def test_observed_requires_date(self):
        self.mutate("records/dcat.json", lambda r: r["provenance"]["sourceChecks"][0].update(observedOn=None))
        self.rejected()

    def test_unknown_language_is_not_silently_english(self):
        self.mutate("records/dcat.json", lambda r: r.update(canonicalLanguage="fr"))
        self.rejected()

    def test_external_snapshot_cannot_be_smuggled_as_local_file(self):
        local = self.read("records/resource-record.json")["distributions"][0]["retrieval"]
        self.mutate("records/dcat.json", lambda r: r["distributions"][0].update(retrieval=local))
        self.rejected()

    def test_reference_cannot_claim_byte_pin(self):
        self.mutate("records/dcat.json", lambda r: r["distributions"][0]["retrieval"].update(bytePin="0" * 64))
        self.rejected()

    def test_license_claim_requires_license_and_evidence(self):
        self.mutate("records/dcat.json", lambda r: r["distributions"][0]["rights"].update(assessment="identified"))
        self.rejected()

    def test_unknown_distribution_edition(self):
        self.mutate("records/dcat.json", lambda r: r["distributions"][0].update(edition="https://example.org/unknown"))
        self.rejected()

    def test_duplicate_edition(self):
        def edit(r):
            edition = copy.deepcopy(r["editions"][0])
            edition["label"] += " alternate"
            r["editions"].append(edition)
        self.mutate("records/dcat.json", edit)
        self.rejected()

    def test_duplicate_distribution(self):
        def edit(r):
            dist = copy.deepcopy(r["distributions"][0])
            dist["language"] = "ja"
            r["distributions"].append(dist)
        self.mutate("records/dcat.json", edit)
        self.rejected()

    def test_bad_local_digest(self):
        self.mutate("records/resource-record.json", lambda r: r["distributions"][0]["retrieval"].update(sha256="0" * 64))
        self.rejected()

    def test_local_path_traversal(self):
        self.mutate("records/resource-record.json", lambda r: r["distributions"][0]["retrieval"].update(path="schemas/../README.md"))
        self.rejected()

    def test_input_symlink(self):
        file = self.root / "records/dcat.json"
        saved = self.root / "dcat-source.json"
        file.rename(saved)
        file.symlink_to(saved)
        self.rejected()

    def test_symlinked_artifact_ancestor(self):
        original = self.root / "schemas"
        original.rename(self.root / "schema-target")
        original.symlink_to(self.root / "schema-target", target_is_directory=True)
        self.rejected()

    def test_unexpected_input_and_missing_inventory(self):
        (self.root / "records/notes.txt").write_text("not a record")
        self.rejected()
        (self.root / "records/notes.txt").unlink()
        shutil.rmtree(self.root / "records")
        self.rejected()

    def test_collection_dangling_member(self):
        self.mutate("collections/initial-standards.json", lambda c: c["members"].append("unknown-resource"))
        self.rejected()

    def test_discovery_does_not_imply_adoption(self):
        self.mutate("records/dcat.json", lambda r: r["registration"].update(adoption="adopted"))
        self.rejected()

    def test_collection_cannot_silently_be_normative_bundle(self):
        self.mutate("collections/initial-standards.json", lambda c: c.update(kind="normative-bundle"))
        self.rejected()

    def relation(self):
        return {"predicate":"http://www.w3.org/2004/02/skos/core#closeMatch", "object":"https://example.org/model",
                "assertedBy":{"name":"Modeling", "id":catalog.OWNER}, "assertionOrigin":"local",
                "normativity":"informative", "subjectEdition":None, "objectEdition":None,
                "evidence":["https://example.org/evidence"], "scope":"Illustrative local assertion, not upstream approval."}

    def test_local_assertion_is_separate_from_upstream_ownership(self):
        self.mutate("records/dcat.json", lambda r: r["relationships"].append(self.relation()))
        catalog.load(self.root)

    def test_assertion_origin_mismatch(self):
        relation = self.relation()
        relation["assertionOrigin"] = "upstream"
        self.mutate("records/dcat.json", lambda r: r["relationships"].append(relation))
        self.rejected()

    def test_normative_assertion_needs_pinned_editions_and_evidence(self):
        relation = self.relation()
        relation["normativity"] = "normative"
        self.mutate("records/dcat.json", lambda r: r["relationships"].append(relation))
        self.rejected()

    def test_unknown_assertion_subject_edition(self):
        relation = self.relation()
        relation["subjectEdition"] = "https://example.org/absent-edition"
        self.mutate("records/dcat.json", lambda r: r["relationships"].append(relation))
        self.rejected()

    def test_remote_schema_resolution_fails_closed(self):
        self.mutate("schemas/collection-0.1.schema.json", lambda s: s.update({"$ref":"https://example.org/must-not-fetch"}))
        with patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
            self.rejected()

    def test_generation_is_deterministic_and_idempotent(self):
        before = (self.root / "catalog.json").read_bytes()
        catalog.project(self.root, check=False)
        self.assertEqual(before, (self.root / "catalog.json").read_bytes())
        self.assertIn(
            "generated by maintain-progressive-discovery",
            (self.root / "docs/resources/index.md").read_text(encoding="utf-8"),
        )
        catalog.project(self.root, check=False)
        catalog.project(self.root, check=True)

    def initialize_git(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'user.email', 'test@example.test'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'user.name', 'Test'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'commit', '-qm', 'baseline'], check=True)

    def test_generate_refuses_authored_or_dirty_discovery_index(self):
        self.initialize_git()
        target = self.root / 'docs/resources/index.md'
        catalog_before = (self.root / 'catalog.json').read_bytes()
        for content in ('# Authored navigation\n',
                        '<!-- generated by maintain-progressive-discovery -->\n# Human edit\n'):
            target.write_text(content)
            result = subprocess.run(
                [sys.executable, str(ROOT / 'tools/catalog.py'), 'generate', '--root', str(self.root)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(target.read_text(), content)
            self.assertEqual((self.root / 'catalog.json').read_bytes(), catalog_before)

    def test_generate_delegates_clean_stale_index_to_selected_cli(self):
        target = self.root / 'docs/resources/index.md'
        target.write_text('<!-- generated by maintain-progressive-discovery -->\n# Old output\n')
        self.initialize_git()
        catalog.project(self.root, check=False)
        catalog.project(self.root, check=True)
        catalog.project(self.root, check=False)

    def test_generate_preserves_concurrent_index_edit_and_reports_partial_outputs(self):
        self.initialize_git()
        self.mutate('records/dcat.json', lambda r: r.update(description='Updated description.'))
        target = self.root / 'docs/resources/index.md'
        original_write = Path.write_text
        def concurrent_write(path, content, *args, **kwargs):
            result = original_write(path, content, *args, **kwargs)
            if path == self.root / 'docs/resources/dcat.md':
                original_write(target, '# Concurrent authored navigation\n')
            return result
        with patch.object(Path, 'write_text', concurrent_write):
            with self.assertRaisesRegex(catalog.CatalogError, 'prior catalog outputs changed:.*dcat.md'):
                catalog.project(self.root, check=False)
        self.assertEqual(target.read_text(), '# Concurrent authored navigation\n')

    def test_stale_projection_and_regeneration(self):
        self.mutate("records/dcat.json", lambda r: r.update(description="Corrected local description."))
        with self.assertRaises(catalog.CatalogError):
            catalog.project(self.root, check=True)
        catalog.project(self.root, check=False)
        catalog.project(self.root, check=True)

    def test_crlf_is_detected_as_byte_difference(self):
        p = self.root / "CATALOG.md"
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
        with self.assertRaises(catalog.CatalogError):
            catalog.project(self.root, check=True)

    def test_missing_and_extra_projection(self):
        p = self.root / "docs/resources/dcat.md"
        p.unlink()
        with self.assertRaises(catalog.CatalogError):
            catalog.project(self.root, check=True)
        catalog.project(self.root, check=False)
        (self.root / "docs/resources/extra.md").write_text("extra")
        with self.assertRaises(catalog.CatalogError):
            catalog.project(self.root, check=False)

    def test_generated_ancestor_symlink(self):
        docs = self.root / "docs"
        docs.rename(self.root / "docs-target")
        docs.symlink_to(self.root / "docs-target", target_is_directory=True)
        with self.assertRaises(catalog.CatalogError):
            catalog.project(self.root, check=False)

    def pinned_relation(self):
        record = self.read("records/dcat.json")
        relation = self.relation()
        relation.update(object=record["resourceId"], subjectEdition=record["editions"][0]["id"],
                        objectEdition=record["editions"][0]["id"], normativity="normative",
                        evidence=[record["provenance"]["sourceChecks"][0]["url"]])
        return relation

    def test_pinned_observed_assertion_is_accepted(self):
        self.mutate("records/dcat.json", lambda r: r["relationships"].append(self.pinned_relation()))
        catalog.load(self.root)

    def test_normative_unobserved_evidence_is_rejected(self):
        relation = self.pinned_relation()
        relation["evidence"] = ["https://example.org/unobserved"]
        self.mutate("records/dcat.json", lambda r: r["relationships"].append(relation))
        self.rejected()

    def test_unknown_assertion_object_edition(self):
        relation = self.pinned_relation()
        relation["objectEdition"] = "https://example.org/absent-edition"
        self.mutate("records/dcat.json", lambda r: r["relationships"].append(relation))
        self.rejected()

    def test_invalid_administrative_schema(self):
        self.mutate("schemas/collection-0.1.schema.json", lambda s: s.update(type="invented-json-type"))
        self.rejected()

    def test_authority_identity_is_modeling(self):
        self.assertEqual("modeling", self.read("authority.json")["authority"])
        schema = self.read("schemas/resource-record-0.1.schema.json")
        self.assertEqual("modeling", schema["properties"]["recordAuthority"]["const"])
        self.assertEqual("https://github.com/TakashiSasaki/templates/tree/modeling", catalog.OWNER)
        self.assertTrue(all(r["recordAuthority"] == "modeling" for r in catalog.load(self.root)[0]))
        self.assertFalse((self.root / ".github/workflows/models-ci.yml").exists())

    def test_ci_uses_canonical_entrypoint_and_stack_bases(self):
        text = (self.root / ".github/workflows/modeling-ci.yml").read_text()
        self.assertIn("python3 tools/qualify.py", text)
        pull_request = text.split("  pull_request:\n", 1)[1].split(
            "  push:\n", 1
        )[0]
        self.assertNotIn("branches:", pull_request)
        self.assertNotIn("codex/modeling-arbitrary-stack-base", pull_request)
        self.assertIn("branches: [modeling]", text)
        self.assertNotIn("actions/setup-python", text)
        self.assertNotIn("python-version", text)
        self.assertNotIn("cache: pip", text)
        self.assertNotIn("matrix:", text)
        self.assertNotIn("windows", text.lower())
        self.assertIn("github.event.pull_request.head.sha", text)

    def test_provider_notification_is_post_qualification_push_only(self):
        text = (self.root / ".github/workflows/modeling-ci.yml").read_text()
        notify = text.split("  notify-integration:", 1)[1]
        self.assertIn("needs: qualify", notify)
        self.assertIn("github.event_name == 'push'", notify)
        self.assertIn("github.ref == 'refs/heads/modeling'", notify)
        self.assertIn("needs.qualify.result == 'success'", notify)
        self.assertIn("publication.provider-qualified", notify)
        self.assertIn("client_payload[provider_revision]", notify)
        self.assertNotIn("client_payload[producer_ref]", notify)
        self.assertIn("contents: write", notify)
        self.assertNotIn("pages: write", notify)

    def test_cli_failure_exit(self):
        self.mutate("records/dcat.json", lambda r: r.update(ownership="invented"))
        result = subprocess.run([sys.executable, str(ROOT / "tools/catalog.py"), "check", "--root", str(self.root)], capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertIn("ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
