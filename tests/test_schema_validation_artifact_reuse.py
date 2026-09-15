from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/schema-validation.yml"


def job_block(workflow: str, name: str) -> str:
    jobs = workflow.split("\njobs:\n", 1)[1]
    matches = list(re.finditer(r"(?m)^  ([A-Za-z0-9_-]+):\n", jobs))
    for index, match in enumerate(matches):
        if match.group(1) != name:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(jobs)
        return jobs[match.start():end]
    raise AssertionError(f"missing workflow job: {name}")


class SchemaValidationArtifactReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_primary_reuses_its_exact_head_publication_qualification(self) -> None:
        primary = job_block(self.workflow, "primary")
        materialize_command = "scripts/materialize_publication.py --source-root ."
        site_contract_command = (
            '"$SITE_PUBLICATION_PROTOCOL_ROOT/scripts/publication_contract.py" --source-root .'
        )
        composition_contract_command = "scripts/validate_publication.py"

        self.assertEqual(primary.count(materialize_command), 1)
        self.assertEqual(primary.count(site_contract_command), 1)
        self.assertEqual(primary.count(composition_contract_command), 1)
        self.assertEqual(primary.count("scripts/run_composition_preflight.py fast"), 1)
        self.assertIn("--validators-only", primary)
        self.assertIn("--publication-already-validated", primary)

    def test_parallel_core_shard_starts_without_a_publication_producer_dependency(self) -> None:
        primary = job_block(self.workflow, "primary")
        parallel = job_block(self.workflow, "parallel")

        self.assertNotIn("\n  publication:\n", self.workflow)
        self.assertNotIn("      - publication\n", primary)
        self.assertNotIn("      - publication\n", parallel)
        self.assertNotIn("actions/upload-artifact@", self.workflow)
        self.assertNotIn("actions/download-artifact@", self.workflow)
        self.assertEqual(
            self.workflow.count("scripts/materialize_publication.py --source-root ."),
            2,
        )
        self.assertEqual(parallel.count("scripts/materialize_publication.py --source-root ."), 1)
        self.assertNotIn("scripts/run_composition_preflight.py", parallel)

    def test_real_browser_is_not_serialized_behind_core_publication_work(self) -> None:
        browser = job_block(self.workflow, "real_browser")
        self.assertIn("      - classify_browser\n", browser)
        self.assertNotIn("      - primary\n", browser)
        self.assertNotIn("      - parallel\n", browser)
        self.assertNotIn("      - publication\n", browser)
        self.assertNotIn("Check out Site publication protocol", browser)
        self.assertNotIn("scripts/materialize_publication.py", browser)

    def test_schema_validation_uses_the_reviewed_python_312_lock_contract(self) -> None:
        self.assertEqual(self.workflow.count('python-version: "3.12"'), 3)
        self.assertNotIn('python-version: "3.11"', self.workflow)
        self.assertNotIn('python-version: "3.13"', self.workflow)
        self.assertNotIn('python-version: "3.14"', self.workflow)
        self.assertNotIn("windows-2022", self.workflow)

    def test_final_gate_requires_parallel_core_jobs_and_browser_policy(self) -> None:
        validate = job_block(self.workflow, "validate")
        for dependency in (
            "classify_browser",
            "primary",
            "parallel",
            "real_browser",
        ):
            self.assertIn(f"      - {dependency}\n", validate)
        self.assertNotIn("publication", validate)
        self.assertIn("PRIMARY_RESULT: ${{ needs.primary.result }}", validate)
        self.assertIn("PARALLEL_RESULT: ${{ needs.parallel.result }}", validate)
        self.assertIn('test "$PRIMARY_RESULT" = success', validate)
        self.assertIn('test "$PARALLEL_RESULT" = success', validate)


if __name__ == "__main__":
    unittest.main()
