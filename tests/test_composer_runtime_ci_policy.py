from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAST_WORKFLOW = ROOT / ".github/workflows/composer-runtime.yml"
FULL_WORKFLOW = ROOT / ".github/workflows/composer-full-compatibility.yml"
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
        cls.fast_workflow = FAST_WORKFLOW.read_text(encoding="utf-8")
        cls.full_workflow = FULL_WORKFLOW.read_text(encoding="utf-8")

    def test_fast_gate_triggers_only_for_authority_push_and_ordinary_pr(self) -> None:
        self.assertEqual(
            _trigger_list(self.fast_workflow, "push", "branches"), ["composition"]
        )
        self.assertEqual(
            _trigger_list(self.fast_workflow, "pull_request", "branches"),
            ["composition"],
        )
        self.assertEqual(
            set(_trigger_list(self.fast_workflow, "pull_request", "types")),
            {"opened", "synchronize", "reopened"},
        )
        trigger = self.fast_workflow.split("\njobs:\n", 1)[0]
        self.assertNotIn("composition-compatibility-*", trigger)
        self.assertNotIn("labeled", trigger)
        self.assertNotIn("unlabeled", trigger)
        self.assertNotIn("schedule:", trigger)
        self.assertNotIn("workflow_dispatch:", trigger)

    def test_fast_classifier_has_no_full_compatibility_decision(self) -> None:
        classifier = _job_block(self.fast_workflow, "classify_runtime")
        self.assertNotIn("\n    if:", classifier)
        self.assertIn("scripts/classify_composition_ci.py", classifier)
        self.assertIn("required:", classifier)
        self.assertIn("reason:", classifier)
        self.assertIn("changed_count:", classifier)
        self.assertNotIn("compatibility_required", classifier)
        self.assertNotIn("compatibility_reason", classifier)
        self.assertNotIn("ci/full-compatibility", classifier)
        self.assertNotIn("force-compatibility", classifier)
        self.assertIn("Record runtime CI selection", classifier)

    def test_fast_tier_is_exactly_ubuntu_python_312(self) -> None:
        conditional = (
            "needs.classify_runtime.result == 'success' && "
            "needs.classify_runtime.outputs.required == 'true'"
        )
        for name in FAST_JOBS:
            with self.subTest(job=name):
                job = _job_block(self.fast_workflow, name)
                self.assertIn("runs-on: ubuntu-24.04", job)
                self.assertIn('python-version: "3.12"', job)
                self.assertIn("PIP_CONFIG_FILE: /dev/null", job)
                self.assertIn(conditional, job)
                self.assertNotIn("\n    strategy:\n", job)
                self.assertNotIn("windows-2022", job)
                for version in ("3.11", "3.13", "3.14"):
                    self.assertNotIn(f'python-version: "{version}"', job)

    def test_fast_gate_has_no_compatibility_jobs(self) -> None:
        for name in COMPATIBILITY_JOBS:
            with self.subTest(job=name):
                with self.assertRaisesRegex(AssertionError, "missing workflow job"):
                    _job_block(self.fast_workflow, name)
        self.assertNotIn("matrix.python-version", self.fast_workflow)
        self.assertNotIn("windows-2022", self.fast_workflow)

    def test_fast_final_validator_propagates_only_fast_skip_semantics(self) -> None:
        validate = _job_block(self.fast_workflow, "validate")
        self.assertIn("name: consumer runtime validate", validate)
        self.assertIn("if: ${{ always() }}", validate)
        for dependency in ("classify_runtime", *FAST_JOBS):
            self.assertIn(f"      - {dependency}\n", validate)
        for dependency in COMPATIBILITY_JOBS:
            self.assertNotIn(f"      - {dependency}\n", validate)

        for assertion in (
            'test "$CLASSIFIER_RESULT" = success',
            'test "$CLEAN_RUNTIME_RESULT" = success',
            'test "$MATERIALIZED_VALIDATION_RESULT" = success',
            'test "$SKILL_RUNNER_RESULT" = success',
            'test "$CLEAN_RUNTIME_RESULT" = skipped',
            'test "$MATERIALIZED_VALIDATION_RESULT" = skipped',
            'test "$SKILL_RUNNER_RESULT" = skipped',
        ):
            with self.subTest(assertion=assertion):
                self.assertIn(assertion, validate)
        self.assertNotIn("COMPATIBILITY_CLEAN_RESULT", validate)
        self.assertIn(
            'echo "invalid consumer-runtime classification: $RUNTIME_REQUIRED"', validate
        )

    def test_full_qualification_has_only_explicit_checkpoint_triggers(self) -> None:
        self.assertEqual(
            _trigger_list(self.full_workflow, "push", "tags"),
            ["composition-compatibility-*"],
        )
        self.assertEqual(
            _trigger_list(self.full_workflow, "pull_request", "branches"),
            ["composition"],
        )
        self.assertEqual(
            _trigger_list(self.full_workflow, "pull_request", "types"), ["labeled"]
        )
        trigger = self.full_workflow.split("\njobs:\n", 1)[0]
        self.assertNotIn("branches:\n      - composition\n    tags:", trigger)
        self.assertNotIn("schedule:", trigger)
        self.assertNotIn("workflow_dispatch:", trigger)
        self.assertNotIn("synchronize", trigger)

        qualify = _job_block(self.full_workflow, "qualify")
        self.assertIn("github.event_name == 'push'", qualify)
        self.assertIn("github.event.label.name == 'ci/full-compatibility'", qualify)
        self.assertIn("CANDIDATE_SHA: ${{ github.sha }}", qualify)

    def test_full_qualification_is_complete_eight_environment_matrix(self) -> None:
        for name in COMPATIBILITY_JOBS:
            with self.subTest(job=name):
                job = _job_block(self.full_workflow, name)
                rows = _include_rows(job)
                pairs = {(row["os"], row["python-version"]) for row in rows}
                self.assertEqual(pairs, FULL_PAIRS)
                self.assertEqual(len(rows), 8)
                self.assertIn("\n      fail-fast: false\n", job)
                self.assertIn("needs.qualify.result == 'success'", job)
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

    def test_all_runtime_surfaces_exist_in_fast_and_full_workflows(self) -> None:
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
                self.assertIn(script, _job_block(self.fast_workflow, fast_name))
                self.assertIn(script, _job_block(self.full_workflow, compatibility_name))
        self.assertIn(
            "smoke_test_remote_skill_installer.py",
            _job_block(self.fast_workflow, "skill-runner"),
        )
        self.assertIn(
            "smoke_test_remote_skill_installer.py",
            _job_block(self.full_workflow, "compatibility-skill-runner"),
        )

    def test_full_final_validator_requires_every_surface(self) -> None:
        validate = _job_block(self.full_workflow, "validate")
        self.assertIn("name: full compatibility validate", validate)
        self.assertIn("github.event.label.name == 'ci/full-compatibility'", validate)
        for dependency in ("qualify", *COMPATIBILITY_JOBS):
            self.assertIn(f"      - {dependency}\n", validate)
        for assertion in (
            'test "$QUALIFY_RESULT" = success',
            'test "$COMPATIBILITY_CLEAN_RESULT" = success',
            'test "$COMPATIBILITY_MATERIALIZED_RESULT" = success',
            'test "$COMPATIBILITY_SKILL_RESULT" = success',
        ):
            with self.subTest(assertion=assertion):
                self.assertIn(assertion, validate)


if __name__ == "__main__":
    unittest.main()
