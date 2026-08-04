from __future__ import annotations

from pathlib import Path

from generated_release_bundle_producer_fixture_prior import (
    RELEASE_BUNDLE_PRODUCER_SCRIPT as _PRIOR_RELEASE_BUNDLE_PRODUCER_SCRIPT,
)


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    occurrences = source.count(old)
    if occurrences != 1:
        raise AssertionError(
            f"release bundle producer fourth-review anchor {label!r} "
            f"matched {occurrences} times"
        )
    return source.replace(old, new, 1)


RELEASE_BUNDLE_PRODUCER_SCRIPT = _PRIOR_RELEASE_BUNDLE_PRODUCER_SCRIPT

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """ROOT = Path(__file__).resolve().parents[1]
GIT_DIR = ROOT / ".git"
""",
    """PRODUCER_PATH = Path(os.path.abspath(__file__))
try:
    producer_mode = PRODUCER_PATH.lstat().st_mode
except OSError as exc:
    print(
        "generated release bundle producer failed: "
        f"cannot inspect producer path: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(2)
if not stat.S_ISREG(producer_mode):
    print(
        "generated release bundle producer failed: "
        "producer path must be a regular non-symbolic file",
        file=sys.stderr,
    )
    raise SystemExit(2)
ROOT = PRODUCER_PATH.parents[1]
GIT_DIR = ROOT / ".git"
""",
    "producer leaf preflight",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary_preexisted = temporary.exists() or temporary.is_symlink()
    if temporary_preexisted:
        raise FileExistsError(f"atomic-write temporary already exists: {temporary}")
    try:
        temporary.write_bytes(content)
        temporary.replace(path)
    except OSError:
        if not temporary_preexisted and (
            temporary.exists() or temporary.is_symlink()
        ):
            try:
                if temporary.is_symlink() or temporary.is_file():
                    temporary.unlink()
            except OSError:
                pass
        raise
""",
    """def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target_mode: int | None = None
    if path.exists() and not path.is_symlink():
        target_status = path.stat()
        if stat.S_ISREG(target_status.st_mode):
            target_mode = stat.S_IMODE(target_status.st_mode)
    temporary = path.with_name(path.name + ".tmp")
    temporary_preexisted = temporary.exists() or temporary.is_symlink()
    if temporary_preexisted:
        raise FileExistsError(f"atomic-write temporary already exists: {temporary}")
    temporary_created = False
    try:
        with temporary.open("xb") as output:
            temporary_created = True
            output.write(content)
        if target_mode is not None:
            temporary.chmod(target_mode)
        temporary.replace(path)
    except OSError:
        if temporary_created and (
            temporary.exists() or temporary.is_symlink()
        ):
            try:
                if temporary.is_symlink() or temporary.is_file():
                    temporary.unlink()
            except OSError:
                pass
        raise
""",
    "exclusive atomic temporary creation and mode preservation",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """    valid, diagnostic = validate_bundle(revision)
    if not valid:
        rollback_created_record(previous_bundle, record_path)
        fail("generated bundle did not validate: " + diagnostic)
""",
    """    try:
        valid, diagnostic = validate_bundle(revision)
    except OSError as exc:
        rollback_created_record(previous_bundle, record_path)
        fail(f"cannot execute release bundle validator: {exc}")
    if not valid:
        rollback_created_record(previous_bundle, record_path)
        fail("generated bundle did not validate: " + diagnostic)
""",
    "creation validator execution rollback",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """    valid, diagnostic = validate_bundle(revision)
    if not valid:
        restore_current(previous_bundle)
        fail(
            "retained release bundle is not accepted by current policy; "
            "new evidence is required: "
            + diagnostic
        )
""",
    """    try:
        valid, diagnostic = validate_bundle(revision)
    except OSError as exc:
        restore_current(previous_bundle)
        fail(f"cannot execute release bundle validator: {exc}")
    if not valid:
        restore_current(previous_bundle)
        fail(
            "retained release bundle is not accepted by current policy; "
            "new evidence is required: "
            + diagnostic
        )
""",
    "activation validator execution rollback",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """    index["currentRecordId"] = record_id
    try:
        write_bytes(INDEX_PATH, json_bytes(index))
    except OSError as exc:
        rollback_created_record(previous_bundle, record_path)
        fail(f"cannot publish release bundle index: {exc}")
""",
    """    index["currentRecordId"] = record_id
    try:
        verify_revision_state(revision)
    except SystemExit:
        rollback_created_record(previous_bundle, record_path)
        raise
    try:
        write_bytes(INDEX_PATH, json_bytes(index))
    except OSError as exc:
        rollback_created_record(previous_bundle, record_path)
        fail(f"cannot publish release bundle index: {exc}")
""",
    "creation pre-publication recheck",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """    index["currentRecordId"] = record_id
    try:
        write_bytes(INDEX_PATH, json_bytes(index))
    except OSError as exc:
        restore_current(previous_bundle)
        fail(f"cannot publish release bundle index: {exc}")
""",
    """    index["currentRecordId"] = record_id
    try:
        verify_revision_state(revision)
    except SystemExit:
        restore_current(previous_bundle)
        raise
    try:
        write_bytes(INDEX_PATH, json_bytes(index))
    except OSError as exc:
        restore_current(previous_bundle)
        fail(f"cannot publish release bundle index: {exc}")
""",
    "activation pre-publication recheck",
)


def _install_release_bundle_producer(root: Path) -> None:
    producer = root / "product/produce_release_bundle.py"
    producer.write_text(RELEASE_BUNDLE_PRODUCER_SCRIPT, encoding="utf-8")
    producer.chmod(0o755)
