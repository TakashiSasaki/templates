#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "scripts/install_agent_policy_skill.py"
SKILL_SOURCE_SMOKE_PATH = ROOT / "scripts/smoke_test_agent_policy_skill_source.py"
RELEASE_PATH = ROOT / "release/toolchain.json"
TOOLCHAIN_REPOSITORY = "TakashiSasaki/templates"
INSTALLER_REPOSITORY_PATH = "scripts/install_agent_policy_skill.py"
EXPECTED_SKILL_SOURCE_REVISION = "a7b260ccc361ad8cd1bab94803a9b355c640fe7e"
SKILL_SOURCE_PATH = "skills/agent-policy"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_installer() -> ModuleType:
    return load_module(INSTALLER_PATH, "installer_candidate_installer")


def load_skill_source_smoke() -> ModuleType:
    return load_module(SKILL_SOURCE_SMOKE_PATH, "installer_candidate_skill_source_smoke")


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def require_revision(value: str) -> str:
    if FULL_SHA.fullmatch(value) is None:
        raise ValueError(
            "installer candidate revision must be a full lowercase commit SHA"
        )
    return value


def raw_installer_url(revision: str) -> str:
    revision = require_revision(revision)
    return (
        "https://raw.githubusercontent.com/"
        f"{TOOLCHAIN_REPOSITORY}/{revision}/{INSTALLER_REPOSITORY_PATH}"
    )


def remote_installer_command(
    revision: str,
    target: Path,
    attestation: Path,
) -> list[str]:
    revision = require_revision(revision)
    url = raw_installer_url(revision)
    bootstrap = (
        "import urllib.request; "
        f"exec(urllib.request.urlopen({url!r}, timeout=30).read())"
    )
    return [
        sys.executable,
        "-I",
        "-c",
        bootstrap,
        str(target),
        "--installer-revision",
        revision,
        "--attestation",
        str(attestation),
    ]


def require_success(result: subprocess.CompletedProcess[str], operation: str) -> None:
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout).strip()
    raise RuntimeError(
        f"installer candidate failed to {operation}" + (f": {detail}" if detail else "")
    )


def verify_attestation_identity(
    attestation: Path,
    installer_revision: str,
) -> None:
    value = load_object(attestation)
    if value.get("installer") != {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": installer_revision,
        "path": INSTALLER_REPOSITORY_PATH,
    }:
        raise RuntimeError(
            "installer candidate attestation has the wrong installer identity"
        )
    if value.get("skill_source") != {
        "repository": TOOLCHAIN_REPOSITORY,
        "revision": EXPECTED_SKILL_SOURCE_REVISION,
        "path": SKILL_SOURCE_PATH,
    }:
        raise RuntimeError(
            "installer candidate attestation has the wrong skill-source identity"
        )


def verify_installed_consumer_path(
    installed: Path,
    root: Path,
    skill_smoke: ModuleType,
) -> None:
    release = load_object(RELEASE_PATH)
    stable_toolchain = release.get("toolchain")
    manifest = load_object(installed / "runtime-manifest.json")
    if manifest.get("toolchain") != stable_toolchain:
        raise RuntimeError(
            "installer candidate installed skill does not select the stable toolchain"
        )

    repository = root / "consumer"
    repository.mkdir()
    (repository / ".git").mkdir()
    configuration = skill_smoke.consumer_configuration(stable_toolchain)
    (repository / ".agent-policy.yml").write_text(
        json.dumps(configuration, indent=2) + "\n",
        encoding="utf-8",
    )

    environment = os.environ.copy()
    environment["AGENT_POLICY_RUNTIME_CACHE"] = str(root / "runtime-cache")
    skill_smoke.require_success(
        skill_smoke.run_installed(installed, repository, environment, "render"),
        "render",
    )

    generated = (
        repository
        / ".agents"
        / "skills"
        / skill_smoke.SKILL_NAME
        / "SKILL.md"
    )
    if not generated.is_file():
        raise RuntimeError("installer candidate did not render the orchestration Skill")
    if "source-skill: orchestrate-repository-change" not in generated.read_text(
        encoding="utf-8"
    ):
        raise RuntimeError("installer candidate rendered Skill lost its source marker")

    lock = repository / ".agent-policy.lock"
    if not lock.is_file():
        raise RuntimeError("installer candidate render did not materialize a lock file")
    skill_smoke.verify_generated_lock(lock, installed, stable_toolchain)

    skill_smoke.require_success(
        skill_smoke.run_installed(installed, repository, environment, "check"),
        "check the rendered consumer",
    )


def run_candidate(installer_revision: str) -> None:
    installer_revision = require_revision(installer_revision)
    installer = load_installer()
    if installer.SKILL_SOURCE_REVISION != EXPECTED_SKILL_SOURCE_REVISION:
        raise RuntimeError(
            "installer candidate does not embed the qualified skill-source revision"
        )
    skill_smoke = load_skill_source_smoke()

    with tempfile.TemporaryDirectory(
        prefix="agent-policy-installer-candidate-"
    ) as temporary:
        root = Path(temporary)
        installed = root / "installed" / "agent-policy"
        attestation = root / "trust" / "agent-policy-installation.json"

        result = subprocess.run(
            remote_installer_command(installer_revision, installed, attestation),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        require_success(result, "execute the exact remote installer")

        installer.verify_installation_attestation(
            installed,
            attestation,
            installer_revision=installer_revision,
        )
        verify_attestation_identity(attestation, installer_revision)
        verify_installed_consumer_path(installed, root, skill_smoke)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify an exact remote installer candidate through immutable script fetch, "
            "external attestation, qualified skill-source installation, stable runtime "
            "execution, and orchestration Skill rendering."
        )
    )
    parser.add_argument("--installer-revision", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_candidate(args.installer_revision)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"installer candidate verification error: {exc}", file=sys.stderr)
        return 1
    print(f"Installer candidate verified: {args.installer_revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
