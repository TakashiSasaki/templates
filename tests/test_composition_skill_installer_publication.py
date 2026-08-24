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
INSTALLER_REVISION = "7412e9545e7648ddd8b3f4c05fe9ef171887d15b"
SKILL_REVISION = "5b93c5628cd3cf7e72393dc3999a70aeb2b2a826"
TOOLCHAIN_REVISION = "cd19bf8edacc146cd928b6175429e62985f17670"
RAW_INSTALLER_URL = (
    "https://raw.githubusercontent.com/TakashiSasaki/templates/"
    f"{INSTALLER_REVISION}/scripts/install_composition_skill.py"
)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


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
        self.assertEqual(len({INSTALLER_REVISION, SKILL_REVISION, TOOLCHAIN_REVISION}), 3)

    def test_release_verifier_matches_pinned_history_and_head_ancestry(self) -> None:
        self.assertEqual(
            verifier.verify("HEAD"),
            (INSTALLER_REVISION, SKILL_REVISION, TOOLCHAIN_REVISION),
        )

    def test_release_readme_publishes_only_full_sha_installer_url(self) -> None:
        content = RELEASE_README.read_text(encoding="utf-8")
        self.assertIn(RAW_INSTALLER_URL, content)
        self.assertIn("installer script revision", content)
        self.assertIn("skill source revision", content)
        self.assertIn("stable Composition toolchain revision", content)
        self.assertIn(INSTALLER_REVISION, content)
        self.assertIn(SKILL_REVISION, content)
        self.assertIn(TOOLCHAIN_REVISION, content)
        self.assertNotIn(
            "raw.githubusercontent.com/TakashiSasaki/templates/composition/", content
        )
        self.assertNotIn(
            "raw.githubusercontent.com/TakashiSasaki/templates/main/", content
        )
        self.assertNotIn("/tar.gz/composition", content)

    def test_consumer_guide_publishes_only_full_sha_installer_url(self) -> None:
        content = CONSUMER_GUIDE.read_text(encoding="utf-8")
        self.assertIn(RAW_INSTALLER_URL, content)
        self.assertIn(INSTALLER_REVISION, content)
        self.assertIn(SKILL_REVISION, content)
        self.assertIn(TOOLCHAIN_REVISION, content)
        self.assertNotIn(
            "raw.githubusercontent.com/TakashiSasaki/templates/composition/", content
        )
        self.assertNotIn(
            "raw.githubusercontent.com/TakashiSasaki/templates/main/", content
        )
        self.assertNotIn("/tar.gz/composition", content)

    def test_consumer_guide_documents_self_contained_validation_cache(self) -> None:
        content = CONSUMER_GUIDE.read_text(encoding="utf-8")
        self.assertIn("without manually creating a validation virtual environment", content)
        self.assertIn("cold validation", content)
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
