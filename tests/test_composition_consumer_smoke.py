from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_composition_consumer_smoke.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("composition_consumer_smoke", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompositionConsumerSmokeTests(unittest.TestCase):
    def test_bytecode_suppression_reaches_selected_test_subprocesses(self) -> None:
        smoke = load_smoke_module()
        with mock.patch.dict(smoke.os.environ, {}, clear=True), tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "probe.py"
            probe.write_text("import sys\nraise SystemExit(not sys.dont_write_bytecode)\n")
            smoke.configure_validation_environment()
            result = subprocess.run([sys.executable, str(probe)], check=False)

        self.assertEqual(result.returncode, 0)
