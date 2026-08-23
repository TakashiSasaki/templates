from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
COMMAND_TEXT = "python product/prove.py"


class ReleaseEvidenceProducerTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def git_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        for name in tuple(environment):
            if name.startswith("GIT_"):
                del environment[name]
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_AUTHOR_NAME": "Release producer acceptance",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "Release producer acceptance",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            }
        )
        return environment

    def run_git(self, target: Path, *arguments: str) -> str:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "maintenance.auto=false",
                "-c",
                "gc.auto=0",
                "-C",
                str(target),
                *arguments,
            ],
            env=self.git_environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"git {' '.join(arguments)} failed\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return completed.stdout.strip()

    def materialize_candidate(self, root: Path, proof_script: str) -> tuple[Path, str, bytes]:
        config = root / "composition.json"
        target = root / "consumer"
        self.write_json(
            config,
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {
                    "include": ["lifecycle.release-bundle"],
                    "exclude": [],
                },
                "parameters": {},
            },
        )
        applied = subprocess.run(
            [
                sys.executable,
                str(COMPOSER),
                "apply",
                "--config",
                str(config),
                "--target",
                str(target),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertTrue(
            (target / ".template-composition/release/candidate.py").is_file()
        )
        self.assertTrue(
            (
                target
                / ".template-composition/release/produce_release_evidence.py"
            ).is_file()
        )

        self.write_json(
            target / "contracts/implementation-evidence.json",
            {
                "$schema": "../schemas/implementation-evidence.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "commands": [
                    {
                        "id": "producer-proof",
                        "command": COMMAND_TEXT,
                        "purpose": "Exercise the managed release evidence producer.",
                    }
                ],
                "releaseGates": [
                    {
                        "id": "producer-release",
                        "purpose": "Block release unless the producer proof passes.",
                        "commandIds": ["producer-proof"],
                    }
                ],
                "records": [
                    {
                        "id": "producer-record",
                        "target": {
                            "kind": "contract-item",
                            "contractId": "surfaces",
                            "itemKind": "surface",
                            "itemId": "producer-fixture",
                        },
                        "implementationBoundary": {
                            "status": "verified",
                            "description": "The fixture implementation is represented by the proof script.",
                            "locator": "product/prove.py",
                        },
                        "positiveEvidence": [
                            {
                                "id": "producer-positive",
                                "status": "verified",
                                "kind": "integration-test",
                                "description": "The producer executes the declared proof.",
                                "locator": "product/prove.py",
                                "commandId": "producer-proof",
                                "expectedResult": "The proof exits successfully.",
                            }
                        ],
                        "negativeEvidence": [
                            {
                                "id": "producer-negative",
                                "status": "verified",
                                "kind": "integration-test",
                                "description": "A failing proof prevents approved release evidence.",
                                "locator": "product/prove.py",
                                "commandId": "producer-proof",
                                "expectedResult": "A non-zero proof leaves canonical evidence unchanged.",
                            }
                        ],
                        "releaseGateIds": ["producer-release"],
                    }
                ],
            },
        )
        self.write_json(
            target / "contracts/release-execution.json",
            {
                "$schema": "../schemas/release-execution.schema.json",
                "schemaVersion": 1,
                "mode": "product",
                "commands": [
                    {
                        "commandId": "producer-proof",
                        "argv": ["python", "product/prove.py"],
                        "workingDirectory": ".",
                    }
                ],
            },
        )
        product = target / "product"
        product.mkdir()
        (product / "prove.py").write_text(proof_script, encoding="utf-8")

        original_evidence = (target / "contracts/release-evidence.json").read_bytes()
        self.run_git(target, "init", "--quiet")
        self.run_git(target, "add", "--all", "--force")
        self.run_git(
            target,
            "commit",
            "--quiet",
            "--message",
            "Create release producer candidate",
        )
        revision = self.run_git(target, "rev-parse", "--verify", "HEAD^{commit}")
        self.assertRegex(revision, r"^[0-9a-f]{40}$")
        return target, revision, original_evidence

    def run_producer(
        self, target: Path, revision: str, *, isolated: bool = True
    ) -> subprocess.CompletedProcess[str]:
        arguments = [sys.executable]
        if isolated:
            arguments.append("-I")
        arguments.extend(
            [
                ".template-composition/release/produce_release_evidence.py",
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

    def assert_seed_unchanged(self, target: Path, original: bytes) -> None:
        self.assertEqual(
            (target / "contracts/release-evidence.json").read_bytes(), original
        )

    def test_success_produces_revision_bound_valid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, original = self.materialize_candidate(
                Path(temp_dir),
                "print('producer proof passed')\n",
            )
            result = self.run_producer(target, revision)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Release evidence produced", result.stdout)

            produced_path = target / "contracts/release-evidence.json"
            self.assertNotEqual(produced_path.read_bytes(), original)
            evidence = json.loads(produced_path.read_text(encoding="utf-8"))
            self.assertEqual(evidence["mode"], "product")
            self.assertEqual(evidence["subject"]["revision"], revision)
            self.assertEqual(evidence["decision"]["status"], "approved")
            self.assertEqual(
                evidence["commandResults"][0]["commandDigest"],
                hashlib.sha256(COMMAND_TEXT.encode("utf-8")).hexdigest(),
            )
            self.assertEqual(evidence["commandResults"][0]["status"], "passed")
            self.assertEqual(evidence["commandResults"][0]["exitCode"], 0)
            self.assertEqual(evidence["gateResults"][0]["status"], "passed")

            validated = subprocess.run(
                [
                    sys.executable,
                    ".template-composition/validators/validate_release_evidence.py",
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

    def test_proof_failure_leaves_canonical_evidence_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, original = self.materialize_candidate(
                Path(temp_dir),
                "raise SystemExit(7)\n",
            )
            result = self.run_producer(target, revision)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("canonical release evidence was restored", result.stderr)
            self.assert_seed_unchanged(target, original)

    def test_revision_and_preexisting_candidate_drift_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, original = self.materialize_candidate(
                Path(temp_dir),
                "print('producer proof passed')\n",
            )
            wrong_revision = "0" * 40
            result = self.run_producer(target, wrong_revision)
            self.assertEqual(result.returncode, 2)
            self.assertIn("revision does not match repository HEAD", result.stderr)
            self.assert_seed_unchanged(target, original)

            (target / "product/prove.py").write_text(
                "print('drifted proof')\n", encoding="utf-8"
            )
            result = self.run_producer(target, revision)
            self.assertEqual(result.returncode, 2)
            self.assertIn("raw tracked bytes differ", result.stderr)
            self.assert_seed_unchanged(target, original)

    def test_candidate_mutation_during_proof_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, original = self.materialize_candidate(
                Path(temp_dir),
                "from pathlib import Path\n"
                "path = Path('README.md')\n"
                "path.write_text(path.read_text(encoding='utf-8') + '\\nproof drift\\n', encoding='utf-8')\n",
            )
            result = self.run_producer(target, revision)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("candidate changed while release commands were running", result.stderr)
            self.assert_seed_unchanged(target, original)

    def test_untracked_nonignored_fails_but_ignored_local_environment_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, original = self.materialize_candidate(
                Path(temp_dir),
                "print('producer proof passed')\n",
            )
            (target / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            result = self.run_producer(target, revision)
            self.assertEqual(result.returncode, 2)
            self.assertIn("untracked non-ignored files", result.stderr)
            self.assert_seed_unchanged(target, original)
            (target / "unexpected.txt").unlink()

            ignored = target / ".venv"
            ignored.mkdir()
            (ignored / "ambient.bin").write_bytes(b"ambient local environment")
            result = self.run_producer(target, revision)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_producer_requires_python_isolated_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, original = self.materialize_candidate(
                Path(temp_dir),
                "print('producer proof passed')\n",
            )
            result = self.run_producer(target, revision, isolated=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("requires Python isolated mode", result.stderr)
            self.assert_seed_unchanged(target, original)


if __name__ == "__main__":
    unittest.main()
