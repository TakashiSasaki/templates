from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import generate_agent_bootstrap as bootstrap
from scripts.assemble_publications import copy_asset
from scripts.prepare_repository_tree_publication import prepare
from scripts.resolve_publication_sources import resolve_sources

ROOT = Path(__file__).resolve().parents[1]


class AgentBootstrapManifestTests(unittest.TestCase):
    def write_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        source_lock = root / "publication-sources.json"
        source_lock.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "repository": "TakashiSasaki/templates",
                    "publications": {
                        "composition": {"revision": "a" * 40},
                        "policy": {"revision": "b" * 40},
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        composition_release = root / "composition-installer.json"
        composition_release.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "channel": "stable",
                    "installer": {
                        "repository": "TakashiSasaki/templates",
                        "revision": "c" * 40,
                        "path": "scripts/install_composition_skill.py",
                        "sha256": "d" * 64,
                    },
                    "skill_source": {
                        "repository": "TakashiSasaki/templates",
                        "revision": "e" * 40,
                        "path": "skills/composition",
                    },
                    "toolchain": {
                        "repository": "TakashiSasaki/templates",
                        "revision": "f" * 40,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        policy_release = root / "policy-installer.json"
        policy_release.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "installer": {
                        "repository": "TakashiSasaki/templates",
                        "revision": "1" * 40,
                        "path": "scripts/install_agent_policy_skill.py",
                    },
                    "skill_source": {
                        "repository": "TakashiSasaki/templates",
                        "revision": "2" * 40,
                        "path": "skills/agent-policy",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return source_lock, composition_release, policy_release

    def test_build_manifest_projects_only_locked_release_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_lock, composition_release, policy_release = self.write_fixture(
                Path(temporary)
            )
            manifest = bootstrap.build_manifest(
                source_lock,
                composition_release,
                policy_release,
            )

        self.assertEqual(manifest["$schema"], bootstrap.SCHEMA_URL)
        self.assertEqual(manifest["schema_version"], 4)
        self.assertEqual(
            manifest["authorities"]["composition"],
            {
                "role": "artifact-capability-lifecycle-semantics",
                "publication_revision": "a" * 40,
                "overview_document_id": bootstrap.COMPOSITION_OVERVIEW_DOCUMENT_ID,
                "publication_catalog_path": bootstrap.PUBLICATION_CATALOG_PATH,
            },
        )
        self.assertEqual(
            manifest["authorities"]["policy"],
            {
                "role": "coding-agent-operating-policy",
                "publication_revision": "b" * 40,
                "overview_document_id": bootstrap.POLICY_OVERVIEW_DOCUMENT_ID,
                "publication_catalog_path": bootstrap.PUBLICATION_CATALOG_PATH,
                "relationship_to_composition": "independent-optional",
            },
        )
        self.assertEqual(
            manifest["authorities"]["site"],
            {
                "role": "publication-integration",
                "overview_document_id": bootstrap.SITE_OVERVIEW_DOCUMENT_ID,
                "consumer_repository_mutation": False,
            },
        )
        self.assertEqual(
            manifest["task_routing"]["policy"]["required_when"],
            [
                "task-explicitly-requires-coding-agent-operating-policy",
                "repository-needs-coding-agent-operating-rules",
            ],
        )
        self.assertEqual(
            manifest["task_routing"]["combined"]["authority_order"],
            ["composition", "policy"],
        )
        self.assertTrue(
            manifest["task_routing"]["combined"]["providers_remain_independent"]
        )
        self.assertEqual(
            manifest["integration_contracts"]["policy_composition_coexistence"],
            {
                "owner": "site",
                "document_id": bootstrap.COEXISTENCE_DOCUMENT_ID,
                "canonical_url": bootstrap.COEXISTENCE_URL,
            },
        )
        self.assertEqual(manifest["composition"]["publication_revision"], "a" * 40)
        self.assertEqual(manifest["policy"]["publication_revision"], "b" * 40)
        self.assertEqual(
            manifest["authorities"]["composition"]["publication_revision"],
            manifest["composition"]["publication_revision"],
        )
        self.assertEqual(
            manifest["authorities"]["policy"]["publication_revision"],
            manifest["policy"]["publication_revision"],
        )
        self.assertEqual(manifest["composition"]["installer"]["revision"], "c" * 40)
        self.assertEqual(manifest["composition"]["installer"]["sha256"], "d" * 64)
        self.assertEqual(manifest["composition"]["skill"]["revision"], "e" * 40)
        self.assertEqual(manifest["composition"]["toolchain"]["revision"], "f" * 40)
        self.assertEqual(manifest["policy"]["installer"]["revision"], "1" * 40)
        self.assertEqual(manifest["policy"]["skill"]["revision"], "2" * 40)
        self.assertEqual(
            manifest["composition"]["installer"]["url"],
            "https://raw.githubusercontent.com/TakashiSasaki/templates/"
            + "c" * 40
            + "/scripts/install_composition_skill.py",
        )
        self.assertEqual(
            manifest["composition"]["skill"]["instructions_url"],
            "https://raw.githubusercontent.com/TakashiSasaki/templates/"
            + "e" * 40
            + "/skills/composition/SKILL.md",
        )
        self.assertEqual(
            manifest["policy"]["installer"]["url"],
            "https://raw.githubusercontent.com/TakashiSasaki/templates/"
            + "1" * 40
            + "/scripts/install_agent_policy_skill.py",
        )
        self.assertEqual(
            manifest["policy"]["skill"]["instructions_url"],
            "https://raw.githubusercontent.com/TakashiSasaki/templates/"
            + "2" * 40
            + "/skills/agent-policy/SKILL.md",
        )
        self.assertEqual(
            manifest["composition_bootstrap"]["verify"],
            "sha256-before-execute",
        )
        self.assertEqual(
            manifest["composition_bootstrap"]["canonical_operation"],
            "execute-verified-installer-argv",
        )
        self.assertEqual(
            manifest["composition_bootstrap"]["reimplementation_policy"],
            "do-not-reimplement",
        )
        self.assertEqual(
            manifest["composition_bootstrap"]["verified_installer_argv"][:4],
            ["{python}", "-I", "-c", bootstrap.VERIFIED_INSTALLER_BOOTSTRAP],
        )
        self.assertEqual(
            manifest["composition_bootstrap"]["verified_installer_argv"][4:],
            [
                "{installer_url}",
                "{installer_sha256}",
                "{installer_file}",
                "{skill_target}",
            ],
        )
        self.assertEqual(
            manifest["composition_bootstrap"]["argument_bindings"],
            {
                "{installer_url}": "composition.installer.url",
                "{installer_sha256}": "composition.installer.sha256",
            },
        )
        self.assertEqual(
            manifest["composition_bootstrap"]["caller_inputs"],
            ["{python}", "{installer_file}", "{skill_target}"],
        )
        self.assertEqual(
            manifest["policy_bootstrap"]["verify"],
            "immutable-full-sha-url",
        )
        self.assertEqual(
            manifest["policy_bootstrap"]["immutable_installer_argv"][:4],
            ["{python}", "-I", "-c", bootstrap.IMMUTABLE_INSTALLER_BOOTSTRAP],
        )
        self.assertEqual(
            manifest["policy_bootstrap"]["argument_bindings"],
            {"{installer_url}": "policy.installer.url"},
        )
        self.assertEqual(
            manifest["policy_workflow"]["unmanaged_inspect_argv"],
            [
                "{python}",
                "{skill_target}/scripts/bootstrap.py",
                "--repository",
                "{repository}",
            ],
        )
        self.assertEqual(
            manifest["policy_workflow"]["unmanaged_apply_argv"][-1],
            "--apply",
        )
        self.assertEqual(
            manifest["composition_workflow"]["runner_argv"],
            [
                "{python}",
                "{skill_target}/scripts/run.py",
                "--repository",
                "{repository}",
                "{command}",
            ],
        )

    def test_verified_composition_bootstrap_checks_digest_before_writing_or_executing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_lock, composition_release, policy_release = self.write_fixture(root)
            manifest = bootstrap.build_manifest(
                source_lock,
                composition_release,
                policy_release,
            )
            source_installer = root / "fixture-installer.py"
            source_installer.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "target = Path(sys.argv[1])\n"
                "target.mkdir(parents=True, exist_ok=True)\n"
                "(target / 'executed').write_text('yes', encoding='utf-8')\n",
                encoding="utf-8",
            )
            installer_bytes = source_installer.read_bytes()
            good_digest = hashlib.sha256(installer_bytes).hexdigest()
            downloaded = root / "downloads" / "nested" / "downloaded-installer.py"
            skill_target = root / "skill-target"

            def resolve(expected_digest: str) -> list[str]:
                replacements = {
                    "{python}": sys.executable,
                    "{installer_url}": source_installer.as_uri(),
                    "{installer_sha256}": expected_digest,
                    "{installer_file}": str(downloaded),
                    "{skill_target}": str(skill_target),
                }
                return [
                    replacements.get(part, part)
                    for part in manifest["composition_bootstrap"][
                        "verified_installer_argv"
                    ]
                ]

            failed = subprocess.run(
                resolve("0" * 64),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("installer SHA-256 mismatch", failed.stderr)
            self.assertFalse(downloaded.exists())
            self.assertFalse(downloaded.parent.exists())
            self.assertFalse((skill_target / "executed").exists())

            subprocess.run(resolve(good_digest), check=True)
            self.assertEqual(downloaded.read_bytes(), installer_bytes)
            self.assertEqual(
                (skill_target / "executed").read_text(encoding="utf-8"),
                "yes",
            )

    def test_policy_bootstrap_executes_the_declared_immutable_installer_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_lock, composition_release, policy_release = self.write_fixture(root)
            manifest = bootstrap.build_manifest(
                source_lock,
                composition_release,
                policy_release,
            )
            source_installer = root / "fixture-policy-installer.py"
            source_installer.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "target = Path(sys.argv[1])\n"
                "target.mkdir(parents=True, exist_ok=True)\n"
                "(target / 'executed').write_text('policy', encoding='utf-8')\n",
                encoding="utf-8",
            )
            skill_target = root / "policy-skill"
            replacements = {
                "{python}": sys.executable,
                "{installer_url}": source_installer.as_uri(),
                "{skill_target}": str(skill_target),
            }
            command = [
                replacements.get(part, part)
                for part in manifest["policy_bootstrap"]["immutable_installer_argv"]
            ]
            subprocess.run(command, check=True)
            self.assertEqual(
                (skill_target / "executed").read_text(encoding="utf-8"),
                "policy",
            )

    def test_composition_release_descriptor_rejects_non_sha256_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_lock, composition_release, policy_release = self.write_fixture(
                Path(temporary)
            )
            value = json.loads(composition_release.read_text(encoding="utf-8"))
            value["installer"]["sha256"] = "not-a-digest"
            composition_release.write_text(
                json.dumps(value) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                bootstrap.AgentBootstrapError,
                "Composition installer.sha256 must be 64 lowercase hexadecimal characters",
            ):
                bootstrap.build_manifest(
                    source_lock,
                    composition_release,
                    policy_release,
                )

    def test_policy_release_descriptor_rejects_mutable_installer_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_lock, composition_release, policy_release = self.write_fixture(
                Path(temporary)
            )
            value = json.loads(policy_release.read_text(encoding="utf-8"))
            value["installer"]["revision"] = "policy"
            policy_release.write_text(json.dumps(value) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                bootstrap.AgentBootstrapError,
                "Policy installer.revision must be a full lowercase 40-character commit SHA",
            ):
                bootstrap.build_manifest(
                    source_lock,
                    composition_release,
                    policy_release,
                )

    def test_projection_rejects_stale_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "agent.json"
            path.write_bytes(b"{}\n")
            with self.assertRaisesRegex(
                bootstrap.AgentBootstrapError,
                "repository agent manifest is stale",
            ):
                bootstrap.verify_projection(
                    path,
                    b'{"expected":true}\n',
                    "repository agent manifest",
                )

    def test_repository_and_public_projections_are_identical(self) -> None:
        repository_manifest = ROOT / "agent.json"
        published_manifest = ROOT / "assets/agent.json"
        schema = ROOT / "schemas/agent-bootstrap.schema.json"
        published_schema = ROOT / "assets/schemas/agent-bootstrap.schema.json"

        self.assertEqual(repository_manifest.read_bytes(), published_manifest.read_bytes())
        self.assertEqual(schema.read_bytes(), published_schema.read_bytes())

        manifest = bootstrap.read_json_object(
            repository_manifest,
            "repository agent manifest",
        )
        schema_value = bootstrap.read_json_object(schema, "agent bootstrap schema")
        sources = resolve_sources(ROOT / "publication-sources.json", {})
        self.assertEqual(
            manifest["composition"]["publication_revision"],
            sources["composition"],
        )
        self.assertEqual(
            manifest["policy"]["publication_revision"],
            sources["policy"],
        )
        self.assertEqual(
            manifest["authorities"]["composition"]["publication_revision"],
            sources["composition"],
        )
        self.assertEqual(
            manifest["authorities"]["policy"]["publication_revision"],
            sources["policy"],
        )
        self.assertEqual(
            manifest["integration_contracts"]["policy_composition_coexistence"][
                "document_id"
            ],
            bootstrap.COEXISTENCE_DOCUMENT_ID,
        )
        self.assertEqual(
            manifest["integration_contracts"]["policy_composition_coexistence"][
                "canonical_url"
            ],
            bootstrap.COEXISTENCE_URL,
        )
        self.assertFalse(manifest["authorities"]["site"]["consumer_repository_mutation"])

        site_manifest = json.loads(
            (ROOT / "site-manifest.json").read_text(encoding="utf-8")
        )
        document_ids: set[str] = set()

        def collect_document_ids(nodes: list[dict[str, object]]) -> None:
            for node in nodes:
                publication = node.get("publication")
                document = node.get("document")
                if isinstance(publication, str) and isinstance(document, str):
                    document_ids.add(f"{publication}:{document}")
                children = node.get("children")
                if isinstance(children, list):
                    collect_document_ids(children)

        collect_document_ids(site_manifest["navigation"])
        for semantic_id in (
            manifest["authorities"]["composition"]["overview_document_id"],
            manifest["authorities"]["policy"]["overview_document_id"],
            manifest["authorities"]["site"]["overview_document_id"],
            manifest["integration_contracts"]["policy_composition_coexistence"][
                "document_id"
            ],
        ):
            with self.subTest(semantic_id=semantic_id):
                self.assertIn(semantic_id, document_ids)

        self.assertEqual(manifest["$schema"], schema_value["$id"])
        self.assertEqual(manifest["canonical_url"], bootstrap.CANONICAL_URL)
        self.assertEqual(manifest["schema_version"], 4)
        for required in (
            "authorities",
            "task_routing",
            "composition",
            "policy",
            "composition_bootstrap",
            "policy_bootstrap",
            "composition_workflow",
            "policy_workflow",
        ):
            self.assertIn(required, schema_value["required"])
        self.assertIn(
            "instructions_url",
            schema_value["properties"]["composition"]["properties"]["skill"]["required"],
        )
        self.assertIn(
            "instructions_url",
            schema_value["properties"]["policy"]["properties"]["skill"]["required"],
        )
        self.assertIn(
            "immutable_installer_argv",
            schema_value["properties"]["policy_bootstrap"]["required"],
        )
        self.assertIn(
            "unmanaged_inspect_argv",
            schema_value["properties"]["policy_workflow"]["required"],
        )

    def test_site_asset_pipeline_places_discovery_contract_at_public_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            prepared = temporary_root / "site-publication"
            prepare(ROOT, prepared)
            self.assertEqual(
                (prepared / "assets/agent.json").read_bytes(),
                (ROOT / "agent.json").read_bytes(),
            )

            docs_root = temporary_root / "build-docs"
            docs_root.mkdir()
            copy_asset(prepared / "assets", docs_root, "site assets")
            self.assertEqual(
                (docs_root / "agent.json").read_bytes(),
                (ROOT / "agent.json").read_bytes(),
            )
            self.assertEqual(
                (docs_root / "schemas/agent-bootstrap.schema.json").read_bytes(),
                (ROOT / "schemas/agent-bootstrap.schema.json").read_bytes(),
            )

    def test_exact_checked_out_provider_descriptors_match_projection_when_available(self) -> None:
        composition_root = ROOT.parent / "composition-source"
        policy_root = ROOT.parent / "policy-source"
        composition_release = composition_root / bootstrap.COMPOSITION_RELEASE_PATH
        policy_release = policy_root / bootstrap.POLICY_RELEASE_PATH
        if not composition_release.is_file() or not policy_release.is_file():
            self.skipTest("exact provider publication checkouts are not available")
        bootstrap.verify_site_projections(ROOT, composition_root, policy_root)


if __name__ == "__main__":
    unittest.main()
