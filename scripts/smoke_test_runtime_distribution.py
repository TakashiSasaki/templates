#!/usr/bin/env python3
"""Build and exercise the Composer consumer runtime in a fresh virtual environment."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_LOCK = SOURCE_ROOT / "requirements-runtime.lock"
RUNTIME_VERIFIER = SOURCE_ROOT / "scripts" / "verify_runtime_environment.py"
COMPOSER = SOURCE_ROOT / "scripts" / "compose.py"


def sanitized_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    supplied = os.environ if source is None else source
    result = {
        key: value
        for key, value in supplied.items()
        if not key.upper().startswith("PIP_")
        and not key.upper().startswith("PYTHON")
    }
    result["PYTHONNOUSERSITE"] = "1"
    result["PIP_CONFIG_FILE"] = os.devnull
    result["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return result


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def run(command: list[str], *, env: Mapping[str, str]) -> None:
    subprocess.run(
        command,
        cwd=SOURCE_ROOT,
        env=dict(env),
        check=True,
    )


def main() -> int:
    if shutil.which("git") is None:
        raise RuntimeError("Composer consumer runtime requires Git on PATH")
    if not RUNTIME_LOCK.is_file():
        raise RuntimeError("requirements-runtime.lock is missing")

    env = sanitized_environment()
    with tempfile.TemporaryDirectory(prefix="composition-runtime-smoke-") as temporary:
        root = Path(temporary)
        runtime = root / "venv"
        run([sys.executable, "-I", "-m", "venv", str(runtime)], env=env)
        python = venv_python(runtime)
        run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--isolated",
                "--disable-pip-version-check",
                "--no-deps",
                "--requirement",
                str(RUNTIME_LOCK),
            ],
            env=env,
        )
        run([str(python), "-I", "-m", "pip", "check"], env=env)
        run([str(python), "-I", str(RUNTIME_VERIFIER)], env=env)
        run([str(python), "-I", str(COMPOSER), "--help"], env=env)

        config = root / "composition.json"
        config.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": "skill",
                    "components": {"include": [], "exclude": []},
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        target = root / "consumer"
        run(
            [str(python), "-I", str(COMPOSER), "inspect", "--target", str(target)],
            env=env,
        )
        run(
            [
                str(python),
                "-I",
                str(COMPOSER),
                "plan",
                "--config",
                str(config),
                "--target",
                str(target),
            ],
            env=env,
        )
        run(
            [
                str(python),
                "-I",
                str(COMPOSER),
                "apply",
                "--config",
                str(config),
                "--target",
                str(target),
            ],
            env=env,
        )
        run(
            [str(python), "-I", str(COMPOSER), "validate", "--target", str(target)],
            env=env,
        )

    print("Composer consumer runtime smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
