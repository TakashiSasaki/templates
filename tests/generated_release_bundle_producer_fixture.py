from __future__ import annotations

from pathlib import Path

RELEASE_BUNDLE_PRODUCER_SCRIPT = r'''#!/usr/bin/env python3
"""Produce and activate immutable fixture release-bundle records."""

from __future__ import annotations

import sys

if not sys.flags.isolated:
    print(
        "generated release bundle producer failed: "
        "producer requires Python isolated mode (-I)",
        file=sys.stderr,
    )
    raise SystemExit(2)

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT_DIR = ROOT / ".git"
MANIFEST_PATH = ROOT / "contracts/manifest.json"
RELEASE_PATH = ROOT / "contracts/release-evidence.json"
BUNDLE_PATH = ROOT / "contracts/release-bundle.json"
INDEX_PATH = ROOT / "product/release-bundle-index.json"
RECORDS_DIR = ROOT / "product/release-bundle-records"
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
RECORD_ID_PATTERN = re.compile(r"^release-bundle-[0-9]{20}$")
_ALLOWED_TRACKED_CHANGES = {
    "contracts/release-evidence.json",
    "contracts/release-bundle.json",
}
_GIT_CONFIG_OVERRIDES = (
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.untrackedCache=false",
    "-c",
    "core.ignoreStat=false",
    "-c",
    "core.sparseCheckout=false",
    "-c",
    "core.sparseCheckoutCone=false",
)


def fail(message: str) -> None:
    print(f"generated release bundle producer failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot load {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"expected JSON object: {path.relative_to(ROOT)}")
    return value


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def timestamp() -> tuple[int, str]:
    current_ns = time.time_ns()
    seconds, nanoseconds = divmod(current_ns, 1_000_000_000)
    whole = datetime.fromtimestamp(seconds, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    return current_ns, f"{whole}.{nanoseconds:09d}Z"


def git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            del environment[name]
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_LITERAL_PATHSPECS"] = "1"
    return environment


def execute_git(arguments: list[str]) -> str:
    completed = subprocess.run(
        arguments,
        cwd=ROOT,
        env=git_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        fail("cannot verify generated repository revision: " + completed.stderr.strip())
    return completed.stdout.strip()


def run_git_unpinned(*arguments: str) -> str:
    return execute_git(
        ["git", *_GIT_CONFIG_OVERRIDES, "-C", str(ROOT), *arguments]
    )


def run_git_pinned(*arguments: str) -> str:
    return execute_git(
        [
            "git",
            *_GIT_CONFIG_OVERRIDES,
            "--git-dir",
            str(GIT_DIR),
            "--work-tree",
            str(ROOT),
            *arguments,
        ]
    )


def allowed_untracked(path: str) -> bool:
    if path in {
        "product/release-run.json",
        "product/release-bundle-index.json",
    }:
        return True
    return (
        path.startswith("product/release-bundle-records/")
        and path.endswith(".json")
    )


def verify_revision_state(revision: str) -> None:
    if GIT_DIR.is_symlink() or not GIT_DIR.is_dir():
        fail("generated repository .git directory is not a regular directory")
    expected_root = ROOT.resolve()
    expected_git_dir = GIT_DIR.resolve()
    resolved_git_dir = Path(
        run_git_unpinned("rev-parse", "--absolute-git-dir")
    ).resolve()
    if resolved_git_dir != expected_git_dir:
        fail("Git resolved directory does not match generated repository .git")
    resolved_worktree = Path(
        run_git_unpinned("rev-parse", "--show-toplevel")
    ).resolve()
    if resolved_worktree != expected_root:
        fail("Git resolved worktree does not match generated repository root")

    head = run_git_pinned("rev-parse", "--verify", "HEAD^{commit}")
    if head != revision:
        fail("revision does not match generated repository HEAD")
    if run_git_pinned("diff", "--cached", "--name-only"):
        fail("generated repository has staged changes")

    tracked_changes = {
        line
        for line in run_git_pinned("diff", "--name-only").splitlines()
        if line
    }
    unexpected_tracked = tracked_changes - _ALLOWED_TRACKED_CHANGES
    if unexpected_tracked:
        fail(
            "generated repository has unexpected tracked changes: "
            + ", ".join(sorted(unexpected_tracked))
        )

    status = run_git_pinned(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    unexpected_untracked: list[str] = []
    for line in status.splitlines():
        if line.startswith("?? "):
            path = line[3:]
            if not allowed_untracked(path):
                unexpected_untracked.append(path)
    if unexpected_untracked:
        fail(
            "generated repository has unexpected untracked files: "
            + ", ".join(sorted(unexpected_untracked))
        )

    ignored = run_git_pinned(
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
    )
    if ignored:
        fail(
            "generated repository has ignored uncommitted files: "
            + ", ".join(ignored.splitlines())
        )


def validator_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("PYTHON"):
            del environment[name]
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def validate_release(revision: str) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/validate_release_evidence.py",
            "--expected-revision",
            revision,
        ],
        cwd=ROOT,
        env=validator_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip()
        fail("approved release evidence is required: " + diagnostic)


def validate_bundle(revision: str) -> tuple[bool, str]:
    diagnostics: list[str] = []
    commands = (
        (
            "scripts/validate_release_bundle.py",
            "--expected-revision",
            revision,
        ),
        (
            "-m",
            "scripts.validate_release_bundle",
            "--expected-revision",
            revision,
        ),
    )
    for arguments in commands:
        completed = subprocess.run(
            [sys.executable, "-B", *arguments],
            cwd=ROOT,
            env=validator_environment(),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            diagnostics.append(completed.stderr.strip() or completed.stdout.strip())
    return not diagnostics, "\n".join(diagnostics)


def active_artifacts() -> list[dict[str, str]]:
    manifest = load_json(MANIFEST_PATH)
    entries = manifest.get("contracts")
    if not isinstance(entries, list):
        fail("contract manifest is malformed")
    artifacts: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            fail("contract manifest contains a malformed entry")
        contract_id = entry.get("id")
        document = entry.get("document")
        if contract_id == "release_bundle":
            continue
        if not isinstance(contract_id, str) or not isinstance(document, str):
            fail("contract manifest contains incomplete active metadata")
        path = ROOT / document
        try:
            content = path.read_bytes()
        except OSError as exc:
            fail(f"cannot read {document}: {exc}")
        artifacts.append(
            {
                "contractId": contract_id,
                "path": document,
                "sha256": sha256_bytes(content),
            }
        )
    return artifacts


def empty_index() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "currentRecordId": None,
        "records": [],
    }


def load_index() -> dict[str, object]:
    if not INDEX_PATH.exists():
        return empty_index()
    index = load_json(INDEX_PATH)
    records = index.get("records")
    current = index.get("currentRecordId")
    if index.get("schemaVersion") != 1 or not isinstance(records, list):
        fail("release bundle index is malformed")
    record_ids: set[str] = set()
    current_count = 0
    for record in records:
        if not isinstance(record, dict):
            fail("release bundle index contains a malformed record")
        record_id = record.get("id")
        path_text = record.get("path")
        digest = record.get("bundleSha256")
        status = record.get("status")
        if (
            not isinstance(record_id, str)
            or RECORD_ID_PATTERN.fullmatch(record_id) is None
            or record_id in record_ids
        ):
            fail("release bundle index contains an invalid or duplicate record id")
        record_ids.add(record_id)
        expected_path = f"product/release-bundle-records/{record_id}.json"
        if path_text != expected_path:
            fail(f"release bundle record {record_id}: path changed")
        record_path = ROOT / expected_path
        try:
            content = record_path.read_bytes()
        except OSError as exc:
            fail(f"release bundle record {record_id}: cannot read retained bytes: {exc}")
        if digest != sha256_bytes(content):
            fail(f"release bundle record {record_id}: retained bytes changed")
        if status == "current":
            current_count += 1
        elif status != "superseded":
            fail(f"release bundle record {record_id}: invalid lifecycle status")
    if records:
        if current_count != 1 or current not in record_ids:
            fail("release bundle index current record is inconsistent")
        current_record = next(
            record for record in records if record.get("id") == current
        )
        if current_record.get("status") != "current":
            fail("release bundle index current record is not marked current")
    elif current is not None:
        fail("empty release bundle index must not claim a current record")
    return index


def next_record_identity(existing_ids: set[str]) -> tuple[str, str]:
    while True:
        current_ns, generated_at = timestamp()
        record_id = f"release-bundle-{current_ns:020d}"
        if record_id not in existing_ids:
            return record_id, generated_at
        time.sleep(0.000001)


def restore_current(previous: bytes | None) -> None:
    if previous is None:
        if BUNDLE_PATH.exists():
            BUNDLE_PATH.unlink()
    else:
        write_bytes(BUNDLE_PATH, previous)


def create_record(revision: str, index: dict[str, object]) -> str:
    records = index["records"]
    assert isinstance(records, list)
    existing_ids = {
        record["id"]
        for record in records
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    record_id, generated_at = next_record_identity(existing_ids)
    record_relative = f"product/release-bundle-records/{record_id}.json"
    bundle = {
        "$schema": "../schemas/release-bundle.schema.json",
        "schemaVersion": 1,
        "mode": "product",
        "subject": {
            "revision": revision,
            "description": "Candidate revision represented by this immutable handoff bundle.",
        },
        "provenance": {
            "kind": "local-run",
            "id": record_id,
            "locator": record_relative,
            "generatedAt": generated_at,
        },
        "handoff": {
            "status": "ready",
            "description": "The exact active contract set is ready for provider-neutral handoff.",
        },
        "artifacts": active_artifacts(),
    }
    content = json_bytes(bundle)
    record_path = ROOT / record_relative
    if record_path.exists():
        fail(f"release bundle record already exists: {record_id}")

    previous_bundle = BUNDLE_PATH.read_bytes() if BUNDLE_PATH.exists() else None
    write_bytes(record_path, content)
    write_bytes(BUNDLE_PATH, content)
    valid, diagnostic = validate_bundle(revision)
    if not valid:
        restore_current(previous_bundle)
        record_path.unlink(missing_ok=True)
        fail("generated bundle did not validate: " + diagnostic)

    for record in records:
        if isinstance(record, dict) and record.get("status") == "current":
            record["status"] = "superseded"
            record["supersededBy"] = record_id
    records.append(
        {
            "id": record_id,
            "path": record_relative,
            "candidateRevision": revision,
            "bundleSha256": sha256_bytes(content),
            "generatedAt": generated_at,
            "status": "current",
        }
    )
    index["currentRecordId"] = record_id
    write_bytes(INDEX_PATH, json_bytes(index))
    return record_id


def activate_record(
    revision: str,
    index: dict[str, object],
    record_id: str,
) -> str:
    records = index["records"]
    assert isinstance(records, list)
    target = next(
        (
            record
            for record in records
            if isinstance(record, dict) and record.get("id") == record_id
        ),
        None,
    )
    if target is None:
        fail(f"unknown retained release bundle record: {record_id}")
    if target.get("candidateRevision") != revision:
        fail("retained release bundle candidate revision does not match requested revision")
    record_path = ROOT / str(target["path"])
    content = record_path.read_bytes()
    if target.get("bundleSha256") != sha256_bytes(content):
        fail("retained release bundle bytes no longer match the index")

    previous_bundle = BUNDLE_PATH.read_bytes() if BUNDLE_PATH.exists() else None
    write_bytes(BUNDLE_PATH, content)
    valid, diagnostic = validate_bundle(revision)
    if not valid:
        restore_current(previous_bundle)
        fail(
            "retained release bundle is not accepted by current policy; "
            "new evidence is required: "
            + diagnostic
        )

    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("id") == record_id:
            record["status"] = "current"
            record.pop("supersededBy", None)
        elif record.get("status") == "current":
            record["status"] = "superseded"
            record["supersededBy"] = record_id
    index["currentRecordId"] = record_id
    write_bytes(INDEX_PATH, json_bytes(index))
    return record_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create one immutable release-bundle record or reactivate an exact "
            "retained record that still satisfies current repository policy."
        )
    )
    parser.add_argument("--revision", required=True)
    parser.add_argument("--activate-record")
    arguments = parser.parse_args(argv)
    if REVISION_PATTERN.fullmatch(arguments.revision) is None:
        fail("revision must be a lowercase 40-hex Git object name")
    if (
        arguments.activate_record is not None
        and RECORD_ID_PATTERN.fullmatch(arguments.activate_record) is None
    ):
        fail("activate-record must be an exact retained release bundle record id")

    verify_revision_state(arguments.revision)
    validate_release(arguments.revision)
    index = load_index()
    if arguments.activate_record is None:
        record_id = create_record(arguments.revision, index)
        print(f"generated release bundle: {record_id}")
    else:
        record_id = activate_record(
            arguments.revision,
            index,
            arguments.activate_record,
        )
        print(f"activated retained release bundle: {record_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _install_release_bundle_producer(root: Path) -> None:
    producer = root / "product/produce_release_bundle.py"
    producer.write_text(RELEASE_BUNDLE_PRODUCER_SCRIPT, encoding="utf-8")
    producer.chmod(0o755)
