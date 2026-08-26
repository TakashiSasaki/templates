from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/composer-runtime.yml"
SUPPORTED_PYTHONS = {"3.11", "3.12", "3.13", "3.14"}
SUPPORTED_OSES = {"ubuntu-24.04", "windows-2022"}
REPRESENTATIVE_PAIRS = {
    *(("ubuntu-24.04", version) for version in SUPPORTED_PYTHONS),
    ("windows-2022", "3.12"),
}
FULL_PAIRS = {
    (os_name, version)
    for os_name in SUPPORTED_OSES
    for version in SUPPORTED_PYTHONS
}


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _job_block(workflow: str, name: str) -> str:
    jobs = workflow.split("\njobs:\n", 1)[1]
    matches = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\n", jobs))
    for index, match in enumerate(matches):
        if match.group(1) != name:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(jobs)
        return jobs[match.start():end]
    raise AssertionError(f"missing workflow job: {name}")


def _include_rows(job: str) -> list[dict[str, str]]:
    lines = job.splitlines()
    try:
        start = lines.index("        include:") + 1
    except ValueError as exc:
        raise AssertionError("job has no matrix include list") from exc

    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines[start:]:
        if line.startswith("          - "):
            if current is not None:
                rows.append(current)
            current = {}
            key, value = line[len("          - "):].split(":", 1)
            current[key] = _unquote(value)
        elif current is not None and line.startswith("            "):
            key, value = line.strip().split(":", 1)
            current[key] = _unquote(value)
        else:
            break
    if current is not None:
        rows.append(current)
    return rows


def _python_versions(job: str) -> set[str]:
    match = re.search(
        r"(?m)^        python-version:\n(?P<items>(?:^          - .+\n?)+)",
        job,
    )
    if not match:
        raise AssertionError("job has no python-version matrix")
    return {
        _unquote(line.split("-", 1)[1])
        for line in match.group("items").splitlines()
    }


def _trigger_branches(workflow: str, event: str) -> list[str]:
    trigger = workflow.split("\njobs:\n", 1)[0]
    match = re.search(
        rf"(?ms)^  {re.escape(event)}:\n(?P<body>.*?)(?=^  [A-Za-z_]+:|\Z)",
        trigger,
    )
    if not match:
        raise AssertionError(f"missing trigger: {event}")
    branches = re.search(
        r"(?m)^    branches:\n(?P<items>(?:^      - .+\n?)+)", match.group("body")
    )
    if not branches:
        raise AssertionError(f"missing branches for trigger: {event}")
    return [
        _unquote(line.split("-", 1)[1])
        for line in branches.group("items").splitlines()
    ]


class ComposerRuntimeCIPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_only_authoritative_composition_push_and_pr_trigger_runtime_ci(self) -> None:
        self.assertEqual(_trigger_branches(self.workflow, "push"), ["composition"])
        self.assertEqual(_trigger_branches(self.workflow, "pull_request"), ["composition"])
        trigger = self.workflow.split("\njobs:\n", 1)[0]
        self.assertNotIn("agent/composition-", trigger)

    def test_pr_clean_and_materialized_tiers_are_representative(self) -> None:
        for name in ("clean-runtime", "materialized-validation"):
            with self.subTest(job=name):
                rows = _include_rows(_job_block(self.workflow, name))
                pairs = {(row["os"], row["python-version"]) for row in rows}
                self.assertEqual(pairs, REPRESENTATIVE_PAIRS)
                self.assertEqual(
                    {version for os_name, version in pairs if os_name == "windows-2022"},
                    {"3.12"},
                )

    def test_authoritative_push_supplements_restore_full_windows_matrix(self) -> None:
        for base_name, supplement_name in (
            ("clean-runtime", "full-windows-clean-runtime"),
            ("materialized-validation", "full-windows-materialized-validation"),
        ):
            with self.subTest(job=supplement_name):
                base_rows = _include_rows(_job_block(self.workflow, base_name))
                base_pairs = {(row["os"], row["python-version"]) for row in base_rows}
                supplement = _job_block(self.workflow, supplement_name)
                self.assertIn("if: ${{ github.event_name == 'push' }}", supplement)
                self.assertIn("runs-on: windows-2022", supplement)
                self.assertNotIn("\n    needs:\n", supplement)
                supplement_pairs = {
                    ("windows-2022", version) for version in _python_versions(supplement)
                }
                self.assertEqual(
                    supplement_pairs,
                    {
                        ("windows-2022", "3.11"),
                        ("windows-2022", "3.13"),
                        ("windows-2022", "3.14"),
                    },
                )
                self.assertEqual(base_pairs | supplement_pairs, FULL_PAIRS)

    def test_representative_jobs_remain_classifier_gated_only_for_prs(self) -> None:
        conditional = (
            "if: ${{ always() && (github.event_name != 'pull_request' || "
            "needs.classify_runtime.outputs.required == 'true') }}"
        )
        for name in ("clean-runtime", "materialized-validation", "skill-runner"):
            with self.subTest(job=name):
                job = _job_block(self.workflow, name)
                self.assertIn("\n    needs:\n      - classify_runtime\n", job)
                self.assertIn(conditional, job)

    def test_windows_skill_runner_remains_in_pr_and_push_baseline(self) -> None:
        job = _job_block(self.workflow, "skill-runner")
        rows = _include_rows(job)
        self.assertEqual({row["os"] for row in rows}, SUPPORTED_OSES)
        self.assertIn('python-version: "3.12"', job)
        self.assertIn("scripts/smoke_test_skill_runner.py", job)
        self.assertIn("scripts/smoke_test_remote_skill_installer.py", job)

    def test_all_runtime_matrices_disable_fail_fast(self) -> None:
        for name in (
            "clean-runtime",
            "materialized-validation",
            "skill-runner",
            "full-windows-clean-runtime",
            "full-windows-materialized-validation",
        ):
            with self.subTest(job=name):
                self.assertIn("\n      fail-fast: false\n", _job_block(self.workflow, name))

    def test_final_validator_propagates_both_tiers_and_skip_semantics(self) -> None:
        validate = _job_block(self.workflow, "validate")
        self.assertIn("name: consumer runtime validate", validate)
        self.assertIn("if: ${{ always() }}", validate)
        for dependency in (
            "classify_runtime",
            "clean-runtime",
            "materialized-validation",
            "skill-runner",
            "full-windows-clean-runtime",
            "full-windows-materialized-validation",
        ):
            self.assertIn(f"      - {dependency}\n", validate)

        for assertion in (
            'test "$CLASSIFIER_RESULT" = skipped',
            'test "$CLEAN_RUNTIME_RESULT" = success',
            'test "$MATERIALIZED_VALIDATION_RESULT" = success',
            'test "$SKILL_RUNNER_RESULT" = success',
            'test "$FULL_WINDOWS_CLEAN_RESULT" = success',
            'test "$FULL_WINDOWS_MATERIALIZED_RESULT" = success',
            'test "$CLASSIFIER_RESULT" = success',
            'test "$FULL_WINDOWS_CLEAN_RESULT" = skipped',
            'test "$FULL_WINDOWS_MATERIALIZED_RESULT" = skipped',
            'test "$CLEAN_RUNTIME_RESULT" = skipped',
            'test "$MATERIALIZED_VALIDATION_RESULT" = skipped',
            'test "$SKILL_RUNNER_RESULT" = skipped',
        ):
            with self.subTest(assertion=assertion):
                self.assertIn(assertion, validate)
        self.assertIn('echo "invalid consumer-runtime classification: $RUNTIME_REQUIRED"', validate)


if __name__ == "__main__":
    unittest.main()
