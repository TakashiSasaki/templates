#!/usr/bin/env python3
"""Smoke-test remote Composition installation and stable Website bootstrap."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER_CANDIDATE = ROOT / "scripts" / "install_composition_skill.py"
RELEASE_DESCRIPTOR = ROOT / "release" / "composition-installer.json"
INSTALLATION_RECEIPT = Path("installation-receipt.json")
REQUIRED = (
    Path("SKILL.md"),
    Path("runtime-manifest.json"),
    Path("scripts/install.py"),
    Path("scripts/run.py"),
    Path("scripts/runtime.py"),
)
WEBSITE_REQUIRED_CONTRACTS = (
    Path("contracts/browser-identity.json"),
    Path("contracts/routes.json"),
    Path("contracts/viewports.json"),
    Path("contracts/site-structure.json"),
    Path("contracts/document-metadata.json"),
    Path("contracts/site-discovery.json"),
)
WEBSITE_FORBIDDEN_CONTRACTS = (
    Path("contracts/application-routes.json"),
    Path("contracts/surfaces.json"),
    Path("contracts/ui-states.json"),
)


def run(
    command: list[str],
    *,
    capture_output: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture_output,
        cwd=cwd,
    )


def require_full_sha(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RuntimeError(f"{label} must be a full lowercase Git SHA")
    return value


def require_regular_skill_files(target: Path, phase: str) -> None:
    for relative in REQUIRED:
        path = target / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"{phase} did not materialize regular file: {relative}")


def require_runner_help(target: Path, phase: str) -> None:
    result = run(
        [sys.executable, "-I", str(target / "scripts" / "run.py"), "--help"],
        capture_output=True,
    )
    if "--repository" not in result.stdout:
        raise RuntimeError(f"{phase} runner help is incomplete")


def exercise_installer_candidate(root: Path) -> None:
    """Retain candidate-installer coverage while stable bootstrap is tested below."""
    target = root / "candidate-composition"
    run([sys.executable, "-I", str(INSTALLER_CANDIDATE), str(target)])
    require_regular_skill_files(target, "remote installer candidate")

    manifest = json.loads((target / "runtime-manifest.json").read_text(encoding="utf-8"))
    revision = manifest.get("toolchain", {}).get("revision")
    require_full_sha(revision, "candidate runtime manifest revision")
    require_runner_help(target, "candidate")

    run(
        [
            sys.executable,
            "-I",
            str(INSTALLER_CANDIDATE),
            str(target),
            "--replace",
        ]
    )
    require_regular_skill_files(target, "candidate replacement")


def download_verified_stable_installer(root: Path) -> tuple[Path, dict[str, object]]:
    descriptor = json.loads(RELEASE_DESCRIPTOR.read_text(encoding="utf-8"))
    if descriptor.get("channel") != "stable":
        raise RuntimeError("Composition release descriptor is not the stable channel")

    installer = descriptor.get("installer")
    if not isinstance(installer, dict):
        raise RuntimeError("Composition release descriptor has invalid installer metadata")
    repository = installer.get("repository")
    path = installer.get("path")
    expected_sha256 = installer.get("sha256")
    if not isinstance(repository, str) or not repository:
        raise RuntimeError("stable installer repository is invalid")
    if not isinstance(path, str) or not path:
        raise RuntimeError("stable installer path is invalid")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise RuntimeError("stable installer SHA-256 is invalid")
    revision = require_full_sha(installer.get("revision"), "stable installer revision")

    url = f"https://raw.githubusercontent.com/{repository}/{revision}/{path}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "composition-stable-bootstrap-smoke/1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            "stable installer SHA-256 mismatch: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )

    target = root / "stable-install_composition_skill.py"
    target.write_bytes(data)
    return target, descriptor


def require_stable_skill_source(target: Path, descriptor: dict[str, object]) -> None:
    skill_source = descriptor.get("skill_source")
    if not isinstance(skill_source, dict):
        raise RuntimeError("Composition release descriptor has invalid skill-source metadata")
    expected_repository = skill_source.get("repository")
    expected_revision = require_full_sha(
        skill_source.get("revision"),
        "stable skill-source revision",
    )
    if not isinstance(expected_repository, str) or not expected_repository:
        raise RuntimeError("stable skill-source repository is invalid")

    receipt_path = target / INSTALLATION_RECEIPT
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise RuntimeError("stable installer did not materialize a regular installation receipt")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    source = receipt.get("source")
    if source != {
        "repository": expected_repository,
        "revision": expected_revision,
    }:
        raise RuntimeError(
            "stable installer materialized unexpected skill source: "
            f"expected {expected_repository}@{expected_revision}, got {source!r}"
        )


def require_stable_website_materialization(
    consumer: Path,
    *,
    expected_revision: str,
) -> None:
    lock_path = consumer / ".template-composition" / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    source = lock.get("source")
    if source != {
        "repository": "TakashiSasaki/templates",
        "revision": expected_revision,
    }:
        raise RuntimeError(
            f"stable Website consumer used unexpected source identity: {source!r}"
        )

    resolved_entries = lock.get("resolved_components")
    if not isinstance(resolved_entries, list):
        raise RuntimeError("stable Website lock has invalid resolved_components")
    resolved = {
        entry.get("id")
        for entry in resolved_entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    for required in ("artifact.website-core", "foundation.web"):
        if required not in resolved:
            raise RuntimeError(
                f"stable Website consumer did not resolve required component: {required}"
            )
    if "artifact.webapp-core" in resolved:
        raise RuntimeError("stable Website consumer unexpectedly resolved Webapp artifact")

    for relative in WEBSITE_REQUIRED_CONTRACTS:
        path = consumer / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(
                f"stable Website consumer did not materialize regular contract: {relative}"
            )
    for relative in WEBSITE_FORBIDDEN_CONTRACTS:
        if (consumer / relative).exists():
            raise RuntimeError(
                f"stable Website consumer materialized Webapp-private contract: {relative}"
            )


def exercise_stable_website_bootstrap(root: Path) -> str:
    target = root / "stable-composition"
    consumer = root / "website-consumer"
    config = root / "composition.json"

    stable_installer, descriptor = download_verified_stable_installer(root)
    run([sys.executable, "-I", str(stable_installer), str(target)])
    require_regular_skill_files(target, "stable remote installer")
    require_stable_skill_source(target, descriptor)
    require_runner_help(target, "stable")

    toolchain = descriptor.get("toolchain")
    if not isinstance(toolchain, dict):
        raise RuntimeError("Composition release descriptor has invalid toolchain metadata")
    expected_revision = require_full_sha(
        toolchain.get("revision"),
        "stable toolchain revision",
    )

    manifest = json.loads((target / "runtime-manifest.json").read_text(encoding="utf-8"))
    manifest_revision = manifest.get("toolchain", {}).get("revision")
    if manifest_revision != expected_revision:
        raise RuntimeError(
            "stable installed skill selected unexpected toolchain: "
            f"expected {expected_revision}, got {manifest_revision!r}"
        )

    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recipe": "website",
                "components": {"include": [], "exclude": []},
                "parameters": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    runner = target / "scripts" / "run.py"
    # Exercise the canonical stable release descriptor through its verified
    # installer and installed runner all the way to a fresh Website consumer.
    # No Website-specific revision override is supplied: the installed runtime
    # manifest selects the stable immutable toolchain for every command below.
    run(
        [
            sys.executable,
            "-I",
            str(runner),
            "--repository",
            str(consumer),
            "doctor",
            "--format",
            "json",
        ],
        cwd=root,
    )
    run(
        [
            sys.executable,
            "-I",
            str(runner),
            "--repository",
            str(consumer),
            "inspect",
        ],
        cwd=root,
    )
    run(
        [
            sys.executable,
            "-I",
            str(runner),
            "--repository",
            str(consumer),
            "plan",
            "--config",
            str(config),
        ],
        cwd=root,
    )
    run(
        [
            sys.executable,
            "-I",
            str(runner),
            "--repository",
            str(consumer),
            "apply",
            "--config",
            str(config),
        ],
        cwd=root,
    )
    require_stable_website_materialization(
        consumer,
        expected_revision=expected_revision,
    )
    run(
        [
            sys.executable,
            "-I",
            str(runner),
            "--repository",
            str(consumer),
            "validate",
        ],
        cwd=root,
    )

    run(
        [
            sys.executable,
            "-I",
            str(stable_installer),
            str(target),
            "--replace",
        ]
    )
    require_regular_skill_files(target, "stable replacement")
    require_stable_skill_source(target, descriptor)
    return expected_revision


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="composition-remote-installer-smoke-") as temporary:
        root = Path(temporary)
        exercise_installer_candidate(root)
        stable_revision = exercise_stable_website_bootstrap(root)

    print(
        "Composition remote installer candidate and stable Website bootstrap smoke test passed "
        f"({stable_revision})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
