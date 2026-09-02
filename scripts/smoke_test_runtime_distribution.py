from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_LOCK = ROOT / "requirements-runtime.lock"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_runtime_environment.py"
VERIFY_SKILL_DATA_SCRIPT = ROOT / "scripts" / "verify_runtime_skill_data.py"


def environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    supplied = os.environ if source is None else source
    result = {
        key: value
        for key, value in supplied.items()
        if not key.upper().startswith(("PIP_", "PYTHON"))
    }
    result["PYTHONNOUSERSITE"] = "1"
    result["PIP_CONFIG_FILE"] = os.devnull
    result["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return result


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def agent_policy_executable(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "agent-policy.exe"
    return venv / "bin" / "agent-policy"


def run(command: list[str], *, env: dict[str, str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    env = environment()
    try:
        with tempfile.TemporaryDirectory(prefix="agent-policy-runtime-smoke-") as temporary:
            venv = Path(temporary) / "venv"
            run([sys.executable, "-I", "-m", "venv", str(venv)], env=env)
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
                    str(RUNTIME_LOCK),
                ],
                env=env,
            )
            run(
                [
                    str(python),
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-deps",
                    str(ROOT),
                ],
                env=env,
            )
            run([str(python), "-I", "-m", "pip", "check"], env=env)
            run([str(python), "-I", str(VERIFY_SCRIPT)], env=env)
            run([str(python), "-I", str(VERIFY_SKILL_DATA_SCRIPT)], env=env)
            run([str(agent_policy_executable(venv)), "--help"], env=env)
    except subprocess.CalledProcessError as exc:
        print(
            f"Runtime distribution smoke test failed with exit status {exc.returncode}",
            file=sys.stderr,
        )
        return 1

    print("Runtime distribution smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
