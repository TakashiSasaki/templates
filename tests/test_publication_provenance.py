from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.write_publication_provenance import (
    ProvenanceError,
    parse_publication_commits,
    write_provenance,
)


class PublicationProvenanceTests(unittest.TestCase):
    def test_writes_sorted_multi_publication_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "build-provenance.json"
            write_provenance(
                output,
                "TakashiSasaki/templates",
                "a" * 40,
                {"webapp": "d" * 40, "policy": "c" * 40, "skill": "b" * 40},
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(2, payload["schema_version"])
            self.assertEqual(
                ["policy", "skill", "webapp"],
                list(payload["publication_commits"]),
            )

    def test_duplicate_publication_commit_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ProvenanceError,
            "duplicate publication commit: skill",
        ):
            parse_publication_commits(
                [f"skill={'a' * 40}", f"skill={'b' * 40}"]
            )


if __name__ == "__main__":
    unittest.main()
