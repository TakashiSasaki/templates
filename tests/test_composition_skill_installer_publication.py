from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path
from types import ModuleType

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / "release" / "composition-installer.json"
SCHEMA = ROOT / "schemas" / "composition-skill-installer-release.schema.json"
RELEASE_README = ROOT / "release" / "README.md"
CONSUMER_GUIDE = ROOT / "docs" / "consumer-guide.md"
SKILL_WALKTHROUGH = ROOT / "docs" / "guides" / "skill-first-use-walkthrough.md"
WEBAPP_WALKTHROUGH = ROOT / "docs" / "guides" / "webapp-product-walkthrough.md"
TRANSLATED_CONSUMER_GUIDE = ROOT / "translations" / "ja" / "docs" / "consumer-guide.md"
TRANSLATED_SKILL_WALKTHROUGH = (
    ROOT / "translations" / "ja" / "docs" / "guides" / "skill-first-use-walkthrough.md"
)
TRANSLATED_WEBAPP_WALKTHROUGH = (
    ROOT / "translations" / "ja" / "docs" / "guides" / "webapp-product-walkthrough.md"
)
INSTALLER_REVISION = "5a3cfb200ed68d87da1a8e128b61b40401820347"
INSTALLER_SHA256 = "114c3375f4edef8aa64f42ab3beeaae246fdf8b960f6eb09868648e6a62cd1ab"
SKILL_REVISION = "8defa866d088de7f8c29bc3a5443dc2df69983dc"
TOOLCHAIN_REVISION = "199f25731170a6e25d25aa759fa6edc038623f58"
RAW_INSTALLER_URL = (
    "https://raw.githubusercontent.com/TakashiSasaki/templates/"
    f"{INSTALLER_REVISION}/scripts/install_composition_skill.py"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load_script() -> ModuleType:
    path = ROOT / "scripts" / "verify_composition_skill_installer_release.py"
    spec = importlib.util.spec_from_file_location(
        "verify_composition_skill_installer_release", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_script()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class CompositionSkillInstallerPublicationTests(unittest.TestCase):
    def assert_verified_bootstrap_guidance(self, path: Path) -> None:
        content = path.read_text(encoding="utf-8")
        self.assertIn(RAW_INSTALLER_URL, content)
        self.assertIn(INSTALLER_SHA256, content)
        self.assertIn("hashlib.sha256(data).hexdigest()", content)
        self.assertIn("if actual != expected:", content)
        self.assertIn("subprocess.run", content)
        self.assertIn("Verified Composition installer SHA-256", content)
        self.assertNotIn("exec(urllib.request.urlopen", content)

    def test_release_descriptor_is_schema_valid_and_separates_identities(self) -> None:
        descriptor = load_json(DESCRIPTOR)
        Draft202012Validator(load_json(SCHEMA)).validate(descriptor)
        self.assertEqual(descriptor["schema_version"], 1)
        self.assertEqual(descriptor["channel"], "stable")
        self.assertEqual(
            descriptor["installer"],
            {
                "repository": "TakashiSasaki/templates",
                "revision": INSTALLER_REVISION,
                "path": "scripts/install_composition_skill.py",
                "sha256": INSTALLER_SHA256,
            },
        )
        self.assertEqual(
            descriptor["skill_source"],
            {
                "repository": "TakashiSasaki/templates",
                "revision": SKILL_REVISION,
                "path": "skills/composition",
            },
        )
        self.assertEqual(
            descriptor["toolchain"],
            {
                "repository": "TakashiSasaki/templates",
                "revision": TOOLCHAIN_REVISION,
            },
        )
        for revision in (INSTALLER_REVISION, SKILL_REVISION, TOOLCHAIN_REVISION):
            self.assertIsNotNone(FULL_SHA.fullmatch(revision))
        self.assertIsNotNone(SHA256.fullmatch(INSTALLER_SHA256))
        self.assertEqual(len({INSTALLER_REVISION, SKILL_REVISION, TOOLCHAIN_REVISION}), 3)

    def test_release_verifier_matches_pinned_history_and_head_ancestry(self) -> None:
        self.assertEqual(
            verifier.verify("HEAD"),
            (INSTALLER_REVISION, SKILL_REVISION, TOOLCHAIN_REVISION),
        )

    def test_release_readme_publishes_only_verified_full_sha_installer(self) -> None:
        content = RELEASE_README.read_text(encoding="utf-8")
        self.assert_verified_bootstrap_guidance(RELEASE_README)
        self.assertIn("installer script revision", content)
        self.assertIn("skill source revision", content)
        self.assertIn("stable Composition toolchain revision", content)
        self.assertIn(INSTALLER_REVISION, content)
        self.assertIn(SKILL_REVISION, content)
        self.assertIn(TOOLCHAIN_REVISION, content)
        self.assertIn("read-only `doctor` command", content)
        self.assertNotIn(
            "raw.githubusercontent.com/TakashiSasaki/templates/composition/", content
        )
        self.assertNotIn(
            "raw.githubusercontent.com/TakashiSasaki/templates/main/", content
        )
        self.assertNotIn("/tar.gz/composition", content)

    def test_consumer_guide_publishes_only_verified_full_sha_installer(self) -> None:
        content = CONSUMER_GUIDE.read_text(encoding="utf-8")
        self.assert_verified_bootstrap_guidance(CONSUMER_GUIDE)
        self.assertIn(INSTALLER_REVISION, content)
        self.assertIn(SKILL_REVISION, content)
        self.assertIn(TOOLCHAIN_REVISION, content)
        self.assertIn(" doctor", content)
        self.assertNotIn(
            "raw.githubusercontent.com/TakashiSasaki/templates/composition/", content
        )
        self.assertNotIn(
            "raw.githubusercontent.com/TakashiSasaki/templates/main/", content
        )
        self.assertNotIn("/tar.gz/composition", content)

    def test_first_use_walkthroughs_publish_verified_installer_and_doctor(self) -> None:
        for path in (SKILL_WALKTHROUGH, WEBAPP_WALKTHROUGH):
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                content = path.read_text(encoding="utf-8")
                self.assert_verified_bootstrap_guidance(path)
                self.assertIn("doctor", content)
                self.assertNotIn(
                    "raw.githubusercontent.com/TakashiSasaki/templates/composition/",
                    content,
                )
                self.assertNotIn(
                    "raw.githubusercontent.com/TakashiSasaki/templates/main/", content
                )

    def test_japanese_bootstrap_guidance_is_also_verified_before_execute(self) -> None:
        for path in (
            TRANSLATED_CONSUMER_GUIDE,
            TRANSLATED_SKILL_WALKTHROUGH,
            TRANSLATED_WEBAPP_WALKTHROUGH,
        ):
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assert_verified_bootstrap_guidance(path)

    def test_consumer_guide_documents_self_contained_validation_cache(self) -> None:
        content = CONSUMER_GUIDE.read_text(encoding="utf-8")
        self.assertIn("without manually creating a validation virtual environment", content)
        self.assertIn("cold materialized validation", content)
        self.assertIn("warm validation cache", content)
        self.assertIn("package acquisition", content)
        self.assertIn("COMPOSITION_VALIDATION_CACHE", content)
        self.assertIn("does not modify the product repository", content)

    def test_duplicate_release_json_members_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate JSON member"):
            verifier.parse_object(
                '{"schema_version":1,"schema_version":1}', "test"
            )

    def test_ancestry_helper_rejects_equal_revisions(self) -> None:
        with self.assertRaisesRegex(ValueError, "strict ancestor"):
            verifier.require_strict_ancestor(
                INSTALLER_REVISION, INSTALLER_REVISION, "self"
            )


if __name__ == "__main__":
    unittest.main()
