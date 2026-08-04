from __future__ import annotations

from pathlib import Path

RELEASE_EVIDENCE_PRODUCER_SCRIPT = r'''#!/usr/bin/env python3
"""Produce fixture release evidence from one reviewed command execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_PATH = ROOT / "contracts/implementation-evidence.json"
RELEASE_PATH = ROOT / "contracts/release-evidence.json"
RUN_PATH = ROOT / "product/release-run.json"
COMMAND_ID = "generated-product-proof"
COMMAND_TEXT = "python product/prove_conformance.py"
COMMAND_PURPOSE = "Run every reviewed generated-product proof."
COMMAND_ARGV = [sys.executable, "product/prove_conformance.py"]
GATE_ID = "generated-product-release"
GATE_PURPOSE = "Block fixture release unless all generated-product proofs pass."
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        fail(f"expected JSON object: {path.relative_to(ROOT)}")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fail(message: str) -> None:
    print(
        f"generated release evidence producer failed: {message}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def timestamp_after(previous_ns: int | None = None) -> tuple[int, str]:
    current_ns = time.time_ns()
    if previous_ns is not None and current_ns <= previous_ns:
        current_ns = previous_ns + 1
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
    return environment


def run_git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        cwd=ROOT,
        env=git_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        fail(
            "cannot verify generated repository revision: "
            + completed.stderr.strip()
        )
    return completed.stdout.strip()


def verify_revision(revision: str) -> str:
    head = run_git("rev-parse", "--verify", "HEAD^{commit}")
    if head != revision:
        fail("revision does not match generated repository HEAD")
    status = run_git("status", "--porcelain=v1", "--untracked-files=all")
    if status:
        fail("generated repository has uncommitted changes")
    return head


def verify_fixed_registration(implementation: dict[str, object]) -> None:
    expected_commands = [
        {
            "id": COMMAND_ID,
            "command": COMMAND_TEXT,
            "purpose": COMMAND_PURPOSE,
        }
    ]
    expected_gates = [
        {
            "id": GATE_ID,
            "purpose": GATE_PURPOSE,
            "commandIds": [COMMAND_ID],
        }
    ]
    if implementation.get("mode") != "product":
        fail("implementation evidence is not in product mode")
    if implementation.get("commands") != expected_commands:
        fail("authoritative command registration changed")
    if implementation.get("releaseGates") != expected_gates:
        fail("release gate registration changed")


def normalize_exit_code(returncode: int) -> int:
    if returncode >= 0:
        return returncode
    return 128 + abs(returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the one reviewed generated-product proof and produce "
            "revision-bound release evidence."
        )
    )
    parser.add_argument("--revision", required=True)
    arguments = parser.parse_args(argv)
    if REVISION_PATTERN.fullmatch(arguments.revision) is None:
        fail("revision must be a lowercase 40-hex Git object name")

    verified_head = verify_revision(arguments.revision)
    implementation = load_json(IMPLEMENTATION_PATH)
    verify_fixed_registration(implementation)

    started_ns, started_at = timestamp_after()
    completed = subprocess.run(
        COMMAND_ARGV,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    completed_ns, completed_at = timestamp_after(started_ns)
    exit_code = normalize_exit_code(completed.returncode)
    command_status = "passed" if completed.returncode == 0 else "failed"
    gate_status = "passed" if command_status == "passed" else "failed"
    decision_status = "approved" if gate_status == "passed" else "rejected"
    decided_ns, decided_at = timestamp_after(completed_ns)
    _, generated_at = timestamp_after(decided_ns)
    command_digest = hashlib.sha256(COMMAND_TEXT.encode("utf-8")).hexdigest()

    run = {
        "schemaVersion": 1,
        "revision": arguments.revision,
        "revisionBinding": {
            "verifiedHead": verified_head,
            "worktree": "clean",
        },
        "command": {
            "id": COMMAND_ID,
            "authoritativeCommand": COMMAND_TEXT,
            "executionArgv": COMMAND_ARGV,
            "commandDigest": command_digest,
            "status": command_status,
            "exitCode": exit_code,
            "startedAt": started_at,
            "completedAt": completed_at,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
        "gate": {
            "id": GATE_ID,
            "status": gate_status,
            "commandIds": [COMMAND_ID],
        },
        "decision": {
            "status": decision_status,
            "decidedAt": decided_at,
        },
        "generatedAt": generated_at,
    }
    write_json(RUN_PATH, run)

    release = {
        "$schema": "../schemas/release-evidence.schema.json",
        "schemaVersion": 1,
        "mode": "product",
        "subject": {
            "revision": arguments.revision,
            "description": "Exact generated-product revision evaluated for release.",
        },
        "provenance": {
            "kind": "local-run",
            "id": "generated-product-release-run",
            "locator": "product/release-run.json",
            "generatedAt": generated_at,
        },
        "decision": {
            "status": decision_status,
            "decidedAt": decided_at,
            "description": (
                "The reviewed generated-product release gate passed."
                if decision_status == "approved"
                else "The reviewed generated-product release gate failed."
            ),
        },
        "commandResults": [
            {
                "commandId": COMMAND_ID,
                "commandDigest": command_digest,
                "status": command_status,
                "exitCode": exit_code,
                "startedAt": started_at,
                "completedAt": completed_at,
                "resultLocator": "product/release-run.json#/command",
            }
        ],
        "gateResults": [
            {
                "gateId": GATE_ID,
                "status": gate_status,
                "resultLocator": "product/release-run.json#/gate",
            }
        ],
    }
    write_json(RELEASE_PATH, release)

    message = f"generated release evidence: {decision_status}"
    if decision_status == "approved":
        print(message)
        return 0
    print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _install_release_evidence_producer(root: Path) -> None:
    producer = root / "product/produce_release_evidence.py"
    producer.write_text(RELEASE_EVIDENCE_PRODUCER_SCRIPT, encoding="utf-8")
    producer.chmod(0o755)
