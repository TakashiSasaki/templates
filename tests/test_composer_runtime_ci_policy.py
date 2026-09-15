from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
FAST_WORKFLOW = ROOT / ".github/workflows/composer-runtime.yml"
FULL_WORKFLOW = ROOT / ".github/workflows/composer-full-compatibility.yml"
RUNNER = ROOT / "scripts/run_composer_runtime_checks.py"
SUPPORTED_PYTHONS = {"3.11", "3.12", "3.13", "3.14"}
SUPPORTED_OSES = {"ubuntu-24.04", "windows-2022"}
FULL_PAIRS = {
    (os_name, version)
    for os_name in SUPPORTED_OSES
    for version in SUPPORTED_PYTHONS
}
EXPECTED_SCRIPTS = (
    "smoke_test_runtime_distribution.py",
    "smoke_test_materialized_validation.py",
    "smoke_test_skill_runner.py",
    "smoke_test_remote_skill_installer.py",
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


def _load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("composer_runtime_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load canonical runtime runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ComposerRuntimeCIPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fast_workflow = FAST_WORKFLOW.read_text(encoding="utf-8")
        cls.full_workflow = FULL_WORKFLOW.read_text(encoding="utf-8")
        cls.runner = _load_runner()

    def test_fast_gate_triggers_only_for_authority_push_and_ordinary_pr(self) -> None:
        self.assertEqual(
            _trigger_list(self.fast_workflow, "push", "branches"), ["composition"]
        )
        self.assertEqual(
            _trigger_list(self.fast_workflow, "pull_request", "branches"),
            ["composition", "feat/composition-*"],
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
        self.assertNotIn("ci/full-compatibility", classifier)
        self.assertIn("Record runtime CI selection", classifier)

    def test_fast_tier_is_two_parallel_ubuntu_python_311_jobs(self) -> None:
        conditional = (
            "needs.classify_runtime.result == 'success' && "
            "needs.classify_runtime.outputs.required == 'true'"
        )
        expected_commands = {
            "runtime-core": (
                "python -I scripts/run_composer_runtime_checks.py "
                "--check runtime-core"
            ),
            "skill-runner": (
                "python -I scripts/run_composer_runtime_checks.py "
                "--check skill-runner"
            ),
        }
        for name, command in expected_commands.items():
            with self.subTest(job=name):
                job = _job_block(self.fast_workflow, name)
                self.assertIn("runs-on: ubuntu-24.04", job)
                self.assertIn('python-version: "3.11"', job)
                self.assertIn("PIP_CONFIG_FILE: /dev/null", job)
                self.assertIn(conditional, job)
                self.assertNotIn("\n    strategy:\n", job)
                self.assertNotIn("windows-2022", job)
                for version in ("3.12", "3.13", "3.14"):
                    self.assertNotIn(f'python-version: "{version}"', job)
                self.assertEqual(job.count(command), 1)

        runtime_core = _job_block(self.fast_workflow, "runtime-core")
        skill_runner = _job_block(self.fast_workflow, "skill-runner")
        self.assertNotIn("skill-runner", runtime_core)
        self.assertNotIn("runtime-core", skill_runner.split("run:", 1)[0])

    def test_fast_gate_has_no_compatibility_matrix(self) -> None:
        with self.assertRaisesRegex(AssertionError, "missing workflow job"):
            _job_block(self.fast_workflow, "compatibility-runtime")
        self.assertNotIn("matrix.python-version", self.fast_workflow)
        self.assertNotIn("windows-2022", self.fast_workflow)

    def test_fast_final_validator_propagates_skip_semantics(self) -> None:
        validate = _job_block(self.fast_workflow, "validate")
        self.assertIn("name: consumer runtime validate", validate)
        self.assertIn("if: ${{ always() }}", validate)
        for dependency in ("classify_runtime", "runtime-core", "skill-runner"):
            self.assertIn(f"      - {dependency}\n", validate)
        for assertion in (
            'test "$CLASSIFIER_RESULT" = success',
            'test "$RUNTIME_CORE_RESULT" = success',
            'test "$SKILL_RUNNER_RESULT" = success',
            'test "$RUNTIME_CORE_RESULT" = skipped',
            'test "$SKILL_RUNNER_RESULT" = skipped',
        ):
            with self.subTest(assertion=assertion):
                self.assertIn(assertion, validate)
        self.assertIn(
            'echo "invalid consumer-runtime classification: $RUNTIME_REQUIRED"',
            validate,
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
        self.assertNotIn("schedule:", trigger)
        self.assertNotIn("workflow_dispatch:", trigger)
        self.assertNotIn("synchronize", trigger)

        qualify = _job_block(self.full_workflow, "qualify")
        self.assertIn("github.event_name == 'push'", qualify)
        self.assertIn("github.event.label.name == 'ci/full-compatibility'", qualify)
        self.assertIn("CANDIDATE_SHA: ${{ github.sha }}", qualify)

    def test_full_qualification_is_one_complete_eight_environment_matrix(self) -> None:
        job = _job_block(self.full_workflow, "compatibility-runtime")
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
        self.assertEqual(
            job.count("python -I scripts/run_composer_runtime_checks.py --check all"),
            1,
        )
        for obsolete in (
            "compatibility-clean-runtime",
            "compatibility-materialized-validation",
            "compatibility-skill-runner",
        ):
            with self.assertRaisesRegex(AssertionError, "missing workflow job"):
                _job_block(self.full_workflow, obsolete)

    def test_canonical_runner_covers_every_runtime_surface_once(self) -> None:
        self.assertEqual(self.runner.selected_scripts("all"), EXPECTED_SCRIPTS)
        self.assertEqual(
            self.runner.selected_scripts("runtime-core"),
            (
                "smoke_test_runtime_distribution.py",
                "smoke_test_materialized_validation.py",
            ),
        )
        self.assertEqual(
            self.runner.selected_scripts("clean-runtime"),
            ("smoke_test_runtime_distribution.py",),
        )
        self.assertEqual(
            self.runner.selected_scripts("materialized-validation"),
            ("smoke_test_materialized_validation.py",),
        )
        self.assertEqual(
            self.runner.selected_scripts("skill-runner"),
            (
                "smoke_test_skill_runner.py",
                "smoke_test_remote_skill_installer.py",
            ),
        )
        self.assertIn(
            "scripts/run_composer_runtime_checks.py --check runtime-core",
            self.fast_workflow,
        )
        self.assertIn(
            "scripts/run_composer_runtime_checks.py --check skill-runner",
            self.fast_workflow,
        )
        self.assertIn(
            "scripts/run_composer_runtime_checks.py --check all",
            self.full_workflow,
        )
        for workflow in (self.fast_workflow, self.full_workflow):
            for script in EXPECTED_SCRIPTS:
                self.assertNotIn(f"python -I scripts/{script}", workflow)

    def test_full_final_validator_requires_combined_matrix(self) -> None:
        validate = _job_block(self.full_workflow, "validate")
        self.assertIn("name: full compatibility validate", validate)
        self.assertIn("github.event.label.name == 'ci/full-compatibility'", validate)
        for dependency in ("qualify", "compatibility-runtime"):
            self.assertIn(f"      - {dependency}\n", validate)
        self.assertIn('test "$QUALIFY_RESULT" = success', validate)
        self.assertIn('test "$COMPATIBILITY_RUNTIME_RESULT" = success', validate)


if __name__ == "__main__":
    unittest.main()
