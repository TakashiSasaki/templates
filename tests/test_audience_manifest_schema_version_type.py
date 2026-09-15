from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import AssemblyError, load_manifest


ROOT = Path(__file__).resolve().parents[1]


class AudienceManifestSchemaVersionTypeTests(unittest.TestCase):
    def test_non_integer_schema_versions_are_rejected(self) -> None:
        production = json.loads((ROOT / "site-manifest.json").read_text(encoding="utf-8"))
        for version in (3.0, "3", None):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                manifest = dict(production)
                manifest["schema_version"] = version
                path = Path(directory) / "site-manifest.json"
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(AssemblyError, "schema_version must be an integer"):
                    load_manifest(path)


if __name__ == "__main__":
    unittest.main()
