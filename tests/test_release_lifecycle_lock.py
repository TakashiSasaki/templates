from __future__ import annotations

import errno
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

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

    def test_repository_git_directory_preconditions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_root = Path(temp_dir) / "missing"
            missing_root.mkdir()
            with self.assertRaisesRegex(
                lifecycle_lock.ReleaseLifecycleLockError,
                "repository \\.git must be a regular directory",
            ):
                with lifecycle_lock.release_lifecycle_lock(missing_root):
                    self.fail("missing .git must never acquire the lifecycle lock")

            file_root = Path(temp_dir) / "file"
            file_root.mkdir()
            (file_root / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
            with self.assertRaisesRegex(
                lifecycle_lock.ReleaseLifecycleLockError,
                "repository \\.git must be a regular directory",
            ):
                with lifecycle_lock.release_lifecycle_lock(file_root):
                    self.fail("file .git must never acquire the lifecycle lock")

            symlink_root = Path(temp_dir) / "symlink"
            symlink_root.mkdir()
            real_git = Path(temp_dir) / "real-git"
            real_git.mkdir()
            try:
                (symlink_root / ".git").symlink_to(real_git, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(
                lifecycle_lock.ReleaseLifecycleLockError,
                "repository \\.git must be a regular directory",
            ):
                with lifecycle_lock.release_lifecycle_lock(symlink_root):
                    self.fail("symlinked .git must never acquire the lifecycle lock")

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

    def test_post_open_path_verification_errors_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()
            real_stat = lifecycle_lock.os.stat

            def fail_lock_stat(path, *args, **kwargs):
                if Path(path).name == lifecycle_lock.LOCK_FILENAME:
                    raise PermissionError(errno.EACCES, "simulated lock path denial")
                return real_stat(path, *args, **kwargs)

            with mock.patch.object(
                lifecycle_lock.os,
                "stat",
                side_effect=fail_lock_stat,
            ):
                with self.assertRaisesRegex(
                    lifecycle_lock.ReleaseLifecycleLockError,
                    "cannot verify release lifecycle lock path",
                ):
                    lifecycle_lock._open_lock_file(git_dir)

    def test_windows_lock_retries_without_writing_a_sentinel_byte(self) -> None:
        fake_msvcrt = types.ModuleType("msvcrt")
        fake_msvcrt.LK_NBLCK = 1
        fake_msvcrt.LK_UNLCK = 2
        calls: list[tuple[int, int, int]] = []

        def fake_locking(descriptor: int, mode: int, nbytes: int) -> None:
            calls.append((descriptor, mode, nbytes))
            if len(calls) == 1:
                raise OSError(errno.EACCES, "simulated contention")

        fake_msvcrt.locking = fake_locking
        previous_msvcrt = sys.modules.get("msvcrt")
        sys.modules["msvcrt"] = fake_msvcrt
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                lock_path = Path(temp_dir) / "lock"
                descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
                try:
                    self.assertEqual(os.fstat(descriptor).st_size, 0)
                    with mock.patch.object(lifecycle_lock.time, "sleep", return_value=None):
                        lifecycle_lock._lock_windows(descriptor)
                    self.assertEqual(os.fstat(descriptor).st_size, 0)
                    self.assertEqual(len(calls), 2)
                    self.assertEqual(
                        [(mode, nbytes) for _, mode, nbytes in calls],
                        [(fake_msvcrt.LK_NBLCK, 1), (fake_msvcrt.LK_NBLCK, 1)],
                    )
                finally:
                    os.close(descriptor)
        finally:
            if previous_msvcrt is None:
                del sys.modules["msvcrt"]
            else:
                sys.modules["msvcrt"] = previous_msvcrt

    def test_competing_processes_are_serialized(self) -> None:
        worker_source = """from __future__ import annotations
import importlib.util
import sys
import time
from pathlib import Path

source = Path(sys.argv[1])
root = Path(sys.argv[2])
ready = Path(sys.argv[3])
acquired = Path(sys.argv[4])
release = None if sys.argv[5] == '-' else Path(sys.argv[5])
spec = importlib.util.spec_from_file_location('release_lifecycle_lock_worker', source)
if spec is None or spec.loader is None:
    raise SystemExit('cannot load lifecycle lock helper')
module = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(module)
ready.write_text('ready\\n', encoding='utf-8')
with module.release_lifecycle_lock(root):
    acquired.write_text('locked\\n', encoding='utf-8')
    if release is not None:
        while not release.exists():
            time.sleep(0.02)
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            worker = root / "worker.py"
            worker.write_text(worker_source, encoding="utf-8")
            first_ready = root / "first.ready"
            first_acquired = root / "first.locked"
            second_ready = root / "second.ready"
            second_acquired = root / "second.locked"
            release_first = root / "release-first"

            first: subprocess.Popen[str] | None = None
            second: subprocess.Popen[str] | None = None
            try:
                first = subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        str(worker),
                        str(LOCK_SOURCE),
                        str(root),
                        str(first_ready),
                        str(first_acquired),
                        str(release_first),
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.wait_for_path(first_ready, first)
                self.wait_for_path(first_acquired, first)

                second = subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        str(worker),
                        str(LOCK_SOURCE),
                        str(root),
                        str(second_ready),
                        str(second_acquired),
                        "-",
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.wait_for_path(second_ready, second)
                time.sleep(0.05)
                self.assertFalse(
                    second_acquired.exists(),
                    "second producer entered the lifecycle critical section concurrently",
                )

                release_first.write_text("release\n", encoding="utf-8")
                first_stdout, first_stderr = first.communicate(timeout=5)
                second_stdout, second_stderr = second.communicate(timeout=5)
                self.assertEqual(first.returncode, 0, first_stdout + first_stderr)
                self.assertEqual(second.returncode, 0, second_stdout + second_stderr)
                self.assertTrue(second_acquired.is_file())
            finally:
                for process in (first, second):
                    if process is not None and process.poll() is None:
                        process.kill()
                        process.communicate()

    def test_both_release_producers_use_the_shared_lock(self) -> None:
        expected = "with lifecycle_lock.release_lifecycle_lock(root):"
        for producer in (EVIDENCE_PRODUCER, BUNDLE_PRODUCER):
            with self.subTest(producer=producer.name):
                text = producer.read_text(encoding="utf-8")
                self.assertIn(expected, text)
                self.assertIn('LIFECYCLE_LOCK_PATH = HERE / "lifecycle_lock.py"', text)


if __name__ == "__main__":
    unittest.main()
