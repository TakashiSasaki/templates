#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_PROTOCOL_REVISION = "3ae5d1e60c65e7a8ebf5f9af0436044484e42983"
SITE_PROTOCOL_SOURCE = "scripts/publication_contract.py"


def clean_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PIP_") and not key.startswith("PYTHON")
    }
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def run(arguments: list[str], *, cwd: Path, environment: dict[str, str]) -> None:
    print("+", " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=cwd, env=environment, check=True)


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def read_site_protocol() -> bytes:
    reference = f"{SITE_PROTOCOL_REVISION}:{SITE_PROTOCOL_SOURCE}"
    try:
        return subprocess.check_output(["git", "show", reference], cwd=ROOT)
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "fetch", "--no-tags", "origin", SITE_PROTOCOL_REVISION],
            cwd=ROOT,
            check=True,
        )
        return subprocess.check_output(["git", "show", reference], cwd=ROOT)


def main() -> int:
    environment = clean_environment()
    worktree: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="policy-docs-smoke-") as temporary:
            temporary_root = Path(temporary)
            worktree = temporary_root / "repository"
            run(
                ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
                cwd=ROOT,
                environment=environment,
            )
            protocol = temporary_root / "site-publication-protocol.py"
            protocol.write_bytes(read_site_protocol())
            venv = temporary_root / "venv"
            run(
                [sys.executable, "-I", "-m", "venv", str(venv)],
                cwd=ROOT,
                environment=environment,
            )
            python = venv_python(venv)
            run(
                [
                    str(python),
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-deps",
                    "--requirement",
                    str(worktree / "requirements-docs.lock"),
                ],
                cwd=worktree,
                environment=environment,
            )
            documentation_environment = dict(environment)
            documentation_environment.update(
                {
                    "BUILD_COMMIT": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=worktree, text=True
                    ).strip(),
                    "BUILD_REPOSITORY": "TakashiSasaki/templates",
                    "BUILD_RUN_ID": "local-preflight",
                    "BUILD_RUN_NUMBER": "0",
                    "POLICY_DOCS_ENV_READY": "1",
                    "SITE_PUBLICATION_PROTOCOL": str(protocol),
                }
            )
            run(
                [
                    str(python),
                    "scripts/run_policy_preflight.py",
                    "--check",
                    "docs",
                ],
                cwd=worktree,
                environment=documentation_environment,
            )
    except subprocess.CalledProcessError as exc:
        print(
            f"Policy documentation smoke test failed with exit status {exc.returncode}",
            file=sys.stderr,
        )
        return 1
    finally:
        if worktree is not None and worktree.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=ROOT,
                env=environment,
                check=False,
            )
    print("Policy documentation smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
