from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "scripts" / "composer_core.py"
SPEC = importlib.util.spec_from_file_location(
    "composition_core_inspect_guard", CORE
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Composition core")
core = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = core
SPEC.loader.exec_module(core)


class CompositionInspectEntrypointGuardTests(unittest.TestCase):
    def test_absent_target_exposes_initial_runner_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            status, payload = core.command_inspect(Path(temp_dir) / "consumer")
        self.assertEqual(status, 0)
        self.assertEqual(payload["state"], "absent")
        guidance = payload["guidance"]
        self.assertEqual(guidance["relevant_mode"], "initial")
        self.assertIn(
            "python scripts/run.py --repository <root>",
            guidance["normal_consumer_entrypoint"],
        )
        self.assertIn("plan --config composition.json", guidance["allowed_next_operations"])

    def test_materialized_files_without_lock_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "consumer"
            metadata = target / ".template-composition"
            metadata.mkdir(parents=True)
            (metadata / "validate.py").write_text("unexpected direct copy", encoding="utf-8")

            status, payload = core.command_inspect(target)

        self.assertEqual(status, 2)
        self.assertEqual(payload["state"], "unmanaged-materialized")
        self.assertEqual(payload["code"], "NOT_A_MANAGED_CONSUMER_ENTRYPOINT")
        self.assertIn("installed Composition skill runner", payload["message"])
        self.assertFalse(payload["guidance"]["recovery_required"])

    def test_interrupted_state_preserves_recovery_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "consumer"
            transaction = target / ".template-composition" / "transaction.json"
            transaction.parent.mkdir(parents=True)
            transaction.write_text("{}", encoding="utf-8")

            status, payload = core.command_inspect(target)

        self.assertEqual(status, 2)
        self.assertEqual(payload["state"], "managed-interrupted")
        self.assertTrue(payload["guidance"]["recovery_required"])
        self.assertIn("apply --mode update", payload["guidance"]["allowed_next_operations"])
        self.assertIn("apply --mode upgrade", payload["guidance"]["allowed_next_operations"])


if __name__ == "__main__":
    unittest.main()
