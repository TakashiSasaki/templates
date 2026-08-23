"""Cross-platform repository-local serialization for release lifecycle producers."""
from __future__ import annotations

import errno
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path

LOCK_FILENAME = "template-composition-release-lifecycle.lock"


class ReleaseLifecycleLockError(RuntimeError):
    """Raised when the shared release lifecycle lock cannot be used safely."""


def _repository_git_directory(root: Path) -> Path:
    root = root.resolve()
    git_dir = root / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir():
        raise ReleaseLifecycleLockError(
            "repository .git must be a regular directory for release lifecycle locking"
        )
    return git_dir


def _open_lock_file(git_dir: Path) -> int:
    lock_path = git_dir / LOCK_FILENAME
    try:
        existing = os.lstat(lock_path)
    except FileNotFoundError:
        existing = None
    except OSError as exc:
        raise ReleaseLifecycleLockError(
            f"cannot inspect release lifecycle lock: {exc}"
        ) from exc
    if existing is not None and not stat.S_ISREG(existing.st_mode):
        raise ReleaseLifecycleLockError(
            "release lifecycle lock must be a regular non-symbolic file"
        )

    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise ReleaseLifecycleLockError(
            f"cannot open release lifecycle lock: {exc}"
        ) from exc

    try:
        opened = os.fstat(descriptor)
        current = os.stat(lock_path, follow_symlinks=False)
        if not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(current.st_mode):
            raise ReleaseLifecycleLockError(
                "release lifecycle lock must remain a regular non-symbolic file"
            )
        opened_identity = (opened.st_dev, opened.st_ino)
        current_identity = (current.st_dev, current.st_ino)
        if opened_identity != current_identity:
            raise ReleaseLifecycleLockError(
                "release lifecycle lock path changed while it was opened"
            )
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _lock_windows(descriptor: int) -> None:
    import msvcrt

    if os.fstat(descriptor).st_size == 0:
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, b"\0")
        os.fsync(descriptor)
    while True:
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            return
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EDEADLK}:
                raise ReleaseLifecycleLockError(
                    f"cannot acquire release lifecycle lock: {exc}"
                ) from exc
            time.sleep(0.05)


def _unlock_windows(descriptor: int) -> None:
    import msvcrt

    os.lseek(descriptor, 0, os.SEEK_SET)
    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)


def _lock_posix(descriptor: int) -> None:
    import fcntl

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except OSError as exc:
        raise ReleaseLifecycleLockError(
            f"cannot acquire release lifecycle lock: {exc}"
        ) from exc


def _unlock_posix(descriptor: int) -> None:
    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


@contextmanager
def release_lifecycle_lock(root: Path):
    """Serialize one complete release lifecycle producer operation per repository."""

    git_dir = _repository_git_directory(root)
    descriptor = _open_lock_file(git_dir)
    locked = False
    try:
        if os.name == "nt":
            _lock_windows(descriptor)
        else:
            _lock_posix(descriptor)
        locked = True
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    _unlock_windows(descriptor)
                else:
                    _unlock_posix(descriptor)
            except OSError:
                pass
        os.close(descriptor)
