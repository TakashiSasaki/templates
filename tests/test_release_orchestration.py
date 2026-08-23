from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_release_evidence_producer as evidence_helpers


MARKER = "template-composition-release-transaction.json"
EVIDENCE_BACKUP = "template-composition-release-evidence.backup"
BUNDLE_BACKUP = "template-composition-release-bundle.backup"


class ReleaseOrchestrationTests(unittest.TestCase):
    def helper(self) -> evidence_helpers.ReleaseEvidenceProducerTests:
        return evidence_helpers.ReleaseEvidenceProducerTests(
            methodName="test_success_produces_revision_bound_valid_evidence"
        )

    def materialize(self, root: Path, proof_script: str) -> tuple[object, Path, str, bytes, bytes]:
        helper = self.helper()
        target, revision, original_evidence = helper.materialize_candidate(root, proof_script)
        orchestrator = target / ".template-composition/release/produce_release.py"
        self.assertTrue(orchestrator.is_file())
        original_bundle = (target / "contracts/release-bundle.json").read_bytes()
        return helper, target, revision, original_evidence, original_bundle

    def run_release(
        self,
        target: Path,
        revision: str | None = None,
        *,
        recover_only: bool = False,
        isolated: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        arguments = [sys.executable]
        if isolated:
            arguments.append("-I")
        arguments.append(".template-composition/release/produce_release.py")
        if recover_only:
            arguments.append("--recover-only")
        elif revision is not None:
            arguments.extend(["--revision", revision])
        return subprocess.run(
            arguments,
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_transaction_state_absent(self, target: Path) -> None:
        git_dir = target / ".git"
        for name in (
            MARKER,
            MARKER + ".tmp",
            EVIDENCE_BACKUP,
            BUNDLE_BACKUP,
        ):
            self.assertFalse((git_dir / name).exists(), name)
            self.assertFalse((git_dir / name).is_symlink(), name)

    def write_interrupted_transaction(
        self,
        target: Path,
        revision: str,
        evidence: bytes,
        bundle: bytes,
    ) -> None:
        git_dir = target / ".git"
        evidence_path = target / "contracts/release-evidence.json"
        bundle_path = target / "contracts/release-bundle.json"
        (git_dir / EVIDENCE_BACKUP).write_bytes(evidence)
        (git_dir / BUNDLE_BACKUP).write_bytes(bundle)
        marker = {
            "schemaVersion": 1,
            "operation": "release",
            "revision": revision,
            "evidenceSha256": hashlib.sha256(evidence).hexdigest(),
            "bundleSha256": hashlib.sha256(bundle).hexdigest(),
            "evidenceMode": stat.S_IMODE(evidence_path.stat().st_mode),
            "bundleMode": stat.S_IMODE(bundle_path.stat().st_mode),
        }
        (git_dir / MARKER).write_text(
            json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_success_produces_evidence_and_bundle_and_commits_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            result = self.run_release(target, revision)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Release evidence and bundle produced", result.stdout)

            evidence_path = target / "contracts/release-evidence.json"
            bundle_path = target / "contracts/release-bundle.json"
            self.assertNotEqual(evidence_path.read_bytes(), original_evidence)
            self.assertNotEqual(bundle_path.read_bytes(), original_bundle)
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(evidence["subject"]["revision"], revision)
            self.assertEqual(evidence["decision"]["status"], "approved")
            self.assertEqual(bundle["subject"]["revision"], revision)
            self.assertEqual(bundle["handoff"]["status"], "ready")
            self.assert_transaction_state_absent(target)

    def test_proof_failure_restores_both_preoperation_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "raise SystemExit(9)\n",
            )
            result = self.run_release(target, revision)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )
            self.assert_transaction_state_absent(target)

    def test_bundle_stage_failure_rolls_back_new_evidence_too(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            helper, target, _, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            validator_relative = ".template-composition/validators/validate_release_bundle.py"
            (target / validator_relative).write_text(
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            helper.run_git(target, "add", validator_relative)
            helper.run_git(target, "commit", "--quiet", "--amend", "--no-edit")
            revision = helper.run_git(target, "rev-parse", "--verify", "HEAD^{commit}")

            result = self.run_release(target, revision)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("release bundle precondition/validation failed", result.stderr)
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )
            self.assert_transaction_state_absent(target)

    def test_recover_only_restores_digest_verified_preoperation_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            self.write_interrupted_transaction(
                target,
                revision,
                original_evidence,
                original_bundle,
            )
            (target / "contracts/release-evidence.json").write_bytes(b"partial evidence\n")
            (target / "contracts/release-bundle.json").write_bytes(b"partial bundle\n")

            result = self.run_release(target, recover_only=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Recovered incomplete release transaction", result.stdout)
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )
            self.assert_transaction_state_absent(target)

    def test_normal_run_recovers_prior_transaction_before_running_new_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            self.write_interrupted_transaction(
                target,
                revision,
                original_evidence,
                original_bundle,
            )
            (target / "contracts/release-evidence.json").write_bytes(b"partial evidence\n")
            (target / "contracts/release-bundle.json").write_bytes(b"partial bundle\n")

            result = self.run_release(target, revision)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Recovered incomplete release transaction", result.stdout)
            self.assertIn("Release evidence and bundle produced", result.stdout)
            evidence = json.loads(
                (target / "contracts/release-evidence.json").read_text(encoding="utf-8")
            )
            bundle = json.loads(
                (target / "contracts/release-bundle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["subject"]["revision"], revision)
            self.assertEqual(bundle["subject"]["revision"], revision)
            self.assert_transaction_state_absent(target)

    def test_corrupt_backup_fails_closed_without_overwriting_partial_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            self.write_interrupted_transaction(
                target,
                revision,
                original_evidence,
                original_bundle,
            )
            evidence_path = target / "contracts/release-evidence.json"
            bundle_path = target / "contracts/release-bundle.json"
            evidence_path.write_bytes(b"partial evidence\n")
            bundle_path.write_bytes(b"partial bundle\n")
            (target / ".git" / EVIDENCE_BACKUP).write_bytes(b"corrupt backup\n")

            result = self.run_release(target, recover_only=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("backup digest does not match transaction marker", result.stderr)
            self.assertEqual(evidence_path.read_bytes(), b"partial evidence\n")
            self.assertEqual(bundle_path.read_bytes(), b"partial bundle\n")
            self.assertTrue((target / ".git" / MARKER).is_file())

    def test_missing_backup_fails_closed_without_touching_partial_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            self.write_interrupted_transaction(
                target,
                revision,
                original_evidence,
                original_bundle,
            )
            evidence_path = target / "contracts/release-evidence.json"
            bundle_path = target / "contracts/release-bundle.json"
            evidence_path.write_bytes(b"partial evidence\n")
            bundle_path.write_bytes(b"partial bundle\n")
            (target / ".git" / BUNDLE_BACKUP).unlink()

            result = self.run_release(target, recover_only=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("cannot inspect release bundle backup", result.stderr)
            self.assertEqual(evidence_path.read_bytes(), b"partial evidence\n")
            self.assertEqual(bundle_path.read_bytes(), b"partial bundle\n")
            self.assertTrue((target / ".git" / MARKER).is_file())

    def test_symbolic_marker_fails_closed_without_following_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, _, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            git_dir = target / ".git"
            outside = Path(temp_dir) / "outside-marker.json"
            outside.write_text("{}\n", encoding="utf-8")
            marker = git_dir / MARKER
            try:
                marker.symlink_to(outside)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            result = self.run_release(target, recover_only=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn(
                "release transaction marker must be a regular non-symbolic file",
                result.stderr,
            )
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )
            self.assertTrue(marker.is_symlink())
            self.assertEqual(outside.read_text(encoding="utf-8"), "{}\n")

    def test_orchestrator_requires_python_isolated_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target, revision, original_evidence, original_bundle = self.materialize(
                Path(temp_dir),
                "print('orchestrated proof passed')\n",
            )
            result = self.run_release(target, revision, isolated=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("requires Python isolated mode", result.stderr)
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )
            self.assert_transaction_state_absent(target)


if __name__ == "__main__":
    unittest.main()
