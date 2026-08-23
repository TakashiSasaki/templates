from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_release_orchestration as orchestration_helpers


class ReleaseOrchestrationCrashTests(unittest.TestCase):
    def test_abrupt_process_exit_leaves_recoverable_transaction(self) -> None:
        helper = orchestration_helpers.ReleaseOrchestrationTests(
            methodName="test_recover_only_restores_digest_verified_preoperation_bytes"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target, revision, original_evidence, original_bundle = helper.materialize(
                root,
                "print('orchestrated proof passed')\n",
            )
            orchestrator = target / ".template-composition/release/produce_release.py"
            worker = root / "release-crash-worker.py"
            worker.write_text(
                "from __future__ import annotations\n"
                "import importlib.util\n"
                "import os\n"
                "import sys\n"
                "from pathlib import Path\n"
                "orchestrator = Path(sys.argv[1])\n"
                "target = Path(sys.argv[2])\n"
                "revision = sys.argv[3]\n"
                "spec = importlib.util.spec_from_file_location('release_crash_worker', orchestrator)\n"
                "if spec is None or spec.loader is None:\n"
                "    raise SystemExit('cannot load release orchestrator')\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "with module.lifecycle_lock.release_lifecycle_lock(target):\n"
                "    git_dir = module.lifecycle_lock._repository_git_directory(target)\n"
                "    module._begin_transaction(target, git_dir, revision)\n"
                "    (target / 'contracts/release-evidence.json').write_bytes(b'crash partial evidence\\n')\n"
                "    (target / 'contracts/release-bundle.json').write_bytes(b'crash partial bundle\\n')\n"
                "    os._exit(77)\n",
                encoding="utf-8",
            )

            crashed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(worker),
                    str(orchestrator),
                    str(target),
                    revision,
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
                env={key: value for key, value in os.environ.items() if not key.startswith("PYTHON")},
            )
            self.assertEqual(crashed.returncode, 77, crashed.stdout + crashed.stderr)
            git_dir = target / ".git"
            self.assertTrue((git_dir / orchestration_helpers.MARKER).is_file())
            self.assertTrue((git_dir / orchestration_helpers.EVIDENCE_BACKUP).is_file())
            self.assertTrue((git_dir / orchestration_helpers.BUNDLE_BACKUP).is_file())
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                b"crash partial evidence\n",
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                b"crash partial bundle\n",
            )

            recovered = helper.run_release(target, recover_only=True)
            self.assertEqual(
                recovered.returncode,
                0,
                recovered.stdout + recovered.stderr,
            )
            self.assertIn("Recovered incomplete release transaction", recovered.stdout)
            self.assertEqual(
                (target / "contracts/release-evidence.json").read_bytes(),
                original_evidence,
            )
            self.assertEqual(
                (target / "contracts/release-bundle.json").read_bytes(),
                original_bundle,
            )
            helper.assert_transaction_state_absent(target)


if __name__ == "__main__":
    unittest.main()
