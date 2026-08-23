from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_SOURCE = (
    ROOT
    / "components/lifecycle.release-execution/files/.template-composition/release/lifecycle_lock.py"
)
EVIDENCE_PRODUCER = (
    ROOT
    / "components/lifecycle.release-evidence/files/.template-composition/release/produce_release_evidence.py"
)
BUNDLE_PRODUCER = (
    ROOT
    / "components/lifecycle.release-bundle/files/.template-composition/release/produce_release_bundle.py"
)


def load_lock_module():
    spec = importlib.util.spec_from_file_location("release_lifecycle_lock_test", LOCK_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load release lifecycle lock helper")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


lifecycle_lock = load_lock_module()


class ReleaseLifecycleLockTests(unittest.TestCase):
    def wait_for_path(self, path: Path, process: subprocess.Popen[str]) -> None:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if path.exists():
                return
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.fail(
                    f"lock worker exited before creating {path.name}\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}"
                )
            time.sleep(0.02)
        process.kill()
        stdout, stderr = process.communicate()
        self.fail(
            f"timed out waiting for {path.name}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    def test_lock_path_rejects_symbolic_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            git_dir = root / ".git"
            git_dir.mkdir()
            outside = root / "outside.lock"
            outside.write_text("outside\n", encoding="utf-8")
            lock_path = git_dir / lifecycle_lock.LOCK_FILENAME
            try:
                lock_path.symlink_to(outside)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(
                lifecycle_lock.ReleaseLifecycleLockError,
                "regular non-symbolic file",
            ):
                with lifecycle_lock.release_lifecycle_lock(root):
                    self.fail("symlinked lock must never be acquired")

    def test_competing_processes_are_serialized(self) -> None:
        worker_source = """from __future__ import annotations
import importlib.util
import sys
import time
from pathlib import Path

source = Path(sys.argv[1])
root = Path(sys.argv[2])
marker = Path(sys.argv[3])
release = None if sys.argv[4] == '-' else Path(sys.argv[4])
spec = importlib.util.spec_from_file_location('release_lifecycle_lock_worker', source)
if spec is None or spec.loader is None:
    raise SystemExit('cannot load lifecycle lock helper')
module = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(module)
with module.release_lifecycle_lock(root):
    marker.write_text('locked\\n', encoding='utf-8')
    if release is not None:
        while not release.exists():
            time.sleep(0.02)
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            worker = root / "worker.py"
            worker.write_text(worker_source, encoding="utf-8")
            first_marker = root / "first.locked"
            second_marker = root / "second.locked"
            release_first = root / "release-first"

            first = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    str(worker),
                    str(LOCK_SOURCE),
                    str(root),
                    str(first_marker),
                    str(release_first),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.wait_for_path(first_marker, first)

            second = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    str(worker),
                    str(LOCK_SOURCE),
                    str(root),
                    str(second_marker),
                    "-",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.2)
            self.assertFalse(
                second_marker.exists(),
                "second producer entered the lifecycle critical section concurrently",
            )

            release_first.write_text("release\n", encoding="utf-8")
            first_stdout, first_stderr = first.communicate(timeout=5)
            second_stdout, second_stderr = second.communicate(timeout=5)
            self.assertEqual(first.returncode, 0, first_stdout + first_stderr)
            self.assertEqual(second.returncode, 0, second_stdout + second_stderr)
            self.assertTrue(second_marker.is_file())

    def test_both_release_producers_use_the_shared_lock(self) -> None:
        expected = "with lifecycle_lock.release_lifecycle_lock(root):"
        for producer in (EVIDENCE_PRODUCER, BUNDLE_PRODUCER):
            with self.subTest(producer=producer.name):
                text = producer.read_text(encoding="utf-8")
                self.assertIn(expected, text)
                self.assertIn('LIFECYCLE_LOCK_PATH = HERE / "lifecycle_lock.py"', text)


if __name__ == "__main__":
    unittest.main()
