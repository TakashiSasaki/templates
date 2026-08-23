from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_release_evidence_producer as evidence_helpers


class ReleaseBundleProducerTests(unittest.TestCase):
    def helper(self) -> evidence_helpers.ReleaseEvidenceProducerTests:
        return evidence_helpers.ReleaseEvidenceProducerTests(
            methodName="test_success_produces_revision_bound_valid_evidence"
        )

    def approved_candidate(self, root: Path) -> tuple[object, Path, str, bytes]:
        helper = self.helper()
        target, revision, _ = helper.materialize_candidate(
            root,
            "print('producer proof passed')\n",
        )
        original_bundle = (target / "contracts/release-bundle.json").read_bytes()
        evidence_result = helper.run_producer(target, revision)
        self.assertEqual(
            evidence_result.returncode,
            0,
            evidence_result.stdout + evidence_result.stderr,
        )
        return helper, target, revision, original_bundle

    def run_bundle(
        self, target: Path, revision: str, *, isolated: bool = True
    ) -> subprocess.CompletedProcess[str]:
        arguments = [sys.executable]
        if isolated:
            arguments.append("-I")
        arguments.extend(
            [
                ".template-composition/release/produce_release_bundle.py",
                "--revision",
                revision,
            ]
        )
        return subprocess.run(
            arguments,
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_success_produces_manifest_ordered_digest_closed_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original = self.approved_candidate(Path(temp_dir))
            result = self.run_bundle(target, revision)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Release bundle produced", result.stdout)

            bundle_path = target / "contracts/release-bundle.json"
            self.assertNotEqual(bundle_path.read_bytes(), original)
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            release = json.loads(
                (target / "contracts/release-evidence.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest = json.loads(
                (target / "contracts/manifest.json").read_text(encoding="utf-8")
            )
            expected_entries = [
                entry for entry in manifest["contracts"] if entry["id"] != "release_bundle"
            ]
            self.assertEqual(bundle["mode"], "product")
            self.assertEqual(bundle["subject"]["revision"], revision)
            self.assertEqual(bundle["handoff"]["status"], "ready")
            self.assertGreater(
                bundle["provenance"]["generatedAt"],
                release["provenance"]["generatedAt"],
            )
            self.assertEqual(
                [artifact["contractId"] for artifact in bundle["artifacts"]],
                [entry["id"] for entry in expected_entries],
            )
            for artifact, entry in zip(bundle["artifacts"], expected_entries):
                self.assertEqual(artifact["path"], entry["document"])
                self.assertEqual(
                    artifact["sha256"],
                    hashlib.sha256(
                        (target / entry["document"]).read_bytes()
                    ).hexdigest(),
                )

            validated = subprocess.run(
                [
                    sys.executable,
                    ".template-composition/validators/validate_release_bundle.py",
                    ".",
                    "--expected-revision",
                    revision,
                ],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                validated.returncode,
                0,
                validated.stdout + validated.stderr,
            )

    def test_revision_mismatch_and_tracked_drift_leave_bundle_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original = self.approved_candidate(Path(temp_dir))
            result = self.run_bundle(target, "0" * 40)
            self.assertEqual(result.returncode, 2)
            self.assertIn("revision does not match repository HEAD", result.stderr)
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(), original
            )

            routes = target / "contracts/routes.json"
            routes.write_text(
                routes.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            result = self.run_bundle(target, revision)
            self.assertEqual(result.returncode, 2)
            self.assertIn("raw tracked bytes differ", result.stderr)
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(), original
            )

    def test_post_write_validation_failure_restores_exact_seed_bytes(self) -> None:
        helper = self.helper()
        with tempfile.TemporaryDirectory() as temp_dir:
            target, _, _ = helper.materialize_candidate(
                Path(temp_dir),
                "print('producer proof passed')\n",
            )
            original_bundle = (target / "contracts/release-bundle.json").read_bytes()
            validator_relative = (
                ".template-composition/validators/validate_release_bundle.py"
            )
            (target / validator_relative).write_text(
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            helper.run_git(target, "add", validator_relative)
            helper.run_git(target, "commit", "--quiet", "--amend", "--no-edit")
            revision = helper.run_git(
                target, "rev-parse", "--verify", "HEAD^{commit}"
            )
            evidence_result = helper.run_producer(target, revision)
            self.assertEqual(
                evidence_result.returncode,
                0,
                evidence_result.stdout + evidence_result.stderr,
            )

            result = self.run_bundle(target, revision)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("release bundle precondition/validation failed", result.stderr)
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )

    def test_producer_requires_python_isolated_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original = self.approved_candidate(Path(temp_dir))
            result = self.run_bundle(target, revision, isolated=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("requires Python isolated mode", result.stderr)
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(), original
            )


if __name__ == "__main__":
    unittest.main()
