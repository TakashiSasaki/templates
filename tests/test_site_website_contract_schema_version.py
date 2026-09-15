from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import site_website_contract as website


ROOT = Path(__file__).resolve().parents[1]


class SiteWebsiteContractSchemaVersionTests(unittest.TestCase):
    def _repository_with_manifest_version(self, version: object) -> Path:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        shutil.copy2(ROOT / "zensical.template.toml", root / "zensical.template.toml")
        manifest = json.loads((ROOT / "site-manifest.json").read_text(encoding="utf-8"))
        manifest["schema_version"] = version
        (root / "site-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        return root

    def tearDown(self) -> None:
        temp_dir = getattr(self, "temp_dir", None)
        if temp_dir is not None:
            temp_dir.cleanup()
            del self.temp_dir

    def test_rejects_non_integer_schema_versions_before_projection(self) -> None:
        for version in (3.0, "3", None, True):
            with self.subTest(version=version):
                root = self._repository_with_manifest_version(version)
                with self.assertRaisesRegex(ValueError, "schema_version must be an integer"):
                    website.documents(root)
                self.temp_dir.cleanup()
                del self.temp_dir

    def test_rejects_unsupported_integer_schema_version(self) -> None:
        root = self._repository_with_manifest_version(4)
        with self.assertRaisesRegex(ValueError, "unsupported site manifest schema_version: 4"):
            website.documents(root)


if __name__ == "__main__":
    unittest.main()
