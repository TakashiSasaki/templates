#!/usr/bin/env python3
"""Exercise materialized validation from a host Python without site packages."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_LOCK = ROOT / "requirements-runtime.lock"
COMPOSER = ROOT / "scripts" / "compose.py"
CACHE_OVERRIDE = "COMPOSITION_VALIDATION_CACHE"


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    expect: int = 0,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != expect:
        raise RuntimeError(
            f"command returned {result.returncode}, expected {expect}: {command!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def clean_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PIP_")
        and not key.upper().startswith("PYTHON")
    }


def parse_json_output(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"command did not emit JSON: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError("command JSON output must be an object")
    return value


def build_provider_runtime(work: Path) -> Path:
    venv = work / "provider-venv"
    run(
        [sys.executable, "-I", "-m", "venv", str(venv)],
        cwd=ROOT,
        env=clean_environment(),
    )
    python = venv_python(venv)
    run(
        [
            str(python),
            "-I",
            "-m",
            "pip",
            "install",
            "--isolated",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--no-deps",
            "--requirement",
            str(RUNTIME_LOCK),
        ],
        cwd=ROOT,
        env=clean_environment(),
    )
    run(
        [str(python), "-I", "-m", "pip", "check"],
        cwd=ROOT,
        env=clean_environment(),
    )
    return python


def materialize_webapp(work: Path, provider_python: Path) -> Path:
    config = work / "composition.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {"include": [], "exclude": []},
                "parameters": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    target = work / "consumer"
    run(
        [
            str(provider_python),
            "-I",
            str(COMPOSER),
            "apply",
            "--config",
            str(config),
            "--target",
            str(target),
        ],
        cwd=ROOT,
        env=clean_environment(),
    )
    return target


def consumer_validation(
    target: Path,
    cache: Path,
    *,
    env_updates: dict[str, str] | None = None,
    expect: int = 0,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    env = clean_environment()
    env[CACHE_OVERRIDE] = str(cache)
    if env_updates:
        env.update(env_updates)
    runner = target / ".template-composition" / "validate.py"
    result = run(
        [
            sys.executable,
            "-S",
            str(runner),
            str(target),
            "--format",
            "json",
        ],
        cwd=target,
        env=env,
        expect=expect,
    )
    return result, parse_json_output(result)


def main() -> int:
    if sys.implementation.name != "cpython":
        raise RuntimeError("smoke test requires CPython")

    with tempfile.TemporaryDirectory() as temp_dir:
        work = Path(temp_dir)
        provider_python = build_provider_runtime(work)
        target = materialize_webapp(work, provider_python)

        blocked_cache = work / "blocked-cache"
        blocked_cache.write_text("not a directory\n", encoding="utf-8")
        blocked_result, blocked = consumer_validation(
            target,
            blocked_cache,
            expect=1,
        )
        if blocked["status"] != "invalid":
            raise RuntimeError(f"blocked cache did not fail closed: {blocked}")
        blocked_checks = {check["id"]: check for check in blocked["checks"]}
        runtime_check = blocked_checks.get("validation-runtime")
        if runtime_check is None or runtime_check["status"] != "failed":
            raise RuntimeError(f"blocked cache missing runtime failure: {blocked}")
        if CACHE_OVERRIDE not in runtime_check["stderr"]:
            raise RuntimeError(f"blocked cache lacks override guidance: {runtime_check}")
        if "Traceback" in blocked_result.stderr or "Traceback" in blocked_result.stdout:
            raise RuntimeError("blocked cache leaked a raw traceback")

        cache = work / "validation-cache"
        _cold_result, cold = consumer_validation(target, cache)
        if cold["status"] != "valid":
            raise RuntimeError(f"cold materialized validation failed: {cold}")
        cold_checks = {check["id"]: check for check in cold["checks"]}
        for check_id in (
            "composition-state",
            "webapp-contracts",
            "webapp-implementation-coverage",
            "contract-evolution",
        ):
            if cold_checks.get(check_id, {}).get("status") != "passed":
                raise RuntimeError(f"cold validation check did not pass: {check_id}: {cold}")
        evidence_check = cold_checks.get("implementation-evidence")
        if evidence_check is None or evidence_check.get("status") != "passed":
            raise RuntimeError(
                f"template implementation evidence was not semantically validated: {cold}"
            )
        evidence_message = evidence_check.get("stdout", "")
        if "Implementation evidence validation: OK" not in evidence_message:
            raise RuntimeError(
                f"template implementation evidence lacks semantic validation result: {evidence_check}"
            )

        poison_proxy = "http://127.0.0.1:9"
        _warm_result, warm = consumer_validation(
            target,
            cache,
            env_updates={
                "HTTP_PROXY": poison_proxy,
                "HTTPS_PROXY": poison_proxy,
                "ALL_PROXY": poison_proxy,
                "NO_PROXY": "",
            },
        )
        if warm["status"] != "valid":
            raise RuntimeError(
                "warm validation attempted acquisition or otherwise failed with network disabled: "
                f"{warm}"
            )

        print(
            "Materialized validation verified: host site-packages hidden, "
            "cold bootstrap passed with explicit template-evidence deferral, "
            "warm cache passed without network, and unwritable-cache diagnostics are actionable."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
