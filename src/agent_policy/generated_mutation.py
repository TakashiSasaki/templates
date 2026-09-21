"""Fail-closed mutations for generated repository files.

The renderer must not validate a public pathname and then use that pathname
later as if it still referred to the object that was validated.  This module
keeps the public directory descriptors open, prepares replacements in a
private namespace, and uses Linux's atomic no-replace rename as the binding
operation.  A target is detached and checked before an existing generated
file is replaced or removed.  If the binding cannot be established, the
operation stops and never overwrites the competing object.

This deliberately has no path-based fallback.  The repository's supported
rendering environments must provide descriptor-relative operations and
``renameat2(RENAME_NOREPLACE)``; other environments receive a clear error.
The design follows the mutation-boundary invariant already implemented by the
maintain-progressive-discovery Skill, while keeping the renderer's regular
file contract separate from that Skill's directory-specific implementation.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import os
import secrets
import stat
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_RENAME_NOREPLACE = 1
_AT_REMOVEDIR = 0x200
_HOLDING_MARKER = ".agent-policy-mutation-owner"
_HOLDING_MARKER_CONTENT = b"agent-policy generated mutation owner\n"

# This is intentionally structured data rather than a prose inventory.  The
# renderer boundary test asserts that the command delegates every destructive
# generated-state operation to one of these responsibilities.
MUTATION_INVENTORY = (
    {
        "operation": "generated-create",
        "primitive": "_native_rename_noreplace",
        "boundary": "public-install",
    },
    {
        "operation": "generated-replace",
        "primitive": "_native_rename_noreplace",
        "boundary": "public-detach-and-install",
    },
    {
        "operation": "obsolete-delete",
        "primitive": "_delete_private",
        "boundary": "private-detach-and-unlink",
    },
    {
        "operation": "rollback-restore",
        "primitive": "_restore_private",
        "boundary": "public-no-clobber-restore",
    },
    {
        "operation": "rollback-remove",
        "primitive": "_delete_private",
        "boundary": "owned-public-detach-and-unlink",
    },
    {
        "operation": "rollback-directory-remove",
        "primitive": "_remove_created_directory",
        "boundary": "created-directory-detach-and-rmdir",
    },
    {
        "operation": "lock-update",
        "primitive": "_write",
        "boundary": "lock-public-detach-and-install",
    },
    {
        "operation": "operation-private-cleanup",
        "primitive": "_close_holding",
        "boundary": "holding-namespace-cleanup",
    },
)


class MutationSafetyError(RuntimeError):
    """The requested mutation could not be safely bound or rolled back."""


@dataclass(frozen=True)
class WriteSpec:
    """A complete replacement and its existing-object ownership predicate."""

    content: bytes
    owns_existing: Callable[[bytes], bool]


@dataclass(frozen=True)
class DeleteSpec:
    """The exact generated object that may be removed."""

    expected: bytes
    owns_existing: Callable[[bytes], bool]


@dataclass
class _Binding:
    relative: str
    parent_fd: int
    name: str
    exists: bool
    identity: tuple[int, int] | None
    mode: int | None
    content: bytes | None
    owns_existing: Callable[[bytes], bool]


@dataclass
class _Record:
    action: str
    binding: _Binding
    current_identity: tuple[int, int] | None
    old_name: str | None = None
    old_identity: tuple[int, int] | None = None
    current_content: bytes | None = None


def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)


def _require_supported_operations() -> None:
    required = (os.open, os.mkdir, os.unlink, os.rmdir)
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise MutationSafetyError(
            "safe generated mutations unavailable: descriptor flags are missing"
        )
    if any(operation not in os.supports_dir_fd for operation in required):
        raise MutationSafetyError(
            "safe generated mutations unavailable: descriptor-relative operations "
            "are missing"
        )
    if getattr(_libc(), "renameat2", None) is None:
        raise MutationSafetyError(
            "safe generated mutations unavailable: atomic no-replace rename is missing"
        )


def _native_rename_noreplace(
    source_fd: int, source: str, destination_fd: int, destination: str
) -> None:
    """Move a name without replacing the destination name."""

    renameat2 = _libc().renameat2
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if renameat2(
        source_fd,
        os.fsencode(source),
        destination_fd,
        os.fsencode(destination),
        _RENAME_NOREPLACE,
    ):
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def _native_unlink(parent_fd: int, name: str, flags: int = 0) -> None:
    unlinkat = _libc().unlinkat
    unlinkat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    unlinkat.restype = ctypes.c_int
    if unlinkat(parent_fd, os.fsencode(name), flags):
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def _read_fd(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(fd, 65536):
        chunks.append(chunk)
    return b"".join(chunks)


def _write_fd(fd: int, content: bytes) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    remaining = memoryview(content)
    while remaining:
        count = os.write(fd, remaining)
        if not count:
            raise OSError("short write while preparing generated output")
        remaining = remaining[count:]
    os.ftruncate(fd, len(content))


def _identity(result: os.stat_result) -> tuple[int, int]:
    return result.st_dev, result.st_ino


def _new_name(prefix: str) -> str:
    return f".{prefix}-{secrets.token_hex(16)}"


def _relative_parts(relative: str) -> tuple[str, ...]:
    parsed = PurePosixPath(relative)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise MutationSafetyError(f"generated mutation path is not relative: {relative}")
    if not parsed.parts:
        raise MutationSafetyError("generated mutation path is empty")
    return parsed.parts


class _Transaction:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.stack = ExitStack()
        self.root_fd: int | None = None
        self.holding_fd: int | None = None
        self.holding_name: str | None = None
        self.holding_identity: tuple[int, int] | None = None
        self.records: list[_Record] = []
        self.created_directories: list[tuple[int, str, tuple[int, int]]] = []
        self.retained = False
        self.aliases: dict[str, str] = {}

    def __enter__(self) -> _Transaction:
        _require_supported_operations()
        self.stack.__enter__()
        try:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            self.root_fd = os.open(self.root, flags)
            self.stack.callback(os.close, self.root_fd)
            try:
                fcntl.flock(self.root_fd, fcntl.LOCK_EX)
            except OSError as exc:
                raise MutationSafetyError(
                    "safe generated mutations unavailable: repository lock failed"
                ) from exc
            self.stack.callback(fcntl.flock, self.root_fd, fcntl.LOCK_UN)
            self._make_holding()
            return self
        except Exception:
            self.stack.__exit__(*__import__("sys").exc_info())
            raise

    def __exit__(self, exc_type, exc, traceback) -> bool:
        try:
            self._close_holding(not self.retained)
        finally:
            self.stack.__exit__(exc_type, exc, traceback)
        return False

    def _make_holding(self) -> None:
        assert self.root_fd is not None
        for _ in range(10):
            name = _new_name("agent-policy-mutation")
            try:
                os.mkdir(name, 0o700, dir_fd=self.root_fd)
            except FileExistsError:
                continue
            try:
                fd = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=self.root_fd,
                )
                result = os.fstat(fd)
                if not stat.S_ISDIR(result.st_mode):
                    raise OSError("mutation holding object is not a directory")
                marker_fd = os.open(
                    _HOLDING_MARKER,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=fd,
                )
                try:
                    _write_fd(marker_fd, _HOLDING_MARKER_CONTENT)
                finally:
                    os.close(marker_fd)
            except Exception as exc:
                # The name was created by this operation, but it is not safe
                # to remove it after a failed identity binding. Leave it for
                # the diagnostic path rather than risk a pathname deletion.
                raise MutationSafetyError(
                    f"mutation holding namespace could not be identity-bound: {name}"
                ) from exc
            self.holding_name = name
            self.holding_fd = fd
            self.holding_identity = _identity(result)
            return
        raise MutationSafetyError("could not allocate an operation-private mutation namespace")

    def _open_parent(self, relative: str) -> tuple[int, str]:
        assert self.root_fd is not None
        parts = _relative_parts(relative)
        parent_fd = self.root_fd
        for component in parts[:-1]:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            try:
                child_fd = os.open(component, flags, dir_fd=parent_fd)
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o755, dir_fd=parent_fd)
                except FileExistsError:
                    pass
                child_fd = os.open(component, flags, dir_fd=parent_fd)
                child_result = os.fstat(child_fd)
                self.created_directories.append(
                    (parent_fd, component, _identity(child_result))
                )
            self.stack.callback(os.close, child_fd)
            parent_fd = child_fd
        return parent_fd, parts[-1]

    def _bind(
        self,
        relative: str,
        owns_existing: Callable[[bytes], bool],
    ) -> _Binding:
        parent_fd, name = self._open_parent(relative)
        try:
            fd = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=parent_fd,
            )
        except FileNotFoundError:
            return _Binding(relative, parent_fd, name, False, None, None, None, owns_existing)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise MutationSafetyError(
                    f"refusing to mutate symlinked generated target: {relative}"
                ) from exc
            raise
        try:
            result = os.fstat(fd)
            if not stat.S_ISREG(result.st_mode) or result.st_nlink != 1:
                raise MutationSafetyError(
                    f"generated target is not an exclusively owned regular file: {relative}"
                )
            content = _read_fd(fd)
        finally:
            os.close(fd)
        if not owns_existing(content):
            raise MutationSafetyError(
                f"refusing to overwrite non-generated file: {relative}"
            )
        return _Binding(
            relative,
            parent_fd,
            name,
            True,
            _identity(result),
            stat.S_IMODE(result.st_mode),
            content,
            owns_existing,
        )

    def _check_aliases(self) -> None:
        for actual, lexical in self.aliases.items():
            lexical_path = self.root / lexical
            actual_path = self.root / actual
            if (
                not lexical_path.is_symlink()
                or lexical_path.resolve(strict=False) != actual_path
            ):
                raise MutationSafetyError(
                    f"generated output symlink changed during render: {lexical}"
                )

    def _prepare(self, content: bytes, mode: int | None) -> tuple[str, tuple[int, int]]:
        assert self.holding_fd is not None
        for _ in range(10):
            name = _new_name("prepared")
            try:
                fd = os.open(
                    name,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=self.holding_fd,
                )
            except FileExistsError:
                continue
            try:
                _write_fd(fd, content)
                if mode is not None:
                    os.fchmod(fd, mode)
                result = os.fstat(fd)
                return name, _identity(result)
            finally:
                os.close(fd)
        raise MutationSafetyError("could not allocate an operation-private prepared file")

    def _open_private(self, name: str) -> tuple[int, os.stat_result]:
        assert self.holding_fd is not None
        fd = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=self.holding_fd,
        )
        return fd, os.fstat(fd)

    def _restore_private(self, name: str, binding: _Binding) -> None:
        assert self.holding_fd is not None
        try:
            _native_rename_noreplace(self.holding_fd, name, binding.parent_fd, binding.name)
        except FileExistsError as exc:
            raise MutationSafetyError(
                f"concurrent replacement retained at {binding.relative}; "
                f"operation-private state retained: {name}"
            ) from exc

    def _detach_public(self, binding: _Binding, name: str) -> tuple[int, int]:
        assert self.holding_fd is not None
        _native_rename_noreplace(
            binding.parent_fd,
            binding.name,
            self.holding_fd,
            name,
        )
        fd, result = self._open_private(name)
        try:
            if not stat.S_ISREG(result.st_mode) or result.st_nlink != 1:
                raise MutationSafetyError(
                    f"target kind changed at mutation boundary: {binding.relative}"
                )
            return _identity(result)
        finally:
            os.close(fd)

    def _check_private(
        self,
        name: str,
        expected_identity: tuple[int, int],
        expected_content: bytes,
        owns_existing: Callable[[bytes], bool],
        relative: str,
    ) -> None:
        fd, result = self._open_private(name)
        try:
            if (
                _identity(result) != expected_identity
                or not stat.S_ISREG(result.st_mode)
                or result.st_nlink != 1
            ):
                raise MutationSafetyError(
                    f"target identity changed at mutation boundary: {relative}"
                )
            content = _read_fd(fd)
        finally:
            os.close(fd)
        if content != expected_content or not owns_existing(content):
            raise MutationSafetyError(
                f"target content or ownership changed at mutation boundary: {relative}"
            )

    def _delete_private(
        self,
        name: str,
        expected_identity: tuple[int, int],
        relative: str,
        expected_content: bytes | None = None,
    ) -> None:
        """Delete a file only after detaching a final operation-owned name."""

        assert self.holding_fd is not None
        bound_name = _new_name("bound-delete")
        _native_rename_noreplace(self.holding_fd, name, self.holding_fd, bound_name)
        try:
            fd, result = self._open_private(bound_name)
            try:
                if (
                    _identity(result) != expected_identity
                    or not stat.S_ISREG(result.st_mode)
                    or result.st_nlink != 1
                ):
                    raise MutationSafetyError(
                        f"operation-private target changed before deletion: {relative}"
                    )
                if expected_content is not None and _read_fd(fd) != expected_content:
                    raise MutationSafetyError(
                        f"operation-private content changed before deletion: {relative}"
                    )
            finally:
                os.close(fd)
            _native_unlink(self.holding_fd, bound_name)
        except Exception:
            self.retained = True
            raise

    def _install_new(
        self,
        binding: _Binding,
        prepared_name: str,
        expected_identity: tuple[int, int],
        expected_content: bytes,
    ) -> None:
        assert self.holding_fd is not None
        _native_rename_noreplace(
            self.holding_fd,
            prepared_name,
            binding.parent_fd,
            binding.name,
        )
        fd = os.open(
            binding.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=binding.parent_fd,
        )
        try:
            result = os.fstat(fd)
            if _identity(result) != expected_identity or _read_fd(fd) != expected_content:
                raise MutationSafetyError(
                    f"installed target identity changed: {binding.relative}"
                )
        finally:
            os.close(fd)

    def _write(self, binding: _Binding, spec: WriteSpec) -> _Record:
        assert self.holding_fd is not None
        prepared_name, prepared_identity = self._prepare(spec.content, binding.mode)
        if not binding.exists:
            try:
                self._install_new(
                    binding, prepared_name, prepared_identity, spec.content
                )
            except Exception as exc:
                try:
                    if self._private_exists(prepared_name):
                        self._delete_private(
                            prepared_name,
                            prepared_identity,
                            binding.relative,
                            spec.content,
                        )
                except Exception as cleanup_error:
                    self.retained = True
                    raise MutationSafetyError(
                        f"{exc}; prepared state retained for {binding.relative}: "
                        f"{cleanup_error}"
                    ) from exc
                raise MutationSafetyError(
                    f"target was created concurrently; refusing to overwrite: "
                    f"{binding.relative}"
                ) from exc
            return _Record(
                "create",
                binding,
                prepared_identity,
                current_content=spec.content,
            )

        old_name = _new_name("old")
        try:
            old_identity = self._detach_public(binding, old_name)
            self._check_private(
                old_name,
                binding.identity or (-1, -1),
                binding.content or b"",
                binding.owns_existing,
                binding.relative,
            )
            self._install_new(
                binding, prepared_name, prepared_identity, spec.content
            )
            return _Record(
                "replace",
                binding,
                prepared_identity,
                old_name,
                old_identity,
                spec.content,
            )
        except Exception as exc:
            # A failed detach leaves the public name untouched.  If detach
            # succeeded, restore only through no-replace rename; a competing
            # creator therefore cannot be overwritten during recovery.
            try:
                if self._private_exists(old_name):
                    self._restore_private(old_name, binding)
                if self._private_exists(prepared_name):
                    self._delete_private(
                        prepared_name,
                        prepared_identity,
                        binding.relative,
                        spec.content,
                    )
            except Exception as restore_error:
                self.retained = True
                raise MutationSafetyError(
                    f"{exc}; operation-private state retained for {binding.relative}: "
                    f"{restore_error}"
                ) from exc
            raise

    def _private_exists(self, name: str) -> bool:
        assert self.holding_fd is not None
        try:
            os.stat(name, dir_fd=self.holding_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True

    def _delete(self, binding: _Binding, spec: DeleteSpec) -> _Record:
        assert binding.exists and binding.identity is not None
        old_name = _new_name("obsolete")
        try:
            old_identity = self._detach_public(binding, old_name)
            self._check_private(
                old_name,
                binding.identity,
                spec.expected,
                spec.owns_existing,
                binding.relative,
            )
            return _Record("delete", binding, None, old_name, old_identity)
        except Exception as exc:
            try:
                if self._private_exists(old_name):
                    self._restore_private(old_name, binding)
            except Exception as restore_error:
                self.retained = True
                raise MutationSafetyError(
                    f"{exc}; operation-private state retained for {binding.relative}: "
                    f"{restore_error}"
                ) from exc
            raise

    def _detach_owned_public(self, record: _Record) -> str:
        assert record.current_identity is not None
        detached = _new_name("rollback")
        identity = self._detach_public(record.binding, detached)
        content_matches = True
        if record.current_content is not None:
            fd, _result = self._open_private(detached)
            try:
                content_matches = _read_fd(fd) == record.current_content
            finally:
                os.close(fd)
        if identity != record.current_identity or not content_matches:
            try:
                self._restore_private(detached, record.binding)
            except Exception:
                self.retained = True
            raise MutationSafetyError(
                f"concurrent state retained during rollback: {record.binding.relative}"
            )
        return detached

    def _rollback_record(self, record: _Record) -> None:
        if record.action == "create":
            detached = self._detach_owned_public(record)
            self._delete_private(
                detached,
                record.current_identity or (-1, -1),
                record.binding.relative,
                record.current_content,
            )
            return
        if record.action == "replace":
            detached = self._detach_owned_public(record)
            assert record.old_name is not None
            self._restore_private(record.old_name, record.binding)
            self._delete_private(
                detached,
                record.current_identity or (-1, -1),
                record.binding.relative,
                record.current_content,
            )
            return
        assert record.action == "delete"
        assert record.old_name is not None
        self._restore_private(record.old_name, record.binding)

    def _remove_created_directory(
        self,
        parent_fd: int,
        name: str,
        expected: tuple[int, int],
    ) -> None:
        assert self.holding_fd is not None
        detached = _new_name("rollback-directory")
        _native_rename_noreplace(parent_fd, name, self.holding_fd, detached)
        try:
            fd, result = self._open_private(detached)
            try:
                if _identity(result) != expected or not stat.S_ISDIR(result.st_mode):
                    raise MutationSafetyError(
                        "concurrent directory state retained during rollback"
                    )
            finally:
                os.close(fd)
            _native_unlink(self.holding_fd, detached, _AT_REMOVEDIR)
        except Exception:
            try:
                if self._private_exists(detached):
                    _native_rename_noreplace(self.holding_fd, detached, parent_fd, name)
            except Exception:
                self.retained = True
            raise

    def _remove_created_directories(self) -> None:
        for parent_fd, name, expected in reversed(self.created_directories):
            try:
                self._remove_created_directory(parent_fd, name, expected)
            except FileNotFoundError:
                continue
            except (OSError, MutationSafetyError):
                self.retained = True

    def _close_holding(self, remove: bool) -> None:
        if self.holding_fd is None or self.holding_name is None:
            return
        try:
            if remove and not self.retained:
                try:
                    _native_unlink(self.holding_fd, _HOLDING_MARKER)
                except FileNotFoundError:
                    pass
                holding_fd = self.holding_fd
                self.holding_fd = None
                os.close(holding_fd)
                cleanup_name = _new_name("mutation-cleanup")
                assert self.root_fd is not None
                _native_rename_noreplace(
                    self.root_fd,
                    self.holding_name,
                    self.root_fd,
                    cleanup_name,
                )
                fd = os.open(
                    cleanup_name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=self.root_fd,
                )
                try:
                    result = os.fstat(fd)
                    if _identity(result) != self.holding_identity:
                        raise MutationSafetyError(
                            "mutation holding namespace changed during cleanup"
                        )
                    _native_unlink(self.root_fd, cleanup_name, _AT_REMOVEDIR)
                finally:
                    os.close(fd)
            else:
                self.retained = True
        finally:
            if self.holding_fd is not None:
                os.close(self.holding_fd)
                self.holding_fd = None

    def apply(
        self,
        writes: Mapping[str, WriteSpec],
        deletes: Mapping[str, DeleteSpec],
        *,
        lock_path: str,
        lock: WriteSpec,
        aliases: Mapping[str, str] | None = None,
    ) -> None:
        self.aliases = {} if aliases is None else dict(aliases)
        self._check_aliases()
        all_names = [*writes, *deletes, lock_path]
        if len(set(all_names)) != len(all_names):
            raise MutationSafetyError("generated mutation paths are duplicated")

        bindings: dict[str, _Binding] = {}
        for relative, spec in writes.items():
            bindings[relative] = self._bind(relative, spec.owns_existing)
        for relative, spec in deletes.items():
            bindings[relative] = self._bind(relative, spec.owns_existing)
        lock_binding = self._bind(lock_path, lambda _content: True)
        bindings[lock_path] = lock_binding

        for relative, spec in writes.items():
            self._check_aliases()
            record = self._write(bindings[relative], spec)
            self.records.append(record)
        for relative, spec in deletes.items():
            self._check_aliases()
            record = self._delete(bindings[relative], spec)
            self.records.append(record)
        self._check_aliases()
        self.records.append(self._write(lock_binding, lock))
        self._check_aliases()

        try:
            for record in self.records:
                if record.action in {"replace", "delete"}:
                    assert record.old_name is not None and record.old_identity is not None
                    self._delete_private(
                        record.old_name,
                        record.old_identity,
                        record.binding.relative,
                        record.binding.content,
                    )
            if self.retained:
                raise MutationSafetyError(
                    "generated mutation completed with retained concurrent state"
                )
        except Exception:
            self.retained = True
            raise


def apply_generated_mutations(
    repository_root: Path,
    writes: Mapping[str, WriteSpec],
    deletes: Mapping[str, DeleteSpec],
    *,
    lock_path: str,
    lock: WriteSpec,
    aliases: Mapping[str, str] | None = None,
) -> None:
    """Apply generated writes/deletes with fail-closed rollback semantics."""

    transaction = _Transaction(repository_root)
    try:
        with transaction:
            try:
                transaction.apply(
                    writes,
                    deletes,
                    lock_path=lock_path,
                    lock=lock,
                    aliases=aliases,
                )
            except Exception as exc:
                rollback_errors: list[str] = []
                for record in reversed(transaction.records):
                    try:
                        transaction._rollback_record(record)
                    except Exception as rollback_error:
                        rollback_errors.append(
                            f"{record.binding.relative}: {rollback_error}"
                        )
                if rollback_errors:
                    transaction.retained = True
                    raise MutationSafetyError(
                        f"generated mutation failed ({exc}); rollback incomplete: "
                        + "; ".join(rollback_errors)
                    ) from exc
                transaction._remove_created_directories()
                raise
    except MutationSafetyError:
        raise
    except Exception as exc:
        raise MutationSafetyError(f"generated mutation failed: {exc}") from exc
