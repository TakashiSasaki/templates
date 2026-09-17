from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.resolve_publication_sources import (
    PUBLICATION_NAMES,
    SourceLockError,
    parse_overrides,
    resolve_sources,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "publication-sources.json"


class SourceResolutionTests(unittest.TestCase):
    def test_reviewed_lock_accepts_exact_full_sha_values(self) -> None:
        resolved = resolve_sources(LOCK, {})
        self.assertEqual(tuple(resolved), PUBLICATION_NAMES)
        self.assertTrue(all(len(value) == 40 for value in resolved.values()))

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
            f"composition={override}\npolicy={resolved['policy']}\n",
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


if __name__ == "__main__":
    unittest.main()
