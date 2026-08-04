from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from generated_release_evidence_producer_fixture import (  # noqa: E402
    RELEASE_REVISION,
    _install_release_evidence_producer,
)
from test_generated_repository_conformance import (  # noqa: E402
    _generated_repository,
    _is_template_maintainer_source,
    _load_json,
    _run_generated_python,
    _write_json,
)


@unittest.skipUnless(
    _is_template_maintainer_source(),
    "template-maintainer-only generated release evidence production suite",
)
class GeneratedReleaseEvidenceProductionTests(unittest.TestCase):
    def run_producer(self, root: Path):
        return _run_generated_python(
            root,
            "product/produce_release_evidence.py",
            "--revision",
            RELEASE_REVISION,
        )

    def assert_release_validates(self, root: Path) -> None:
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

    def test_reviewed_runner_produces_release_evidence_from_actual_execution(
        self,
    ) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)

            result = self.run_producer(root)

            self.assertEqual(
                0,
                result.returncode,
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            self.assertIn(
                "generated release evidence: approved",
                result.stdout,
            )

            run = _load_json(root / "product/release-run.json")
            release = _load_json(root / "contracts/release-evidence.json")
            implementation = _load_json(
                root / "contracts/implementation-evidence.json"
            )

            self.assertEqual(RELEASE_REVISION, run["revision"])
            self.assertEqual(
                "python product/prove_conformance.py",
                run["command"]["authoritativeCommand"],
            )
            self.assertEqual(
                [sys.executable, "product/prove_conformance.py"],
                run["command"]["executionArgv"],
            )
            self.assertEqual(0, run["command"]["exitCode"])
            self.assertIn(
                "generated repository proof: 52 checks passed",
                run["command"]["stdout"],
            )
            self.assertEqual("passed", run["command"]["status"])
            self.assertEqual("passed", run["gate"]["status"])
            self.assertEqual("approved", run["decision"]["status"])

            self.assertEqual("product", release["mode"])
            self.assertEqual(RELEASE_REVISION, release["subject"]["revision"])
            self.assertEqual(
                implementation["commands"][0]["id"],
                release["commandResults"][0]["commandId"],
            )
            self.assertEqual(
                run["command"]["startedAt"],
                release["commandResults"][0]["startedAt"],
            )
            self.assertEqual(
                run["command"]["completedAt"],
                release["commandResults"][0]["completedAt"],
            )
            self.assertEqual("passed", release["commandResults"][0]["status"])
            self.assertEqual(0, release["commandResults"][0]["exitCode"])
            self.assertEqual("passed", release["gateResults"][0]["status"])
            self.assertEqual("approved", release["decision"]["status"])

            self.assert_release_validates(root)

        self.assertEqual(
            "template",
            _load_json(ROOT / "contracts/release-evidence.json")["mode"],
        )
        self.assertFalse((ROOT / "product").exists())

    def test_failed_reviewed_command_cannot_produce_approved_release(self) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            inventory_path = root / "product/conformance-targets.json"
            inventory = _load_json(inventory_path)
            first_target = next(iter(inventory["targets"].values()))
            first_target["positive"] = False
            _write_json(inventory_path, inventory)

            result = self.run_producer(root)

            self.assertEqual(1, result.returncode)
            self.assertIn(
                "generated release evidence: rejected",
                result.stderr,
            )

            run = _load_json(root / "product/release-run.json")
            release = _load_json(root / "contracts/release-evidence.json")
            self.assertEqual("failed", run["command"]["status"])
            self.assertNotEqual(0, run["command"]["exitCode"])
            self.assertEqual("failed", run["gate"]["status"])
            self.assertEqual("rejected", run["decision"]["status"])
            self.assertEqual("failed", release["commandResults"][0]["status"])
            self.assertNotEqual(0, release["commandResults"][0]["exitCode"])
            self.assertEqual("failed", release["gateResults"][0]["status"])
            self.assertEqual("rejected", release["decision"]["status"])
            self.assertNotEqual("approved", release["decision"]["status"])

            validation = _run_generated_python(
                root,
                "scripts/validate_release_evidence.py",
                "--expected-revision",
                RELEASE_REVISION,
            )
            self.assertEqual(1, validation.returncode)
            self.assertIn("status must be passed", validation.stderr)
            self.assertIn("release status must be approved", validation.stderr)

    def test_runner_rejects_authoritative_command_drift_before_execution(
        self,
    ) -> None:
        with _generated_repository() as root:
            _install_release_evidence_producer(root)
            implementation_path = root / "contracts/implementation-evidence.json"
            implementation = _load_json(implementation_path)
            implementation["commands"][0][
                "command"
            ] = "python -I product/prove_conformance.py"
            _write_json(implementation_path, implementation)

            result = self.run_producer(root)

            self.assertEqual(2, result.returncode)
            self.assertIn(
                "authoritative command registration changed",
                result.stderr,
            )
            self.assertFalse((root / "product/release-run.json").exists())
            self.assertEqual(
                "template",
                _load_json(root / "contracts/release-evidence.json")["mode"],
            )


class GeneratedReleaseEvidenceProductionScopeTests(unittest.TestCase):
    def test_generated_release_production_suite_is_template_maintainer_only(
        self,
    ) -> None:
        source_is_template = _is_template_maintainer_source()
        suite_is_skipped = bool(
            getattr(
                GeneratedReleaseEvidenceProductionTests,
                "__unittest_skip__",
                False,
            )
        )
        self.assertEqual(not source_is_template, suite_is_skipped)
        if suite_is_skipped:
            self.assertEqual(
                "template-maintainer-only generated release evidence production suite",
                getattr(
                    GeneratedReleaseEvidenceProductionTests,
                    "__unittest_skip_why__",
                ),
            )


if __name__ == "__main__":
    unittest.main()
