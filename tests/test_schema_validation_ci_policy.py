from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _trigger_events(workflow: str) -> list[str]:
    trigger = workflow.split("\njobs:\n", 1)[0]
    try:
        on_block = trigger.split("\non:\n", 1)[1]
    except IndexError as exc:
        raise AssertionError("workflow has no on block") from exc
    return re.findall(r"(?m)^  ([A-Za-z_]+):\s*$", on_block)


def _trigger_branches(workflow: str, event: str) -> list[str]:
    trigger = workflow.split("\njobs:\n", 1)[0]
    match = re.search(
        rf"(?ms)^  {re.escape(event)}:\n(?P<body>.*?)(?=^  [A-Za-z_]+:|\Z)",
        trigger,
    )
    if not match:
        raise AssertionError(f"missing trigger: {event}")
    branches = re.search(
        r"(?m)^    branches:\n(?P<items>(?:^      - .+\n?)+)",
        match.group("body"),
    )
    if not branches:
        raise AssertionError(f"missing branches for trigger: {event}")
    return [
        _unquote(line.split("-", 1)[1])
        for line in branches.group("items").splitlines()
    ]


def _job_block(workflow: str, name: str) -> str:
    jobs = workflow.split("\njobs:\n", 1)[1]
    matches = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\n", jobs))
    for index, match in enumerate(matches):
        if match.group(1) != name:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(jobs)
        return jobs[match.start():end]
    raise AssertionError(f"missing workflow job: {name}")


class SchemaValidationCIPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_schema_validation_uses_pr_and_authoritative_push_tiers_only(self) -> None:
        self.assertEqual(_trigger_events(self.workflow), ["push", "pull_request"])
        self.assertEqual(_trigger_branches(self.workflow, "push"), ["composition"])
        self.assertEqual(
            _trigger_branches(self.workflow, "pull_request"),
            ["composition", "feat/composition-*", "feat/workspace-*"],
        )
        trigger = self.workflow.split("\njobs:\n", 1)[0]
        self.assertNotIn("agent/composition-", trigger)

    def test_schema_validation_reuses_canonical_validator_preflight(self) -> None:
        primary = _job_block(self.workflow, "primary")
        self.assertEqual(primary.count("scripts/run_composition_preflight.py fast"), 1)
        self.assertIn("--validators-only", primary)
        self.assertIn("--publication-already-validated", primary)
        self.assertEqual(primary.count("scripts/validate_publication.py"), 1)
        for duplicate in (
            "scripts/validate_translations.py",
            "scripts/validate_component_versions.py",
            "scripts/verify_composition_skill_installer_release.py",
            "scripts/run_unittest_shard.py --suite core --shard-count 2 --verify-only",
        ):
            self.assertNotIn(duplicate, primary)

    def test_core_jobs_remain_parallel_instead_of_waiting_for_a_producer(self) -> None:
        primary = _job_block(self.workflow, "primary")
        parallel = _job_block(self.workflow, "parallel")
        self.assertNotIn("needs:\n", primary)
        self.assertNotIn("needs:\n", parallel)
        self.assertNotIn("\n  publication:\n", self.workflow)
        self.assertNotIn("actions/upload-artifact@", self.workflow)
        self.assertNotIn("actions/download-artifact@", self.workflow)

    def test_phase_zero_source_precedes_expensive_core_work_in_each_shard(self) -> None:
        for name in ("primary", "parallel"):
            with self.subTest(job=name):
                job = _job_block(self.workflow, name)
                self.assertIn("scripts/composition_phase_zero.py", job)
                self.assertLess(
                    job.index("scripts/composition_phase_zero.py"),
                    job.index("scripts/materialize_publication.py --source-root ."),
                )

    def test_primary_schema_ci_executes_the_fast_real_consumer_spine(self) -> None:
        primary = _job_block(self.workflow, "primary")
        spine = "scripts/run_composition_consumer_smoke.py"
        self.assertEqual(primary.count(spine), 1)
        self.assertLess(
            primary.index(spine),
            primary.index("scripts/run_unittest_shard.py"),
        )

    def test_execution_jobs_are_bound_to_the_exact_pull_request_head(self) -> None:
        checkout_ref = "ref: ${{ github.event.pull_request.head.sha || github.sha }}"
        for job_name in (
            "classify_browser",
            "primary",
            "parallel",
            "real_browser",
        ):
            with self.subTest(job=job_name):
                self.assertIn(checkout_ref, _job_block(self.workflow, job_name))

    def test_integration_protocol_checkout_is_limited_to_core_jobs_that_need_it(self) -> None:
        integration_protocol_ref = "ref: a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d"
        for job_name in ("primary", "parallel"):
            with self.subTest(job=job_name):
                job = _job_block(self.workflow, job_name)
                self.assertIn(integration_protocol_ref, job)
                self.assertIn("Check out Integration publication protocol", job)
        browser = _job_block(self.workflow, "real_browser")
        self.assertNotIn(integration_protocol_ref, browser)
        self.assertNotIn("Check out Integration publication protocol", browser)


if __name__ == "__main__":
    unittest.main()
