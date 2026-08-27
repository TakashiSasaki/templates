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
    def write_fixture(self, root: Path) -> tuple[Path, Path]:
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
        release = root / "composition-installer.json"
        release.write_text(
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
        return source_lock, release

    def test_build_manifest_projects_only_locked_release_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_lock, release = self.write_fixture(Path(temporary))
            manifest = bootstrap.build_manifest(source_lock, release)

        self.assertEqual(manifest["$schema"], bootstrap.SCHEMA_URL)
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["composition"]["publication_revision"], "a" * 40)
        self.assertEqual(manifest["composition"]["installer"]["revision"], "c" * 40)
        self.assertEqual(manifest["composition"]["installer"]["sha256"], "d" * 64)
        self.assertEqual(manifest["composition"]["skill"]["revision"], "e" * 40)
        self.assertEqual(manifest["composition"]["toolchain"]["revision"], "f" * 40)
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
        self.assertEqual(manifest["bootstrap"]["verify"], "sha256-before-execute")
        self.assertEqual(
            manifest["bootstrap"]["verified_installer_argv"][:4],
            ["{python}", "-I", "-c", bootstrap.VERIFIED_INSTALLER_BOOTSTRAP],
        )
        self.assertEqual(
            manifest["bootstrap"]["verified_installer_argv"][4:],
            [
                "{installer_url}",
                "{installer_sha256}",
                "{installer_file}",
                "{skill_target}",
            ],
        )
        self.assertEqual(
            manifest["bootstrap"]["argument_bindings"],
            {
                "{installer_url}": "composition.installer.url",
                "{installer_sha256}": "composition.installer.sha256",
            },
        )
        self.assertEqual(
            manifest["bootstrap"]["caller_inputs"],
            ["{python}", "{installer_file}", "{skill_target}"],
        )
        self.assertEqual(
            manifest["workflow"]["runner_argv"],
            [
                "{python}",
                "{skill_target}/scripts/run.py",
                "--repository",
                "{repository}",
                "{command}",
            ],
        )

    def test_verified_bootstrap_checks_digest_before_writing_or_executing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_lock, release = self.write_fixture(root)
            manifest = bootstrap.build_manifest(source_lock, release)
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
            downloaded = root / "downloaded-installer.py"
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
                    for part in manifest["bootstrap"]["verified_installer_argv"]
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
            self.assertFalse((skill_target / "executed").exists())

            subprocess.run(resolve(good_digest), check=True)
            self.assertEqual(downloaded.read_bytes(), installer_bytes)
            self.assertEqual(
                (skill_target / "executed").read_text(encoding="utf-8"),
                "yes",
            )

    def test_release_descriptor_rejects_non_sha256_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_lock, release = self.write_fixture(Path(temporary))
            value = json.loads(release.read_text(encoding="utf-8"))
            value["installer"]["sha256"] = "not-a-digest"
            release.write_text(json.dumps(value) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                bootstrap.AgentBootstrapError,
                "installer.sha256 must be 64 lowercase hexadecimal characters",
            ):
                bootstrap.build_manifest(source_lock, release)

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

        manifest = bootstrap.read_json_object(repository_manifest, "repository agent manifest")
        schema_value = bootstrap.read_json_object(schema, "agent bootstrap schema")
        sources = resolve_sources(ROOT / "publication-sources.json", {})
        self.assertEqual(
            manifest["composition"]["publication_revision"],
            sources["composition"],
        )
        self.assertEqual(manifest["$schema"], schema_value["$id"])
        self.assertEqual(manifest["canonical_url"], bootstrap.CANONICAL_URL)
        self.assertIn(
            "instructions_url",
            schema_value["properties"]["composition"]["properties"]["skill"]["required"],
        )
        self.assertIn(
            "verified_installer_argv",
            schema_value["properties"]["bootstrap"]["required"],
        )
        self.assertIn(
            "argument_bindings",
            schema_value["properties"]["bootstrap"]["required"],
        )
        self.assertIn(
            "runner_argv",
            schema_value["properties"]["workflow"]["required"],
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

    def test_exact_checked_out_composition_descriptor_matches_projection_when_available(self) -> None:
        composition_root = ROOT.parent / "composition-source"
        release = composition_root / "release/composition-installer.json"
        if not release.is_file():
            self.skipTest("exact Composition publication checkout is not available")
        bootstrap.verify_site_projections(ROOT, composition_root)


if __name__ == "__main__":
    unittest.main()