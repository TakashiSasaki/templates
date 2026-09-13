from __future__ import annotations

import copy
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema.exceptions import ValidationError

from scripts.publication_contract import PublicationContractError, read_json_object
from scripts.validate_audience_inventory import (
    AREA, ROOT, GitEvidence, InventoryError, tree_declarations,
    validate_inventory, validate_structure,
)


class MemoryEvidence:
    """A small independent catalog/manifest fixture, not reconstructed from rows."""

    def __init__(self, revisions):
        self.files = {}
        self.revisions = revisions
        for authority, source in (("site", "docs/landing.md"),
                                  ("composition", "README.md"),
                                  ("policy", "docs/overview.md")):
            identifier = "portal-home" if authority == "site" else "overview"
            self.put(authority, "docs/publication-catalog.json", {
                "schema_version": 3, "documents": [
                    {"id": identifier, "source": source, "optional": False, "home": True},
                ],
            })
            self.put(authority, source, "# Overview\n")
        self.put("site", "site-manifest.json", {
            "schema_version": 2, "home": {"publication": "site", "document": "portal-home"},
            "navigation": [
                {"title": "Documentation portal", "publication": "site", "document": "portal-home", "destination": "index.md"},
                {"title": "Composition", "children": [
                    {"title": "Overview", "publication": "composition", "document": "overview", "destination": "composition/index.md"},
                ]},
                {"title": "Policy", "children": [
                    {"title": "Overview", "publication": "policy", "document": "overview", "destination": "policy/index.md"},
                ]},
            ],
        })
        self.put("site", "publication-sources.json", {
            "schema_version": 1, "repository": "TakashiSasaki/templates",
            "publications": {a: {"revision": revisions[a]} for a in ("composition", "policy")},
        })
        self.put("site", "docs/repository-trees/overview.md", "# Repository trees\n")
        self.put("site", "scripts/prepare_repository_tree_publication.py",
                 "TREE_DOCUMENTS = ({'id': 'repository-trees', 'source': 'docs/repository-trees/overview.md'},)\n"
                 "TREE_NAVIGATION = {'title':'Repository trees','children':[{'title':'Overview','publication':'site',"
                 "'document':'repository-trees','destination':'repository-trees/index.md'}]}\n")

    def put(self, authority, path, value):
        self.files[(self.revisions[authority], path)] = (
            value if isinstance(value, str) else json.dumps(value)
        ).encode()

    def commit(self, revision):
        if revision not in self.revisions.values():
            raise InventoryError("missing revision")

    def read(self, revision, path):
        try:
            return self.files[(revision, path)]
        except KeyError as exc:
            raise InventoryError("missing audited file") from exc


class AudienceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = read_json_object(AREA / "migration-matrix.schema.json", "schema")
        cls.full = read_json_object(AREA / "migration-matrix.json", "matrix")

    def setUp(self):
        self.matrix = copy.deepcopy(self.full)
        selected = {"site": {"portal-home", "repository-trees"},
                    "composition": {"overview"}, "policy": {"overview"}}
        self.matrix["documents"] = {
            a: {i: e for i, e in rows.items() if i in selected[a]}
            for a, rows in self.matrix["documents"].items()
        }
        self.evidence = MemoryEvidence(self.matrix["audit"]["revisions"])

    def validate(self):
        return validate_inventory(self.matrix, self.schema, self.evidence)

    def test_complete_catalog_and_generated_surface(self):
        self.assertEqual(self.validate()["published"], 4)

    def test_committed_matrix_schema_and_decisions(self):
        validate_structure(self.full, self.schema)

    def test_missing_published_document(self):
        del self.matrix["documents"]["site"]["portal-home"]
        with self.assertRaisesRegex(InventoryError, "missing=.*portal-home"):
            self.validate()

    def test_missing_generated_document(self):
        del self.matrix["documents"]["site"]["repository-trees"]
        with self.assertRaisesRegex(InventoryError, "missing=.*repository-trees"):
            self.validate()

    def test_nonexistent_published_identity(self):
        rows = self.matrix["documents"]["composition"]
        rows["imaginary"] = rows.pop("overview")
        with self.assertRaisesRegex(InventoryError, "nonexistent=.*imaginary"):
            self.validate()

    def test_candidate_requires_existing_source_or_explicit_authoring(self):
        candidate = copy.deepcopy(self.full["documents"]["composition"]["provider-maintenance"])
        self.matrix["documents"]["composition"]["provider-maintenance"] = candidate
        self.assertEqual(self.validate()["candidates"], 1)
        candidate["source"] = "docs/missing.md"
        candidate["provider_action"] = "publish-existing"
        with self.assertRaisesRegex(InventoryError, "missing audited file"):
            self.validate()
        self.evidence.put("composition", "docs/missing.md", "# Maintainer guide\n")
        self.assertEqual(self.validate()["candidates"], 1)

    def test_duplicate_json_identity_is_rejected_before_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "matrix.json"
            path.write_text('{"documents":{"site":{"same":{},"same":{"notes":"different"}}}}')
            with self.assertRaisesRegex(PublicationContractError, "duplicate object member: same"):
                read_json_object(path, "matrix")

    def test_schema_rejects_unknowns_missing_fields_and_bad_navigation(self):
        mutations = [
            lambda m: m["documents"].update(unknown={}),
            lambda m: m["audit"]["revisions"].update(site="site"),
            lambda m: m["audit"]["revisions"].update(site="a" * 40 + "\n"),
            lambda m: m["audit"].update(started_at="2026-99-99T00:00:00Z"),
            lambda m: m["audit"]["revisions"].pop("policy"),
            lambda m: m["documents"]["site"]["portal-home"].pop("primary_audience"),
            lambda m: m["documents"]["site"]["portal-home"].update(primary_audience="beginner"),
            lambda m: m["documents"]["site"]["portal-home"].update(additional_audiences="maintain"),
            lambda m: m["documents"]["site"]["portal-home"].update(additional_audiences=["expert"]),
            lambda m: m["documents"]["site"]["portal-home"].update(additional_audiences=["maintain", "maintain"]),
            lambda m: m["documents"]["site"]["portal-home"].update(additional_audiences=["use"]),
            lambda m: m["documents"]["site"]["portal-home"].update(proposed_navigation=[]),
            lambda m: m["documents"]["site"]["portal-home"]["proposed_navigation"][0].update(path=["Unknown", "Page"]),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                value = copy.deepcopy(self.matrix)
                mutation(value)
                with self.assertRaises(ValidationError):
                    validate_structure(value, self.schema)

    def test_duplicate_source_under_another_identity(self):
        self.matrix["documents"]["site"]["duplicate"] = copy.deepcopy(
            self.matrix["documents"]["site"]["portal-home"])
        with self.assertRaisesRegex(InventoryError, "duplicated canonical source"):
            self.validate()

    def test_declared_shared_audience_needs_navigation_membership(self):
        self.matrix["documents"]["site"]["portal-home"]["proposed_navigation"].pop()
        with self.assertRaisesRegex(InventoryError, "exactly the declared audiences"):
            self.validate()

    def test_audited_source_destination_and_exposure_cannot_drift(self):
        for field, value in [("source", "docs/other.md"),
                             ("current_destination", "elsewhere.md"),
                             ("current_navigation", [["Wrong title"]])]:
            with self.subTest(field=field):
                original = self.matrix["documents"]["site"]["portal-home"][field]
                self.matrix["documents"]["site"]["portal-home"][field] = value
                with self.assertRaisesRegex(InventoryError, f"audited {field} mismatch"):
                    self.validate()
                self.matrix["documents"]["site"]["portal-home"][field] = original

    def test_provider_lock_mismatch_requires_explicit_reaudit(self):
        self.evidence.put("site", "publication-sources.json", {
            "schema_version": 1, "repository": "TakashiSasaki/templates",
            "publications": {a: {"revision": "a" * 40} for a in ("composition", "policy")},
        })
        with self.assertRaisesRegex(InventoryError, "differs from publication lock"):
            self.validate()

    def test_duplicate_catalog_and_manifest_identities_fail(self):
        for path in ("docs/publication-catalog.json", "site-manifest.json"):
            with self.subTest(path=path):
                evidence = MemoryEvidence(self.matrix["audit"]["revisions"])
                value = json.loads(evidence.read(evidence.revisions["site"], path))
                key = "documents" if "documents" in value else "navigation"
                value[key].append(value[key][0])
                evidence.put("site", path, value)
                with self.assertRaises((InventoryError, PublicationContractError)):
                    validate_inventory(self.matrix, self.schema, evidence)

    def test_generated_declarations_are_not_executed(self):
        with self.assertRaises(ValueError):
            tree_declarations(b"TREE_DOCUMENTS = print('must not execute')\nTREE_NAVIGATION = {}")

    def test_architecture_internal_links_and_incoming_discovery(self):
        for document in AREA.glob("*.md"):
            text = re.sub(r"```.*?```", "", document.read_text(), flags=re.S)
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if "://" in target:
                    continue
                path, _, fragment = target.partition("#")
                resolved = (document.parent / path).resolve() if path else document
                self.assertTrue(resolved.is_file(), f"{document}: missing {target}")
                if fragment:
                    headings = re.findall(r"^#+ (.+)$", resolved.read_text(), re.M)
                    slugs = [re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-") for h in headings]
                    self.assertIn(fragment, slugs, f"{document}: missing fragment {target}")
        for path in ("README.md", "MAINTENANCE.md", "docs/index.md", "docs/authority-model.md"):
            self.assertIn("architecture/audience/README.md", (ROOT / path).read_text())


class GitEvidenceTests(unittest.TestCase):
    def test_exact_objects_ignore_worktree_and_git_replacements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(["git", "-C", tmp, *args], stderr=subprocess.DEVNULL).decode().strip()
            git("init")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            (root / "document.md").write_text("# Original\n")
            (root / "link.md").symlink_to("document.md")
            git("add", ".")
            git("commit", "-m", "Original")
            original = git("rev-parse", "HEAD")
            (root / "document.md").write_text("# Changed\n")
            git("commit", "-am", "Changed")
            changed = git("rev-parse", "HEAD")
            git("replace", original, changed)
            evidence = GitEvidence(root)
            evidence.commit(original)
            self.assertEqual(evidence.read(original, "document.md"), b"# Original\n")
            with self.assertRaisesRegex(InventoryError, "not a regular file"):
                evidence.read(original, "link.md")
            with self.assertRaises(InventoryError):
                evidence.read(original, "absent.md")
            with self.assertRaises(InventoryError):
                evidence.commit("f" * 40)


if __name__ == "__main__":
    unittest.main()
