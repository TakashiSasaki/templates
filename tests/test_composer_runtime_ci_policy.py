from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/composer-runtime.yml"
SUPPORTED_PYTHONS = {"3.11", "3.12", "3.13", "3.14"}
SUPPORTED_OSES = {"ubuntu-24.04", "windows-2022"}
FULL_PAIRS = {
    (os_name, version)
    for os_name in SUPPORTED_OSES
    for version in SUPPORTED_PYTHONS
}
FAST_JOBS = ("clean-runtime", "materialized-validation", "skill-runner")
COMPATIBILITY_JOBS = (
    "compatibility-clean-runtime",
    "compatibility-materialized-validation",
    "compatibility-skill-runner",
)


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


def _trigger_body(workflow: str, event: str) -> str:
    trigger = workflow.split("\njobs:\n", 1)[0]
    match = re.search(
        rf"(?ms)^  {re.escape(event)}:\n(?P<body>.*?)(?=^  [A-Za-z_]+:|\Z)",
        trigger,
    )
    if not match:
        raise AssertionError(f"missing trigger: {event}")
    return match.group("body")


def _trigger_list(workflow: str, event: str, key: str) -> list[str]:
    body = _trigger_body(workflow, event)
    match = re.search(
        rf"(?m)^    {re.escape(key)}:\n(?P<items>(?:^      - .+\n?)+)", body
    )
    if not match:
        raise AssertionError(f"missing {key} for trigger: {event}")
    return [
        _unquote(line.split("-", 1)[1])
        for line in match.group("items").splitlines()
    ]


class ComposerRuntimeCIPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_authority_and_checkpoint_triggers_are_exact(self) -> None:
        self.assertEqual(_trigger_list(self.workflow, "push", "branches"), ["composition"])
        self.assertEqual(
            _trigger_list(self.workflow, "push", "tags"),
            ["composition-compatibility-*"],
        )
        self.assertEqual(
            _trigger_list(self.workflow, "pull_request", "branches"), ["composition"]
        )
        self.assertEqual(
            set(_trigger_list(self.workflow, "pull_request", "types")),
            {"opened", "synchronize", "reopened", "labeled", "unlabeled"},
        )
        trigger = self.workflow.split("\njobs:\n", 1)[0]
        self.assertNotIn("agent/composition-", trigger)
        self.assertNotIn("schedule:", trigger)
        self.assertNotIn("workflow_dispatch:", trigger)

    def test_classifier_runs_for_pr_push_and_explicit_checkpoints(self) -> None:
        classifier = _job_block(self.workflow, "classify_runtime")
        self.assertNotIn("\n    if:", classifier)
        self.assertIn("scripts/classify_composition_ci.py", classifier)
        self.assertIn("compatibility_required:", classifier)
        self.assertIn("compatibility_reason:", classifier)
        self.assertIn("ci/full-compatibility", classifier)
        self.assertIn("refs/tags/composition-compatibility-", classifier)
        self.assertIn("--force-compatibility", classifier)
        self.assertIn("github.event.before", classifier)

    def test_fast_tier_is_exactly_ubuntu_python_312(self) -> None:
        conditional = (
            "needs.classify_runtime.result == 'success' && "
            "needs.classify_runtime.outputs.required == 'true'"
        )
        for name in FAST_JOBS:
            with self.subTest(job=name):
                job = _job_block(self.workflow, name)
                self.assertIn("runs-on: ubuntu-24.04", job)
                self.assertIn('python-version: "3.12"', job)
                self.assertIn("PIP_CONFIG_FILE: /dev/null", job)
                self.assertIn(conditional, job)
                self.assertNotIn("\n    strategy:\n", job)
                self.assertNotIn("windows-2022", job)
                for version in ("3.11", "3.13", "3.14"):
                    self.assertNotIn(f'python-version: "{version}"', job)

    def test_compatibility_tier_is_full_eight_environment_matrix(self) -> None:
        conditional = (
            "needs.classify_runtime.result == 'success' && "
            "needs.classify_runtime.outputs.compatibility_required == 'true'"
        )
        for name in COMPATIBILITY_JOBS:
            with self.subTest(job=name):
                job = _job_block(self.workflow, name)
                rows = _include_rows(job)
                pairs = {(row["os"], row["python-version"]) for row in rows}
                self.assertEqual(pairs, FULL_PAIRS)
                self.assertEqual(len(rows), 8)
                self.assertIn("\n      fail-fast: false\n", job)
                self.assertIn(conditional, job)
                self.assertEqual(
                    {
                        row["pip-config-file"]
                        for row in rows
                        if row["os"] == "ubuntu-24.04"
                    },
                    {"/dev/null"},
                )
                self.assertEqual(
                    {
                        row["pip-config-file"]
                        for row in rows
                        if row["os"] == "windows-2022"
                    },
                    {"NUL"},
                )

    def test_all_runtime_surfaces_exist_in_both_tiers(self) -> None:
        pairs = (
            ("clean-runtime", "compatibility-clean-runtime", "smoke_test_runtime_distribution.py"),
            (
                "materialized-validation",
                "compatibility-materialized-validation",
                "smoke_test_materialized_validation.py",
            ),
            ("skill-runner", "compatibility-skill-runner", "smoke_test_skill_runner.py"),
        )
        for fast_name, compatibility_name, script in pairs:
            with self.subTest(surface=fast_name):
                self.assertIn(script, _job_block(self.workflow, fast_name))
                self.assertIn(script, _job_block(self.workflow, compatibility_name))
        self.assertIn(
            "smoke_test_remote_skill_installer.py",
            _job_block(self.workflow, "skill-runner"),
        )
        self.assertIn(
            "smoke_test_remote_skill_installer.py",
            _job_block(self.workflow, "compatibility-skill-runner"),
        )

    def test_final_validator_propagates_fast_and_compatibility_skip_semantics(self) -> None:
        validate = _job_block(self.workflow, "validate")
        self.assertIn("name: consumer runtime validate", validate)
        self.assertIn("if: ${{ always() }}", validate)
        for dependency in (
            "classify_runtime",
            *FAST_JOBS,
            *COMPATIBILITY_JOBS,
        ):
            self.assertIn(f"      - {dependency}\n", validate)

        for assertion in (
            'test "$CLASSIFIER_RESULT" = success',
            'test "$CLEAN_RUNTIME_RESULT" = success',
            'test "$MATERIALIZED_VALIDATION_RESULT" = success',
            'test "$SKILL_RUNNER_RESULT" = success',
            'test "$CLEAN_RUNTIME_RESULT" = skipped',
            'test "$MATERIALIZED_VALIDATION_RESULT" = skipped',
            'test "$SKILL_RUNNER_RESULT" = skipped',
            'test "$COMPATIBILITY_CLEAN_RESULT" = success',
            'test "$COMPATIBILITY_MATERIALIZED_RESULT" = success',
            'test "$COMPATIBILITY_SKILL_RESULT" = success',
            'test "$COMPATIBILITY_CLEAN_RESULT" = skipped',
            'test "$COMPATIBILITY_MATERIALIZED_RESULT" = skipped',
            'test "$COMPATIBILITY_SKILL_RESULT" = skipped',
        ):
            with self.subTest(assertion=assertion):
                self.assertIn(assertion, validate)
        self.assertIn(
            'echo "invalid consumer-runtime classification: $RUNTIME_REQUIRED"', validate
        )
        self.assertIn(
            'echo "invalid compatibility classification: $COMPATIBILITY_REQUIRED"',
            validate,
        )


if __name__ == "__main__":
    unittest.main()
