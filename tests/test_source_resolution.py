from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.resolve_publication_sources import (
    ALL_PUBLICATION_NAMES,
    SourceLockError,
    parse_overrides,
    resolve_candidate_sources,
    resolve_sources,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "publication-sources.json"


class SourceResolutionTests(unittest.TestCase):
    def test_reviewed_lock_accepts_exact_full_sha_values(self) -> None:
        resolved = resolve_sources(LOCK, {})
        self.assertEqual(tuple(resolved), ALL_PUBLICATION_NAMES)
        self.assertTrue(all(len(value) == 40 for value in resolved.values()))

    def test_committed_cutover_uses_the_three_provider_tuple(self) -> None:
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertEqual(lock["schema_version"], 2)
        self.assertEqual(
            lock["publications"],
            {
                "modeling": {"revision": "202afe0206d673b2e2195a2df271d76862f9323a"},
                "composition": {"revision": "d4d0e35485ea0c2030e902f462374f6fb8f8588a"},
                "policy": {"revision": "aa6f9ac4822cbbb9b7bb6940525d54ad690d76d3"},
            },
        )

    def test_branch_and_abbreviated_override_refs_are_rejected(self) -> None:
        for ref in ("composition", "a" * 39):
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(SourceLockError, "full lowercase commit SHA"):
                    parse_overrides([f"composition={ref}"])

    def test_unknown_duplicate_and_missing_provider_overrides_fail_closed(self) -> None:
        with self.assertRaisesRegex(SourceLockError, "unknown publication"):
            parse_overrides(["site=" + "a" * 40])
        with self.assertRaisesRegex(SourceLockError, "duplicate override"):
            parse_overrides(["composition=" + "a" * 40, "composition=" + "b" * 40])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock.json"
            data = json.loads(LOCK.read_text(encoding="utf-8"))
            del data["publications"]["policy"]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(SourceLockError, "exactly"):
                resolve_sources(path, {})

    def test_override_does_not_mutate_reviewed_lock_and_output_order_is_stable(self) -> None:
        original = LOCK.read_bytes()
        override = "f" * 40
        resolved = resolve_sources(LOCK, {"composition": override})
        self.assertEqual(resolved["composition"], override)
        self.assertEqual(LOCK.read_bytes(), original)
        output = __import__("io").StringIO()
        write_outputs(output, resolved)
        self.assertEqual(
            output.getvalue(),
            f"modeling={resolved['modeling']}\ncomposition={override}\npolicy={resolved['policy']}\n",
        )

    def test_failed_cli_resolution_does_not_create_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "resolved.txt"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/resolve_publication_sources.py",
                    "--lock",
                    str(LOCK),
                    "--override",
                    "composition=branch",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_modeling_requires_an_explicit_candidate_override(self) -> None:
        with self.assertRaisesRegex(SourceLockError, "explicit full SHA"):
            resolve_candidate_sources(LOCK, {}, required_new_providers=("modeling",))
        resolved = resolve_candidate_sources(
            LOCK,
            {"modeling": "a" * 40},
            required_new_providers=("modeling",),
        )
        self.assertEqual(tuple(resolved), ("modeling", "composition", "policy"))

    def test_schema_two_lock_can_be_read_after_explicit_modeling_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock.json"
            path.write_bytes(
                json.dumps({
                    "schema_version": 2,
                    "repository": "TakashiSasaki/templates",
                    "publications": {
                        "modeling": {"revision": "a" * 40},
                        "composition": {"revision": "b" * 40},
                        "policy": {"revision": "c" * 40},
                    },
                }).encode()
            )
            self.assertEqual(
                resolve_sources(path, {}),
                {"modeling": "a" * 40, "composition": "b" * 40, "policy": "c" * 40},
            )


if __name__ == "__main__":
    unittest.main()
