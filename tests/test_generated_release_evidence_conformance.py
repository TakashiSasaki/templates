from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_generated_repository_conformance import (  # noqa: E402
    _generated_repository,
    _is_template_maintainer_source,
    _load_json,
    _run_generated_python,
    _write_json,
)

RELEASE_REVISION = "0123456789abcdef0123456789abcdef01234567"


def _materialize_release_evidence(root: Path) -> None:
    implementation = _load_json(
        root / "contracts/implementation-evidence.json"
    )
    commands = implementation["commands"]
    gates = implementation["releaseGates"]

    command_results = []
    for index, command in enumerate(commands):
        command_results.append(
            {
                "commandId": command["id"],
                "commandDigest": hashlib.sha256(
                    command["command"].encode("utf-8")
                ).hexdigest(),
                "status": "passed",
                "exitCode": 0,
                "startedAt": f"2026-08-04T00:00:{index:02d}Z",
                "completedAt": f"2026-08-04T00:01:{index:02d}Z",
                "resultLocator": (
                    "product/release-run.json#/commands/"
                    f"{command['id']}"
                ),
            }
        )

    gate_results = [
        {
            "gateId": gate["id"],
            "status": "passed",
            "resultLocator": (
                "product/release-run.json#/gates/"
                f"{gate['id']}"
            ),
        }
        for gate in gates
    ]

    release = {
        "$schema": "../schemas/release-evidence.schema.json",
        "schemaVersion": 1,
        "mode": "product",
        "subject": {
            "revision": RELEASE_REVISION,
            "description": "Exact generated-product revision approved for release.",
        },
        "provenance": {
            "kind": "ci-run",
            "id": "generated-product-release-run",
            "locator": "product/release-run.json",
            "generatedAt": "2026-08-04T00:03:00Z",
        },
        "decision": {
            "status": "approved",
            "decidedAt": "2026-08-04T00:02:00Z",
            "description": "Every generated-product release gate passed.",
        },
        "commandResults": command_results,
        "gateResults": gate_results,
    }
    _write_json(root / "contracts/release-evidence.json", release)


@unittest.skipUnless(
    _is_template_maintainer_source(),
    "template-maintainer-only generated release evidence suite",
)
class GeneratedReleaseEvidenceConformanceTests(unittest.TestCase):
    def test_generated_product_release_evidence_passes_both_entry_points(
        self,
    ) -> None:
        source_release = _load_json(
            ROOT / "contracts/release-evidence.json"
        )
        self.assertEqual("template", source_release["mode"])

        with _generated_repository() as root:
            _materialize_release_evidence(root)

            for command in (
                (
                    "scripts/validate_release_evidence.py",
                    "--expected-revision",
                    RELEASE_REVISION,
                ),
                (
                    "-m",
                    "scripts.validate_release_evidence",
                    "--expected-revision",
                    RELEASE_REVISION,
                ),
            ):
                with self.subTest(command=command):
                    result = _run_generated_python(root, *command)
                    self.assertEqual(
                        0,
                        result.returncode,
                        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
                    )
                    self.assertIn(
                        "All release evidence and revision bindings are valid.",
                        result.stdout,
                    )

        self.assertEqual(
            "template",
            _load_json(ROOT / "contracts/release-evidence.json")["mode"],
        )

    def test_generated_release_rejects_revision_mismatch(self) -> None:
        with _generated_repository() as root:
            _materialize_release_evidence(root)

            result = _run_generated_python(
                root,
                "scripts/validate_release_evidence.py",
                "--expected-revision",
                "f" * 40,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "does not match expected revision",
            result.stderr,
        )

    def test_generated_release_rejects_command_definition_drift(self) -> None:
        with _generated_repository() as root:
            _materialize_release_evidence(root)
            release_path = root / "contracts/release-evidence.json"
            release = _load_json(release_path)
            release["commandResults"][0]["commandDigest"] = "0" * 64
            _write_json(release_path, release)

            result = _run_generated_python(
                root,
                "scripts/validate_release_evidence.py",
                "--expected-revision",
                RELEASE_REVISION,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "commandDigest does not match the authoritative command",
            result.stderr,
        )


class GeneratedReleaseEvidenceScopeTests(unittest.TestCase):
    def test_generated_release_suite_is_template_maintainer_only(self) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(
                GeneratedReleaseEvidenceConformanceTests,
                "__unittest_skip__",
                False,
            )
        )
        self.assertEqual(not source_is_template, suite_is_skipped)
        if suite_is_skipped:
            self.assertEqual(
                "template-maintainer-only generated release evidence suite",
                getattr(
                    GeneratedReleaseEvidenceConformanceTests,
                    "__unittest_skip_why__",
                ),
            )


if __name__ == "__main__":
    unittest.main()
