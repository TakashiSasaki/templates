#!/usr/bin/env python3
"""Produce a digest-closed release bundle for approved revision-bound evidence."""
from __future__ import annotations

import sys

if not sys.flags.isolated:
    print("release bundle producer requires Python isolated mode (-I)", file=sys.stderr)
    raise SystemExit(2)
sys.dont_write_bytecode = True

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
LIFECYCLE_LOCK_PATH = HERE / "lifecycle_lock.py"
EVIDENCE_RELATIVE = "contracts/release-evidence.json"
BUNDLE_RELATIVE = "contracts/release-bundle.json"
LIFECYCLE_OUTPUTS = frozenset({EVIDENCE_RELATIVE, BUNDLE_RELATIVE})


def load_managed_module(name: str, path: Path, label: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load managed {label}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


candidate = load_managed_module(
    "composition_release_candidate",
    CANDIDATE_PATH,
    "candidate verification helper",
)
lifecycle_lock = load_managed_module(
    "composition_release_lifecycle_lock",
    LIFECYCLE_LOCK_PATH,
    "release lifecycle lock helper",
)


def fail(message: str, *, code: int = 2) -> None:
    print(f"release bundle producer failed: {message}", file=sys.stderr)
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


def validator_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("PYTHON"):
            del environment[name]
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def run_validator(root: Path, relative: str, *arguments: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-B", str(root / relative), str(root), *arguments],
        cwd=root,
        env=validator_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip()
        fail(f"release bundle precondition/validation failed: {diagnostic}")


def verify_candidate(root: Path, revision: str, *, context: str) -> None:
    try:
        candidate.verify_candidate(
            root,
            revision,
            allowed_modified=LIFECYCLE_OUTPUTS,
        )
    except candidate.CandidateError as exc:
        fail(f"{context}: {exc}")


def verify_unchanged(path: Path, expected: bytes, *, label: str) -> None:
    try:
        current = path.read_bytes()
    except OSError as exc:
        fail(f"cannot read {label}: {exc}")
    if current != expected:
        fail(f"{label} changed during bundle production")


def timestamp_ns(value: str) -> int:
    if not isinstance(value, str) or not value.endswith("Z"):
        fail("release evidence generatedAt must be a UTC timestamp")
    text = value[:-1]
    if "." in text:
        whole, fraction = text.split(".", 1)
    else:
        whole, fraction = text, ""
    if len(fraction) > 9 or (fraction and not fraction.isdigit()):
        fail("release evidence generatedAt has invalid fractional seconds")
    try:
        base = datetime.strptime(whole, "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        fail(f"release evidence generatedAt is invalid: {exc}")
    return int(base.timestamp()) * 1_000_000_000 + int(fraction.ljust(9, "0") or "0")


def timestamp_after(reference_ns: int) -> str:
    current_ns = max(time.time_ns(), reference_ns + 1)
    seconds, nanoseconds = divmod(current_ns, 1_000_000_000)
    whole = datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{whole}.{nanoseconds:09d}Z"


def artifact_inventory(root: Path, manifest: dict) -> list[dict[str, str]]:
    entries = manifest.get("contracts")
    if not isinstance(entries, list):
        fail("contract manifest contracts must be an array")
    artifacts: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            fail(f"contract manifest entry {index} must be an object")
        contract_id = entry.get("id")
        document = entry.get("document")
        if not isinstance(contract_id, str) or not contract_id:
            fail(f"contract manifest entry {index} requires id")
        if contract_id == "release_bundle":
            continue
        if not isinstance(document, str) or not document:
            fail(f"contract manifest entry {contract_id} requires document")
        try:
            path = candidate.ensure_output_path(root, document)
        except candidate.CandidateError as exc:
            fail(f"unsafe bundle artifact path {document!r}: {exc}")
        if not path.is_file():
            fail(f"bundle artifact is missing: {document}")
        artifacts.append(
            {
                "contractId": contract_id,
                "path": document,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return artifacts


def produce_locked(root: Path, args: argparse.Namespace) -> int:
    try:
        evidence_path = candidate.ensure_output_path(root, EVIDENCE_RELATIVE)
        bundle_path = candidate.ensure_output_path(root, BUNDLE_RELATIVE)
    except candidate.CandidateError as exc:
        fail(str(exc))
    try:
        original_evidence = evidence_path.read_bytes()
        original_bundle = bundle_path.read_bytes()
    except OSError as exc:
        fail(f"cannot snapshot release lifecycle outputs: {exc}")

    try:
        verify_candidate(
            root,
            args.revision,
            context="candidate is not ready for bundle production",
        )
        run_validator(
            root,
            ".template-composition/validators/validate_release_evidence.py",
            "--expected-revision",
            args.revision,
        )
        verify_unchanged(
            evidence_path,
            original_evidence,
            label="approved release evidence",
        )
        verify_unchanged(
            bundle_path,
            original_bundle,
            label="canonical release bundle",
        )

        release = load_json(evidence_path)
        if release.get("mode") != "product":
            fail("release evidence must be in product mode")
        if release.get("decision", {}).get("status") != "approved":
            fail("release evidence must be approved")
        generated_at = release.get("provenance", {}).get("generatedAt")
        release_generated_ns = timestamp_ns(generated_at)

        manifest = load_json(root / "contracts/manifest.json")
        artifacts = artifact_inventory(root, manifest)
        verify_unchanged(
            evidence_path,
            original_evidence,
            label="approved release evidence",
        )
        verify_unchanged(
            bundle_path,
            original_bundle,
            label="canonical release bundle",
        )
        verify_candidate(
            root,
            args.revision,
            context="candidate changed while bundle inputs were collected",
        )

        provenance_id = args.provenance_id or f"bundle-{args.revision[:12]}"
        provenance_locator = args.provenance_locator or BUNDLE_RELATIVE
        bundle = {
            "$schema": "../schemas/release-bundle.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "subject": {
                "revision": args.revision,
                "description": "Exact product revision with approved digest-closed release contracts.",
            },
            "provenance": {
                "kind": args.provenance_kind,
                "id": provenance_id,
                "locator": provenance_locator,
                "generatedAt": timestamp_after(release_generated_ns),
            },
            "handoff": {
                "status": "ready",
                "description": "All active registered release contract bytes are digest-closed.",
            },
            "artifacts": artifacts,
        }

        atomic_write(bundle_path, json_bytes(bundle))
        verify_candidate(
            root,
            args.revision,
            context="candidate changed during bundle production",
        )
        verify_unchanged(
            evidence_path,
            original_evidence,
            label="approved release evidence",
        )
        run_validator(
            root,
            ".template-composition/validators/validate_release_bundle.py",
            "--expected-revision",
            args.revision,
        )
    except BaseException:
        atomic_write(bundle_path, original_bundle)
        raise

    print(f"Release bundle produced for {args.revision}")
    return 0


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
        with lifecycle_lock.release_lifecycle_lock(root):
            return produce_locked(root, args)
    except lifecycle_lock.ReleaseLifecycleLockError as exc:
        fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
