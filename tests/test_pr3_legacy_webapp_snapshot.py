from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBAPP_FILES = ROOT / "components" / "artifact.webapp-core" / "files"

# Git blob object IDs from legacy Webapp source snapshot
# fa269e1310a37ad46f3644ed4f46954a815380ec.
#
# Files in this map have not undergone a versioned semantic change since the
# migration and therefore remain byte-identical provenance checks. Routes and
# surfaces are intentionally excluded: the current authority has evolved both
# contract families through explicit breaking schema versions after the legacy
# snapshot.
UNCHANGED_LEGACY_BLOBS = {
    "contracts/ui-states.json": "d4ae16b89510befc257dc568b69da390ff799472",
    "contracts/viewports.json": "57f55e6a1346937eef229887c002a979f1e3eef2",
    "schemas/ui-states.schema.json": "bb23e330cebbd1d63498036464feb312c454a1cd",
    "schemas/viewports.schema.json": "7b440afe0ac9482c59cf80bd36bf97f511855ee6",
    "docs/migrations/routes-v1-to-v2.md": "b623aaa47b48ca2585d55550f4988d40de1cbf22",
    "docs/migrations/ui-states-v1-to-v2.md": "8e1b855280274f9b1577a3d1d3f6f0956d2e20c7",
}

EVOLVED_LEGACY_BLOBS = {
    "contracts/routes.json": "480fc10dcec657578a61acf0a12f74dee597ab7e",
    "contracts/surfaces.json": "eeb15feb65811df36363e57bbdac292809ee9450",
    "schemas/routes.schema.json": "ebc88f619552b06f2b8e648c3fd768a53c77ba45",
    "schemas/surfaces.schema.json": "33df7161f8ab9720143f7a90a2ab68872a019585",
}


def git_blob_id(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


class LegacyWebappSnapshotTests(unittest.TestCase):
    def test_unchanged_migrated_domain_bytes_match_legacy_snapshot(self) -> None:
        for relative, expected_blob in UNCHANGED_LEGACY_BLOBS.items():
            with self.subTest(path=relative):
                data = (WEBAPP_FILES / relative).read_bytes()
                self.assertEqual(git_blob_id(data), expected_blob)

    def test_versioned_contracts_have_evolved_from_legacy_snapshot(self) -> None:
        for relative, legacy_blob in EVOLVED_LEGACY_BLOBS.items():
            with self.subTest(path=relative):
                data = (WEBAPP_FILES / relative).read_bytes()
                self.assertNotEqual(git_blob_id(data), legacy_blob)


if __name__ == "__main__":
    unittest.main()
