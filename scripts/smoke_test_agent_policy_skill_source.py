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
RELEASE_PATH = ROOT / "release/toolchain.json"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SKILL_NAME = "orchestrate-repository-change"
LOCK_VERSION = "1"


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_installer() -> ModuleType:
    return load_module(INSTALLER_PATH, "skill_source_candidate_installer")


def load_installed_runtime(installed: Path) -> ModuleType:
    return load_module(
        installed / "scripts" / "runtime.py",
        "skill_source_candidate_runtime",
    )


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def require_revision(value: str) -> str:
    if FULL_SHA.fullmatch(value) is None:
        raise ValueError("skill source candidate revision must be a full lowercase commit SHA")
    return value


def consumer_configuration(toolchain: object) -> dict[str, object]:
    if not isinstance(toolchain, dict):
        raise RuntimeError("stable release toolchain must be an object")
    return {
        "schema_version": 2,
        "toolchain": toolchain,
        "contexts": {
            "coding": {
                "profiles": ["core"],
                "project_policy": {"files": []},
            }
        },
        "outputs": {
            "agents": {
                "enabled": True,
                "path": "AGENTS.md",
                "context": "coding",
                "renderer": "agents-md",
            }
        },
        "skills": {"enabled": [SKILL_NAME]},
    }


def lock_version(path: Path) -> str:
    found: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent != 0 or ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        if key != "lock_version":
            continue
        if found is not None:
            raise RuntimeError("candidate skill lock contains duplicate lock_version")
        value = raw_value.strip()
        if not value or value[0] in {'\"', "'"} or value[-1:] in {'\"', "'"}:
            raise RuntimeError("candidate skill lock_version must be a plain scalar")
        found = value
    if found is None:
        raise RuntimeError("candidate skill lock is missing lock_version")
    return found


def verify_generated_lock(
    lock: Path,
    installed: Path,
    stable_toolchain: object,
) -> None:
    if not isinstance(stable_toolchain, dict):
        raise RuntimeError("stable release toolchain must be an object")
    if lock_version(lock) != LOCK_VERSION:
        raise RuntimeError("candidate skill lock schema version is unsupported")

    runtime = load_installed_runtime(installed)
    try:
        repository, revision = runtime.lock_toolchain(lock)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"candidate skill lock toolchain is invalid: {exc}") from exc

    lock_toolchain = {
        "repository": repository,
        "revision": revision,
    }
    if lock_toolchain != stable_toolchain:
        raise RuntimeError(
            "candidate skill lock does not bind the complete stable toolchain identity"
        )


def run_installed(
    installed: Path,
    repository: Path,
    environment: dict[str, str],
    command: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(installed / "scripts" / "run.py"),
            "--repository",
            str(repository),
            command,
        ],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def require_success(result: subprocess.CompletedProcess[str], operation: str) -> None:
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout).strip()
    raise RuntimeError(
        f"candidate skill failed to {operation} through the installed stable runtime"
        + (f": {detail}" if detail else "")
    )


def run_candidate(revision: str) -> None:
    revision = require_revision(revision)
    release = load_object(RELEASE_PATH)
    stable_toolchain = release.get("toolchain")
    installer = load_installer()

    with tempfile.TemporaryDirectory(
        prefix="agent-policy-skill-source-candidate-"
    ) as temporary:
        root = Path(temporary)
        installed = root / "installed" / "agent-policy"
        archive = installer.download_archive(revision)
        installer.install_downloaded_skill(archive, installed, replace=False)

        manifest = load_object(installed / "runtime-manifest.json")
        if manifest.get("toolchain") != stable_toolchain:
            raise RuntimeError(
                "candidate skill runtime manifest does not select the stable toolchain"
            )

        repository = root / "consumer"
        repository.mkdir()
        (repository / ".git").mkdir()
        (repository / ".agent-policy.yml").write_text(
            json.dumps(consumer_configuration(stable_toolchain), indent=2) + "\n",
            encoding="utf-8",
        )

        environment = os.environ.copy()
        environment["AGENT_POLICY_RUNTIME_CACHE"] = str(root / "runtime-cache")
        require_success(
            run_installed(installed, repository, environment, "render"),
            "render",
        )

        generated = repository / ".agents" / "skills" / SKILL_NAME / "SKILL.md"
        if not generated.is_file():
            raise RuntimeError("candidate skill did not render the orchestration Skill")
        content = generated.read_text(encoding="utf-8")
        if "source-skill: orchestrate-repository-change" not in content:
            raise RuntimeError("rendered orchestration Skill lost its generated-source marker")

        lock = repository / ".agent-policy.lock"
        if not lock.is_file():
            raise RuntimeError("candidate skill render did not materialize a lock file")
        verify_generated_lock(lock, installed, stable_toolchain)

        require_success(
            run_installed(installed, repository, environment, "check"),
            "check the rendered consumer",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify an exact agent-policy skill-source candidate through remote "
            "archive download, atomic installation, stable runtime execution, and "
            "generated Skill rendering."
        )
    )
    parser.add_argument("--revision", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_candidate(args.revision)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"skill source candidate verification error: {exc}", file=sys.stderr)
        return 1
    print(f"Skill source candidate verified: {args.revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
