#!/usr/bin/env python3
"""Produce release evidence and a digest-closed bundle as one recoverable transaction."""
from __future__ import annotations

import sys

if not sys.flags.isolated:
    print("release orchestration requires Python isolated mode (-I)", file=sys.stderr)
    raise SystemExit(2)
sys.dont_write_bytecode = True

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIFECYCLE_LOCK_PATH = HERE / "lifecycle_lock.py"
EVIDENCE_PRODUCER_PATH = HERE / "produce_release_evidence.py"
BUNDLE_PRODUCER_PATH = HERE / "produce_release_bundle.py"
MARKER_FILENAME = "template-composition-release-transaction.json"
MARKER_TEMP_FILENAME = MARKER_FILENAME + ".tmp"
EVIDENCE_BACKUP_FILENAME = "template-composition-release-evidence.backup"
BUNDLE_BACKUP_FILENAME = "template-composition-release-bundle.backup"
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def load_managed_module(name: str, path: Path, label: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load managed {label}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lifecycle_lock = load_managed_module(
    "composition_release_orchestration_lock",
    LIFECYCLE_LOCK_PATH,
    "release lifecycle lock helper",
)
evidence_producer = load_managed_module(
    "composition_release_evidence_producer",
    EVIDENCE_PRODUCER_PATH,
    "release evidence producer",
)
bundle_producer = load_managed_module(
    "composition_release_bundle_producer",
    BUNDLE_PRODUCER_PATH,
    "release bundle producer",
)


class ReleaseTransactionError(RuntimeError):
    """Raised when the recoverable release transaction cannot be used safely."""


def fail(message: str, *, code: int = 2) -> None:
    print(f"release orchestration failed: {message}", file=sys.stderr)
    raise SystemExit(code)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise ReleaseTransactionError(
                "short write while persisting release transaction state"
            )
        view = view[written:]


def _read_regular(path: Path, *, label: str) -> bytes:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ReleaseTransactionError(f"cannot inspect {label}: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ReleaseTransactionError(f"{label} must be a regular non-symbolic file")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ReleaseTransactionError(f"cannot read {label}: {exc}") from exc


def _unlink_regular(path: Path, *, label: str) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ReleaseTransactionError(f"cannot inspect {label}: {exc}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ReleaseTransactionError(f"{label} must be a regular non-symbolic file")
    try:
        path.unlink()
    except OSError as exc:
        raise ReleaseTransactionError(f"cannot remove {label}: {exc}") from exc
    _fsync_directory(path.parent)


def _create_durable(path: Path, data: bytes, *, label: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ReleaseTransactionError(f"cannot create {label}: {exc}") from exc
    try:
        _write_all(descriptor, data)
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        try:
            path.unlink()
            _fsync_directory(path.parent)
        except OSError:
            pass
        raise
    else:
        os.close(descriptor)
    _fsync_directory(path.parent)


def _fsync_regular_file(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ReleaseTransactionError(
            f"cannot open release output for fsync: {path}: {exc}"
        ) from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ReleaseTransactionError(
                f"release output must remain a regular file: {path}"
            )
        os.fsync(descriptor)
    except OSError as exc:
        raise ReleaseTransactionError(f"cannot fsync release output {path}: {exc}") from exc
    finally:
        os.close(descriptor)


def _durable_replace(path: Path, data: bytes, *, mode: int, label: str) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    except OSError as exc:
        raise ReleaseTransactionError(f"cannot inspect {label}: {exc}") from exc
    if info is not None and not stat.S_ISREG(info.st_mode):
        raise ReleaseTransactionError(f"{label} must remain a regular non-symbolic file")

    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.release-restore-", dir=path.parent
    )
    temporary = Path(temp_name)
    try:
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(descriptor, mode)
            except OSError:
                pass
        _write_all(descriptor, data)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1

        try:
            current = os.lstat(path)
        except FileNotFoundError:
            current = None
        except OSError as exc:
            raise ReleaseTransactionError(f"cannot re-inspect {label}: {exc}") from exc
        if current is not None and not stat.S_ISREG(current.st_mode):
            raise ReleaseTransactionError(
                f"{label} changed to a non-regular or symbolic path during recovery"
            )

        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _output_paths(root: Path, *, require_regular: bool = True) -> tuple[Path, Path]:
    try:
        evidence = evidence_producer.candidate.ensure_output_path(
            root, evidence_producer.EVIDENCE_RELATIVE
        )
        bundle = bundle_producer.candidate.ensure_output_path(
            root, bundle_producer.BUNDLE_RELATIVE
        )
    except (
        evidence_producer.candidate.CandidateError,
        bundle_producer.candidate.CandidateError,
    ) as exc:
        raise ReleaseTransactionError(str(exc)) from exc
    if require_regular:
        for path, label in ((evidence, "release evidence"), (bundle, "release bundle")):
            try:
                info = os.lstat(path)
            except OSError as exc:
                raise ReleaseTransactionError(f"cannot inspect {label}: {exc}") from exc
            if not stat.S_ISREG(info.st_mode):
                raise ReleaseTransactionError(
                    f"{label} must be a regular non-symbolic file"
                )
    return evidence, bundle


def _transaction_paths(git_dir: Path) -> tuple[Path, Path, Path]:
    return (
        git_dir / MARKER_FILENAME,
        git_dir / EVIDENCE_BACKUP_FILENAME,
        git_dir / BUNDLE_BACKUP_FILENAME,
    )


def _cleanup_paths(git_dir: Path, *, strict: bool) -> None:
    _, evidence_backup, bundle_backup = _transaction_paths(git_dir)
    for path, label in (
        (git_dir / MARKER_TEMP_FILENAME, "release transaction marker temporary"),
        (evidence_backup, "release evidence backup"),
        (bundle_backup, "release bundle backup"),
    ):
        try:
            _unlink_regular(path, label=label)
        except ReleaseTransactionError as exc:
            if strict:
                raise
            print(f"release orchestration cleanup warning: {exc}", file=sys.stderr)


def _cleanup_orphans(git_dir: Path) -> None:
    marker, _, _ = _transaction_paths(git_dir)
    if marker.exists() or marker.is_symlink():
        return
    _cleanup_paths(git_dir, strict=True)


def _marker_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_create_marker(git_dir: Path, value: dict) -> None:
    marker = git_dir / MARKER_FILENAME
    temporary = git_dir / MARKER_TEMP_FILENAME
    _unlink_regular(temporary, label="stale release transaction marker temporary")
    _create_durable(
        temporary,
        _marker_bytes(value),
        label="release transaction marker temporary",
    )
    try:
        os.replace(temporary, marker)
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise ReleaseTransactionError(
            f"cannot publish release transaction marker: {exc}"
        ) from exc
    _fsync_directory(git_dir)


def _load_marker(path: Path) -> dict:
    raw = _read_regular(path, label="release transaction marker")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseTransactionError(
            f"release transaction marker is invalid JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ReleaseTransactionError("release transaction marker must be an object")
    expected_keys = {
        "schemaVersion",
        "operation",
        "revision",
        "evidenceSha256",
        "bundleSha256",
        "evidenceMode",
        "bundleMode",
    }
    if set(value) != expected_keys:
        raise ReleaseTransactionError("release transaction marker has unexpected fields")
    if value["schemaVersion"] != 1 or isinstance(value["schemaVersion"], bool):
        raise ReleaseTransactionError(
            "release transaction marker schemaVersion must be integer 1"
        )
    if value["operation"] != "release":
        raise ReleaseTransactionError("release transaction marker operation is unsupported")
    revision = value["revision"]
    if not isinstance(revision, str) or REVISION_PATTERN.fullmatch(revision) is None:
        raise ReleaseTransactionError("release transaction marker revision is invalid")
    for key in ("evidenceSha256", "bundleSha256"):
        digest = value[key]
        if not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None:
            raise ReleaseTransactionError(f"release transaction marker {key} is invalid")
    for key in ("evidenceMode", "bundleMode"):
        mode = value[key]
        if (
            not isinstance(mode, int)
            or isinstance(mode, bool)
            or not 0 <= mode <= 0o7777
        ):
            raise ReleaseTransactionError(f"release transaction marker {key} is invalid")
    return value


def _begin_transaction(root: Path, git_dir: Path, revision: str) -> None:
    _cleanup_orphans(git_dir)
    marker, evidence_backup, bundle_backup = _transaction_paths(git_dir)
    if marker.exists() or marker.is_symlink():
        raise ReleaseTransactionError(
            "incomplete release transaction requires recovery before starting"
        )

    evidence_path, bundle_path = _output_paths(root)
    evidence = _read_regular(evidence_path, label="release evidence")
    bundle = _read_regular(bundle_path, label="release bundle")
    marker_value = {
        "schemaVersion": 1,
        "operation": "release",
        "revision": revision,
        "evidenceSha256": _sha256(evidence),
        "bundleSha256": _sha256(bundle),
        "evidenceMode": stat.S_IMODE(os.lstat(evidence_path).st_mode),
        "bundleMode": stat.S_IMODE(os.lstat(bundle_path).st_mode),
    }

    try:
        _create_durable(evidence_backup, evidence, label="release evidence backup")
        _create_durable(bundle_backup, bundle, label="release bundle backup")
        _atomic_create_marker(git_dir, marker_value)
    except BaseException:
        try:
            _cleanup_paths(git_dir, strict=False)
        finally:
            raise


def _recover_incomplete(root: Path, git_dir: Path) -> bool:
    marker, evidence_backup, bundle_backup = _transaction_paths(git_dir)
    if not marker.exists() and not marker.is_symlink():
        _cleanup_orphans(git_dir)
        return False

    marker_value = _load_marker(marker)
    evidence = _read_regular(evidence_backup, label="release evidence backup")
    bundle = _read_regular(bundle_backup, label="release bundle backup")
    if _sha256(evidence) != marker_value["evidenceSha256"]:
        raise ReleaseTransactionError(
            "release evidence backup digest does not match transaction marker"
        )
    if _sha256(bundle) != marker_value["bundleSha256"]:
        raise ReleaseTransactionError(
            "release bundle backup digest does not match transaction marker"
        )

    evidence_path, bundle_path = _output_paths(root, require_regular=False)
    _durable_replace(
        evidence_path,
        evidence,
        mode=marker_value["evidenceMode"],
        label="release evidence",
    )
    _durable_replace(
        bundle_path,
        bundle,
        mode=marker_value["bundleMode"],
        label="release bundle",
    )

    _unlink_regular(marker, label="release transaction marker")
    _cleanup_paths(git_dir, strict=False)
    print(f"Recovered incomplete release transaction for {marker_value['revision']}")
    return True


def _verify_downstream_bundle_unchanged(root: Path, git_dir: Path) -> None:
    _, _, bundle_backup = _transaction_paths(git_dir)
    expected = _read_regular(bundle_backup, label="release bundle backup")
    _, bundle_path = _output_paths(root)
    current = _read_regular(bundle_path, label="release bundle")
    if current != expected:
        raise ReleaseTransactionError(
            "release evidence stage modified downstream release bundle"
        )


def _commit_transaction(root: Path, git_dir: Path) -> None:
    marker, _, _ = _transaction_paths(git_dir)
    evidence_path, bundle_path = _output_paths(root)
    _fsync_regular_file(evidence_path)
    _fsync_regular_file(bundle_path)
    _fsync_directory(evidence_path.parent)
    _unlink_regular(marker, label="release transaction marker")
    _cleanup_paths(git_dir, strict=False)


def _evidence_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        revision=args.revision,
        provenance_kind=args.provenance_kind,
        provenance_id=args.evidence_provenance_id,
        provenance_locator=args.evidence_provenance_locator,
    )


def _bundle_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        revision=args.revision,
        provenance_kind=args.provenance_kind,
        provenance_id=args.bundle_provenance_id,
        provenance_locator=args.bundle_provenance_locator,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--revision")
    parser.add_argument("--recover-only", action="store_true")
    parser.add_argument(
        "--provenance-kind",
        choices=("local-run", "ci-run", "other"),
        default="local-run",
    )
    parser.add_argument("--evidence-provenance-id")
    parser.add_argument("--evidence-provenance-locator")
    parser.add_argument("--bundle-provenance-id")
    parser.add_argument("--bundle-provenance-locator")
    args = parser.parse_args()

    if not args.recover_only:
        if (
            not isinstance(args.revision, str)
            or REVISION_PATTERN.fullmatch(args.revision) is None
        ):
            fail("--revision must be an explicit lowercase 40-hex commit")
    elif args.revision is not None:
        fail("--recover-only does not accept --revision")

    root = Path(args.root).resolve()
    try:
        with lifecycle_lock.release_lifecycle_lock(root):
            git_dir = lifecycle_lock._repository_git_directory(root)
            recovered = _recover_incomplete(root, git_dir)
            if args.recover_only:
                if not recovered:
                    print("No incomplete release transaction found")
                return 0

            _begin_transaction(root, git_dir, args.revision)
            try:
                evidence_result = evidence_producer.produce_locked(
                    root,
                    _evidence_args(args),
                    additional_allowed_modified=frozenset(
                        {bundle_producer.BUNDLE_RELATIVE}
                    ),
                )
                if evidence_result != 0:
                    _recover_incomplete(root, git_dir)
                    print(
                        "release orchestration stopped because release evidence "
                        f"production returned {evidence_result}",
                        file=sys.stderr,
                    )
                    return evidence_result

                _verify_downstream_bundle_unchanged(root, git_dir)
                bundle_result = bundle_producer.produce_locked(root, _bundle_args(args))
                if bundle_result != 0:
                    _recover_incomplete(root, git_dir)
                    print(
                        "release orchestration stopped because release bundle "
                        f"production returned {bundle_result}",
                        file=sys.stderr,
                    )
                    return bundle_result

                _commit_transaction(root, git_dir)
            except BaseException:
                try:
                    _recover_incomplete(root, git_dir)
                except BaseException as recovery_exc:
                    print(
                        f"release orchestration recovery failed: {recovery_exc}",
                        file=sys.stderr,
                    )
                raise
    except lifecycle_lock.ReleaseLifecycleLockError as exc:
        fail(str(exc))
    except ReleaseTransactionError as exc:
        fail(str(exc))

    print(f"Release evidence and bundle produced for {args.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
