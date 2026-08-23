#!/usr/bin/env python3
"""Execute release bindings and atomically produce approved revision-bound evidence."""
from __future__ import annotations

import sys

if not sys.flags.isolated:
    print("release evidence producer requires Python isolated mode (-I)", file=sys.stderr)
    raise SystemExit(2)

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATE_PATH = HERE / "candidate.py"
EVIDENCE_RELATIVE = "contracts/release-evidence.json"


def load_candidate_module():
    spec = importlib.util.spec_from_file_location("composition_release_candidate", CANDIDATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load managed candidate verification helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


candidate = load_candidate_module()


def fail(message: str, *, code: int = 2) -> None:
    print(f"release evidence producer failed: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot load {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"expected JSON object: {path}")
    return value


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if temporary.is_symlink():
        fail(f"temporary output path is a symlink: {temporary}")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def timestamp_after(previous_ns: int | None = None) -> tuple[int, str]:
    current_ns = time.time_ns()
    if previous_ns is not None and current_ns <= previous_ns:
        current_ns = previous_ns + 1
    seconds, nanoseconds = divmod(current_ns, 1_000_000_000)
    whole = datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return current_ns, f"{whole}.{nanoseconds:09d}Z"


def validator_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("PYTHON"):
            del environment[name]
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def run_validator(root: Path, relative: str, *arguments: str) -> None:
    path = root / relative
    completed = subprocess.run(
        [sys.executable, "-B", str(path), str(root), *arguments],
        cwd=root,
        env=validator_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip()
        fail(f"precondition/produced evidence validation failed: {diagnostic}")


def verify_candidate(root: Path, revision: str, *, context: str | None = None) -> None:
    try:
        candidate.verify_candidate(
            root,
            revision,
            allowed_modified=frozenset({EVIDENCE_RELATIVE}),
        )
    except candidate.CandidateError as exc:
        if context is None:
            fail(str(exc))
        fail(f"{context}: {exc}")


def verify_evidence_unchanged(path: Path, original: bytes, *, context: str) -> None:
    try:
        current = path.read_bytes()
    except OSError as exc:
        fail(f"{context}: cannot read canonical release evidence: {exc}")
    if current != original:
        fail(f"{context}: release command modified canonical release evidence")


def command_index(items: object, key: str, label: str) -> dict[str, dict]:
    if not isinstance(items, list):
        fail(f"{label} must be an array")
    result: dict[str, dict] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            fail(f"{label} entry {index} must be an object")
        value = item.get(key)
        if not isinstance(value, str) or not value:
            fail(f"{label} entry {index} requires {key}")
        if value in result:
            fail(f"duplicate {label} {key}: {value}")
        result[value] = item
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--revision", required=True)
    parser.add_argument(
        "--provenance-kind",
        choices=("local-run", "ci-run", "other"),
        default="local-run",
    )
    parser.add_argument("--provenance-id")
    parser.add_argument("--provenance-locator")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        evidence_path = candidate.ensure_output_path(root, EVIDENCE_RELATIVE)
    except candidate.CandidateError as exc:
        fail(str(exc))
    try:
        original_evidence = evidence_path.read_bytes()
    except OSError as exc:
        fail(f"cannot read canonical release evidence: {exc}")

    try:
        verify_candidate(root, args.revision)
        run_validator(
            root,
            ".template-composition/validators/validate_implementation_evidence.py",
        )
        run_validator(
            root,
            ".template-composition/validators/validate_release_execution.py",
        )

        implementation = load_json(root / "contracts/implementation-evidence.json")
        execution = load_json(root / "contracts/release-execution.json")
        if implementation.get("mode") != "product":
            fail("implementation evidence must be in product mode")
        if execution.get("mode") != "product":
            fail("release execution must be in product mode")

        authoritative = command_index(
            implementation.get("commands"), "id", "implementation command"
        )
        bindings = command_index(
            execution.get("commands"), "commandId", "release execution command"
        )
        gates = command_index(
            implementation.get("releaseGates"), "id", "release gate"
        )

        gated_ids: set[str] = set()
        for gate in gates.values():
            command_ids = gate.get("commandIds")
            if not isinstance(command_ids, list):
                fail(f"release gate {gate['id']}: commandIds must be an array")
            gated_ids.update(command_ids)
        if gated_ids != set(authoritative) or set(bindings) != set(authoritative):
            fail("validated release command closure changed unexpectedly")

        command_results: list[dict] = []
        previous_ns: int | None = None
        for command in implementation["commands"]:
            command_id = command["id"]
            binding = bindings[command_id]
            argv = binding["argv"]
            working_directory = binding["workingDirectory"]

            verify_evidence_unchanged(
                evidence_path,
                original_evidence,
                context=f"before release command {command_id}",
            )
            verify_candidate(
                root,
                args.revision,
                context=f"candidate changed before release command {command_id}",
            )
            try:
                cwd = candidate.resolve_working_directory(root, working_directory)
            except candidate.CandidateError as exc:
                fail(str(exc))

            started_ns, started_at = timestamp_after(previous_ns)
            print(f"Running release command {command_id}: {argv!r}", flush=True)
            try:
                completed = subprocess.run(argv, cwd=cwd, check=False)
            except OSError as exc:
                fail(f"cannot execute release command {command_id}: {exc}")
            completed_ns, completed_at = timestamp_after(started_ns)
            previous_ns = completed_ns
            if completed.returncode != 0:
                atomic_write(evidence_path, original_evidence)
                print(
                    f"release command {command_id} failed with exit code {completed.returncode}; canonical release evidence was restored",
                    file=sys.stderr,
                )
                return 1

            verify_candidate(
                root,
                args.revision,
                context=(
                    "candidate changed while release commands were running "
                    f"(after {command_id})"
                ),
            )
            verify_evidence_unchanged(
                evidence_path,
                original_evidence,
                context=f"after release command {command_id}",
            )
            command_results.append(
                {
                    "commandId": command_id,
                    "commandDigest": hashlib.sha256(
                        command["command"].encode("utf-8")
                    ).hexdigest(),
                    "status": "passed",
                    "exitCode": 0,
                    "startedAt": started_at,
                    "completedAt": completed_at,
                    "resultLocator": (
                        f"{EVIDENCE_RELATIVE}#/commandResults/{len(command_results)}"
                    ),
                }
            )

        verify_evidence_unchanged(
            evidence_path,
            original_evidence,
            context="before release evidence generation",
        )
        verify_candidate(
            root,
            args.revision,
            context="candidate changed before release evidence generation",
        )

        decided_ns, decided_at = timestamp_after(previous_ns)
        _, generated_at = timestamp_after(decided_ns)
        provenance_id = args.provenance_id or f"release-{args.revision[:12]}"
        provenance_locator = args.provenance_locator or EVIDENCE_RELATIVE
        gate_results = [
            {
                "gateId": gate["id"],
                "status": "passed",
                "resultLocator": f"{EVIDENCE_RELATIVE}#/gateResults/{index}",
            }
            for index, gate in enumerate(implementation["releaseGates"])
        ]
        release = {
            "$schema": "../schemas/release-evidence.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "subject": {
                "revision": args.revision,
                "description": "Exact product revision evaluated by the release producer.",
            },
            "provenance": {
                "kind": args.provenance_kind,
                "id": provenance_id,
                "locator": provenance_locator,
                "generatedAt": generated_at,
            },
            "decision": {
                "status": "approved",
                "decidedAt": decided_at,
                "description": "All authoritative release commands and declared release gates passed.",
            },
            "commandResults": command_results,
            "gateResults": gate_results,
        }

        atomic_write(evidence_path, json_bytes(release))
        run_validator(
            root,
            ".template-composition/validators/validate_release_evidence.py",
            "--expected-revision",
            args.revision,
        )
    except BaseException:
        atomic_write(evidence_path, original_evidence)
        raise

    print(f"Release evidence produced for {args.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
