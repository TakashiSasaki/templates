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


class PublicationPreflightShellTests(unittest.TestCase):
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
