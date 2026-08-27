#!/usr/bin/env python3
"""Smoke-test installed Composition skill with ephemeral immutable source snapshots."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "composition"
EXPECTED_REPOSITORY = "TakashiSasaki/templates"


def clean_environment() -> dict[str, str]:
    result = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PIP_")
        and not key.upper().startswith("PYTHON")
        and not key.upper().startswith("GIT_")
    }
    result["PYTHONNOUSERSITE"] = "1"
    result["PIP_CONFIG_FILE"] = os.devnull
    result["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return result


def offline_environment(source: dict[str, str]) -> dict[str, str]:
    result = dict(source)
    blocked = "http://127.0.0.1:9"
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        result[key] = blocked
    result["NO_PROXY"] = ""
    result["no_proxy"] = ""
    return result


def run(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
) -> None:
    subprocess.run(command, env=env, cwd=cwd, check=True)


def run_json(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
) -> dict[str, object]:
    result = subprocess.run(
        command,
        env=env,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("expected JSON object from Composition runner")
    return value


def single_directory(path: Path, label: str) -> Path:
    entries = [entry for entry in path.iterdir() if entry.is_dir()]
    if len(entries) != 1:
        raise RuntimeError(f"expected one {label} cache entry, found {entries!r}")
    return entries[0]


def assert_no_source_residue(cache: Path, scratch: Path) -> None:
    source_cache = cache / "sources"
    if source_cache.exists():
        raise RuntimeError(
            f"normal consumer execution created a persistent source cache: {source_cache}"
        )
    residue = [
        path
        for path in scratch.iterdir()
        if path.name.startswith("composition-source-")
    ]
    if residue:
        raise RuntimeError(f"ephemeral Composition source residue remains: {residue!r}")


def main() -> int:
    env = clean_environment()
    manifest = json.loads((SKILL / "runtime-manifest.json").read_text(encoding="utf-8"))
    expected_revision = manifest["toolchain"]["revision"]

    with tempfile.TemporaryDirectory(prefix="composition-skill-smoke-") as temporary:
        root = Path(temporary)
        installed = root / "installed-composition"
        target = root / "consumer"
        cache = root / "runner-cache"
        validation_cache = root / "validation-cache"
        scratch = root / "scratch"
        scratch.mkdir()
        env["COMPOSITION_RUNTIME_CACHE"] = str(cache)
        env["COMPOSITION_VALIDATION_CACHE"] = str(validation_cache)
        env["TMPDIR"] = str(scratch)
        env["TMP"] = str(scratch)
        env["TEMP"] = str(scratch)
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

        run(
            [
                sys.executable,
                "-I",
                str(SKILL / "scripts" / "install.py"),
                str(installed),
            ],
            env=env,
        )
        runner = installed / "scripts" / "run.py"

        # Doctor is intentionally network-free. It must not require Git or create a
        # persistent source checkout merely to diagnose local readiness.
        doctor = run_json(
            [
                sys.executable,
                "-I",
                str(runner),
                "--repository",
                str(target),
                "doctor",
                "--format",
                "json",
            ],
            env=offline_environment(env),
            cwd=root,
        )
        if doctor["status"] != "ready":
            raise RuntimeError(f"fresh installed runner doctor was not ready: {doctor!r}")
        checks = doctor["checks"]
        if not isinstance(checks, dict):
            raise RuntimeError("doctor checks must be an object")
        if checks["git"]["status"] != "not-required":
            raise RuntimeError("normal consumer doctor still requires Git")
        if checks["source_cache"]["status"] != "ephemeral":
            raise RuntimeError("doctor did not report ephemeral source acquisition")
        if checks["package_source"]["status"] != "not-probed":
            raise RuntimeError("doctor must not claim remote/package-source availability")
        if checks["package_source"]["network_requests"] is not False:
            raise RuntimeError("doctor must not perform network requests")
        acquisition = doctor["acquisition"]
        if not isinstance(acquisition, dict):
            raise RuntimeError("doctor acquisition state must be an object")
        if acquisition["source_mode"] != "ephemeral-full-sha-archive":
            raise RuntimeError("doctor reported an unexpected source acquisition mode")
        if acquisition["runtime_mode"] != "persistent-validated-cache":
            raise RuntimeError("doctor reported an unexpected runtime cache mode")
        assert_no_source_residue(cache, scratch)
        if validation_cache.exists():
            raise RuntimeError("doctor must not acquire a validation cache")

        # Provenance is also local and network-free before the consumer exists.
        before = run_json(
            [
                sys.executable,
                "-I",
                str(runner),
                "--repository",
                str(target),
                "provenance",
            ],
            env=offline_environment(env),
            cwd=root,
        )
        before_roles = before["roles"]
        if not isinstance(before_roles, dict):
            raise RuntimeError("provenance roles must be an object")
        if before_roles["skill_source"]["status"] != "unrecorded":
            raise RuntimeError("direct local skill install must not invent a source revision")
        if before_roles["selected_toolchain"]["source"] != {
            "repository": EXPECTED_REPOSITORY,
            "revision": expected_revision,
        }:
            raise RuntimeError("provenance selected unexpected stable toolchain")
        assert_no_source_residue(cache, scratch)

        # Cold apply acquires an immutable full-SHA archive and creates only the
        # validated Python runtime cache. No templates checkout is persisted.
        run(
            [
                sys.executable,
                "-I",
                str(runner),
                "--repository",
                str(target),
                "apply",
                "--config",
                "composition.json",
            ],
            env=env,
            cwd=root,
        )
        assert_no_source_residue(cache, scratch)
        runtime_entry = single_directory(cache / "runtimes", "runtime")
        if not (runtime_entry / "runtime.json").is_file():
            raise RuntimeError("runtime cache marker is missing")

        lock = json.loads(
            (target / ".template-composition" / "lock.json").read_text(
                encoding="utf-8"
            )
        )
        source = lock["source"]
        if source != {
            "repository": EXPECTED_REPOSITORY,
            "revision": expected_revision,
        }:
            raise RuntimeError(
                f"runner materialized unexpected source identity: {source!r}"
            )

        # Warm doctor still reports source acquisition because source snapshots are
        # deliberately disposable. Runtime persistence remains a performance cache.
        warm_doctor = run_json(
            [
                sys.executable,
                "-I",
                str(runner),
                "--repository",
                str(target),
                "doctor",
                "--format",
                "json",
            ],
            env=offline_environment(env),
            cwd=root,
        )
        warm_acquisition = warm_doctor["acquisition"]
        if not isinstance(warm_acquisition, dict):
            raise RuntimeError("warm doctor acquisition state must be an object")
        if warm_acquisition["source_required"] is not True:
            raise RuntimeError("warm doctor must still require ephemeral source acquisition")
        if warm_acquisition["runtime_required"] is not False:
            raise RuntimeError("warm doctor did not recognize the persistent runtime cache")
        assert_no_source_residue(cache, scratch)

        # Normal validation reacquires source but reuses the validated runtime. The
        # product's materialized validator remains usable independently afterward.
        run(
            [
                sys.executable,
                "-I",
                str(runner),
                "--repository",
                str(target),
                "validate",
            ],
            env=env,
            cwd=root,
        )
        assert_no_source_residue(cache, scratch)

        validator = target / ".template-composition" / "validate_composition.py"
        run(
            [sys.executable, "-I", str(validator), str(target)],
            env=env,
        )

    print(
        "Composition installed-skill zero-clone runner smoke test: OK "
        f"({expected_revision})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
