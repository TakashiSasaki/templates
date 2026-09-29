"""Regression coverage for the Site publication preflight shell wrapper."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/publication-reconcile.yml"
STEP_NAME = "Site preflight against the selected public Bundle contract"
INSTALL_STEP_NAME = "Install pinned Site renderer dependencies"
DEPENDENCY_BOUNDARY_STEP_NAME = "Validate Site build dependency boundary"


def preflight_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    step = next(
        step
        for step in workflow["jobs"]["classify"]["steps"]
        if step.get("name") == STEP_NAME
    )
    return step["run"]


def rendered_script() -> str:
    return re.sub(r"\$\{\{.*?\}\}", "SAFE_GITHUB_EXPRESSION", preflight_script())


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def classify_steps() -> list[dict]:
    return workflow()["jobs"]["classify"]["steps"]


class PublicationPreflightShellTests(unittest.TestCase):
    def test_classify_establishes_the_pinned_renderer_environment_before_preflight(self):
        steps = classify_steps()
        install_index = next(
            index
            for index, step in enumerate(steps)
            if step.get("name") == INSTALL_STEP_NAME
        )
        boundary_index = next(
            index
            for index, step in enumerate(steps)
            if step.get("name") == DEPENDENCY_BOUNDARY_STEP_NAME
        )
        preflight_index = next(
            index
            for index, step in enumerate(steps)
            if step.get("name") == STEP_NAME
        )
        install = steps[install_index]["run"]
        boundary = steps[boundary_index]["run"]

        self.assertLess(install_index, boundary_index)
        self.assertLess(boundary_index, preflight_index)
        self.assertIn("python3 -m pip install", install)
        self.assertIn("--no-deps", install)
        self.assertIn("--requirement requirements-build.lock", install)
        self.assertIn("python3 -m pip check", install)
        self.assertEqual(
            boundary,
            "python3 scripts/check_python_dependencies.py . --environment build",
        )

    def test_reconciliation_keeps_renderer_install_out_of_adoption_job(self):
        adoption_steps = workflow()["jobs"]["adopt_lock_pr"]["steps"]
        adoption_source = "\n".join(step.get("run", "") for step in adoption_steps)

        self.assertNotIn("requirements-build.lock", adoption_source)
        self.assertNotIn("zensical", adoption_source)
        self.assertNotIn("pip check", adoption_source)
        self.assertNotIn("check_python_dependencies.py", adoption_source)

    def test_reconciliation_uses_the_real_site_qualification_entrypoint(self):
        preflight = next(step for step in classify_steps() if step.get("name") == STEP_NAME)
        self.assertIn("python3 scripts/qualify_site_candidate.py", preflight["run"])

    def test_workflow_does_not_install_an_unpinned_zensical_package(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"pip install[^\n]*zensical")

    def test_exact_preflight_step_is_valid_bash_after_expression_rendering(self):
        result = subprocess.run(
            ["bash", "-n", "-c", rendered_script()],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ordinary_pycode_heredoc_terminators_are_at_column_zero(self):
        lines = rendered_script().splitlines()
        openers = [line for line in lines if "<<'PYCODE'" in line]
        terminators = [line for line in lines if line.strip() == "PYCODE"]

        self.assertEqual(len(openers), len(terminators))
        self.assertGreaterEqual(len(openers), 3)
        self.assertTrue(all(line == "PYCODE" for line in terminators))

    def test_wrapper_reaches_qualified_bundle_branch(self):
        result, report, output = self._run_wrapper(
            bundle=True,
            receipt=True,
            qualification_report={
                "boundary": "integration-to-site",
                "classification": "NOT_ELIGIBLE",
                "idempotency_key": "qualified-key",
                "trusted": {
                    "policy_revision": "a" * 40,
                    "controller_revision": "b" * 40,
                },
                "evidence_refs": ["trusted-receipt://receipt"],
                "checks": {"results": {"site-qualification": "passed"}, "not_run": []},
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["classification"], "NOT_ELIGIBLE")
        self.assertEqual(report["idempotency_key"], "qualified-key")
        self.assertIn("site_gate=passed", output)

    def test_wrapper_reaches_missing_bundle_fallback(self):
        result, report, output = self._run_wrapper(bundle=False, receipt=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["reason_codes"], ["MISSING_INTEGRATION_ARTIFACT"])
        self.assertEqual(report["classification"], "INFRASTRUCTURE_FAILURE")
        self.assertIn("site_gate=stopped", output)

    def test_wrapper_reaches_missing_receipt_fallback(self):
        result, report, output = self._run_wrapper(bundle=True, receipt=False)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["reason_codes"], ["MISSING_TRUSTED_INTEGRATION_RECEIPT"])
        self.assertEqual(report["classification"], "INFRASTRUCTURE_FAILURE")
        self.assertIn("site_gate=stopped", output)

    def _run_wrapper(self, *, bundle, receipt, qualification_report=None):
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            (worktree / "candidate-integration-source.json").write_text(
                json.dumps({"integration_revision": "c" * 40}), encoding="utf-8"
            )
            if bundle:
                (worktree / "publication-bundle").mkdir()
            if receipt:
                (worktree / "trusted-integration-receipt.json").write_text(
                    "trusted receipt", encoding="utf-8"
                )

            fake_python = worktree / "python3"
            fake_python.write_text(
                "#!" + sys.executable + "\n"
                "import json\n"
                "import os\n"
                "import sys\n"
                "\n"
                "if sys.argv[1:2] == ['scripts/qualify_site_candidate.py']:\n"
                "    report = " + repr(qualification_report) + "\n"
                "    if report is None:\n"
                "        raise SystemExit('qualification stub was not configured')\n"
                "    output = sys.argv[sys.argv.index('--output') + 1]\n"
                "    with open(output, 'w', encoding='utf-8') as handle:\n"
                "        json.dump(report, handle)\n"
                "    raise SystemExit(0)\n"
                "\nos.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n",
                encoding="utf-8",
            )
            fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

            output_path = worktree / "github-output.txt"
            summary_path = worktree / "summary.txt"
            environment = {
                **os.environ,
                "PATH": str(worktree) + os.pathsep + os.environ.get("PATH", ""),
                "TRUSTED_POLICY": "d" * 40,
                "TRUSTED_CONTROLLER": "e" * 40,
                "TRUSTED_RECEIPT_AVAILABLE": "true" if receipt else "false",
                "GITHUB_OUTPUT": str(output_path),
                "GITHUB_STEP_SUMMARY": str(summary_path),
            }
            result = subprocess.run(
                ["bash", "-e", "-c", rendered_script()],
                cwd=worktree,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            report_path = worktree / "site-reconcile-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            output = output_path.read_text(encoding="utf-8")
            return result, report, output


if __name__ == "__main__":
    unittest.main()
