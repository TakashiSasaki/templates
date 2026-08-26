from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


class ReleasePythonRuntimeTokenTests(unittest.TestCase):
    def test_python_release_token_uses_producer_interpreter_not_path_lookup(self) -> None:
        from test_release_evidence_producer import ReleaseEvidenceProducerTests

        helper = ReleaseEvidenceProducerTests(
            methodName="test_success_produces_revision_bound_valid_evidence"
        )
        expected = sys.executable
        proof_script = (
            "import sys\n"
            f"expected = {expected!r}\n"
            "if sys.executable != expected:\n"
            "    raise SystemExit(23)\n"
            "print('managed Python runtime token used producer interpreter')\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target, revision, _ = helper.materialize_candidate(
                Path(temp_dir), proof_script
            )
            result = helper.run_producer(target, revision)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "managed Python runtime token used producer interpreter",
            result.stdout,
        )

    def test_release_contract_rejects_host_specific_python_executable(self) -> None:
        from test_release_execution_contract import ReleaseExecutionContractTests

        helper = ReleaseExecutionContractTests(
            methodName="test_product_execution_exactly_covers_authoritative_commands"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            target = helper.materialize_webapp(Path(temp_dir))
            helper.write_json(
                target / "contracts/implementation-evidence.json",
                helper.product_implementation(),
            )
            execution = helper.product_execution()
            execution["commands"][0]["argv"][0] = sys.executable
            helper.write_json(
                target / "contracts/release-execution.json",
                execution,
            )
            result = helper.run_validator(target)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("argv must exactly execute declared harness", result.stderr)


if __name__ == "__main__":
    unittest.main()
