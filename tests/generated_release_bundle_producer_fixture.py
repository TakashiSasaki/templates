from __future__ import annotations

from pathlib import Path

from generated_release_bundle_producer_fixture_base import (
    RELEASE_BUNDLE_PRODUCER_SCRIPT as _BASE_RELEASE_BUNDLE_PRODUCER_SCRIPT,
)


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    occurrences = source.count(old)
    if occurrences != 1:
        raise AssertionError(
            f"release bundle producer hardening anchor {label!r} "
            f"matched {occurrences} times"
        )
    return source.replace(old, new, 1)


RELEASE_BUNDLE_PRODUCER_SCRIPT = _BASE_RELEASE_BUNDLE_PRODUCER_SCRIPT

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
""",
    """import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
""",
    "isolated imports",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """RECORDS_DIR = ROOT / \"product/release-bundle-records\"
REVISION_PATTERN = re.compile(r\"^[0-9a-f]{40}$\")
""",
    """RECORDS_DIR = ROOT / \"product/release-bundle-records\"
LOCK_PATH = GIT_DIR / \"release-bundle-lifecycle.lock\"
REVISION_PATTERN = re.compile(r\"^[0-9a-f]{40}$\")
""",
    "repository-local lock path",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + \".tmp\")
    temporary.write_bytes(content)
    temporary.replace(path)
""",
    """def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + \".tmp\")
    temporary_preexisted = temporary.exists() or temporary.is_symlink()
    if temporary_preexisted:
        raise FileExistsError(f\"atomic-write temporary already exists: {temporary}\")
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
    "atomic-write temporary cleanup",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """    tracked_changes = {
        line
        for line in run_git_pinned(\"diff\", \"--name-only\").splitlines()
        if line
    }
    unexpected_tracked = tracked_changes - _ALLOWED_TRACKED_CHANGES
    if unexpected_tracked:
        fail(
            \"generated repository has unexpected tracked changes: \"
            + \", \".join(sorted(unexpected_tracked))
        )

    verify_raw_candidate_bytes(revision, candidate_paths)

    status = run_git_pinned(
        \"status\",
        \"--porcelain=v1\",
        \"--untracked-files=all\",
    )
    unexpected_untracked: list[str] = []
    for line in status.splitlines():
        if line.startswith(\"?? \"):
            path = line[3:]
            if not allowed_untracked(path):
                unexpected_untracked.append(path)
""",
    """    verify_raw_candidate_bytes(revision, candidate_paths)

    untracked = run_git_pinned(
        \"ls-files\",
        \"--others\",
        \"--exclude-standard\",
    )
    unexpected_untracked = [
        path
        for path in untracked.splitlines()
        if path and not allowed_untracked(path)
    ]
""",
    "filter-free worktree inspection",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """    if index.get(\"schemaVersion\") != 1 or not isinstance(records, list):
        fail(\"release bundle index is malformed\")
""",
    """    schema_version = index.get(\"schemaVersion\")
    if (
        type(schema_version) is not int
        or schema_version != 1
        or not isinstance(records, list)
    ):
        fail(\"release bundle index is malformed\")
""",
    "exact lifecycle schema version type",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """def main(argv: list[str] | None = None) -> int:
""",
    """@contextmanager
def lifecycle_lock():
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, \"O_NOFOLLOW\"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(LOCK_PATH, flags, 0o600)
    except OSError as exc:
        fail(f\"cannot open release bundle lifecycle lock: {exc}\")
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            fail(\"release bundle lifecycle lock must be a regular file\")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except OSError as exc:
            fail(f\"cannot acquire release bundle lifecycle lock: {exc}\")
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
""",
    "exclusive lifecycle lock",
)

RELEASE_BUNDLE_PRODUCER_SCRIPT = _replace_once(
    RELEASE_BUNDLE_PRODUCER_SCRIPT,
    """    verify_revision_state(arguments.revision)
    validate_release(arguments.revision)
    index = load_index()
    if arguments.activate_record is None:
        record_id = create_record(arguments.revision, index)
        print(f\"generated release bundle: {record_id}\")
    else:
        record_id = activate_record(
            arguments.revision,
            index,
            arguments.activate_record,
        )
        print(f\"activated retained release bundle: {record_id}\")
""",
    """    verify_revision_state(arguments.revision)
    validate_release(arguments.revision)
    with lifecycle_lock():
        index = load_index()
        if arguments.activate_record is None:
            record_id = create_record(arguments.revision, index)
            print(f\"generated release bundle: {record_id}\")
        else:
            record_id = activate_record(
                arguments.revision,
                index,
                arguments.activate_record,
            )
            print(f\"activated retained release bundle: {record_id}\")
""",
    "serialized lifecycle transaction",
)


def _install_release_bundle_producer(root: Path) -> None:
    producer = root / "product/produce_release_bundle.py"
    producer.write_text(RELEASE_BUNDLE_PRODUCER_SCRIPT, encoding="utf-8")
    producer.chmod(0o755)
