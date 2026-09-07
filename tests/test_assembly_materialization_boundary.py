from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import load_catalog


class AssemblyMaterializationBoundaryTests(unittest.TestCase):
    def test_load_catalog_materializes_generated_assets_before_consumption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            catalog = {
                "schema_version": 4,
                "documents": [
                    {
                        "id": "overview",
                        "source": "README.md",
                        "optional": False,
                        "home": True,
                    }
                ],
                "assets": [
                    {
                        "source": "generated/output.bin",
                        "destination": "runtime/output.bin",
                        "optional": False,
                        "source_kind": "generated",
                    }
                ],
            }
            catalog_path = root / "docs" / "publication-catalog.json"
            catalog_path.parent.mkdir(parents=True)
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

            materializer = root / "scripts" / "materialize_publication.py"
            materializer.parent.mkdir(parents=True)
            materializer.write_text(
                """from __future__ import annotations
import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
args = parser.parse_args()
counter = args.source_root / 'materializer-runs.txt'
count = int(counter.read_text(encoding='utf-8')) + 1 if counter.exists() else 1
counter.write_text(str(count), encoding='utf-8')
target = args.source_root / 'generated' / 'output.bin'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(b'generated')
""",
                encoding="utf-8",
            )

            documents, assets = load_catalog("fixture", root)
            self.assertEqual({"overview"}, set(documents))
            self.assertEqual("generated/output.bin", assets[0]["source"].as_posix())
            self.assertEqual(b"generated", (root / "generated" / "output.bin").read_bytes())

            # Repeated canonical catalog consumption keeps both validation phases
            # but does not re-run the expensive provider generator on success.
            load_catalog("fixture", root)
            self.assertEqual(
                "1",
                (root / "materializer-runs.txt").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
