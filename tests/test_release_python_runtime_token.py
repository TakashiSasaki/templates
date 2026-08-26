from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from test_release_evidence_producer import ReleaseEvidenceProducerTests


class ReleasePythonRuntimeTokenTests(unittest.TestCase):
    def test_python_release_token_uses_producer_interpreter_not_path_lookup(self) -> None:
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
            target, revision, original = helper.materialize_candidate(
                Path(temp_dir), proof_script
            )
            result = helper.run_producer(target, revision)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "managed Python runtime token used producer interpreter",
            result.stdout,
        )
        self.assertNotEqual(original, b"")


if __name__ == "__main__":
    unittest.main()
