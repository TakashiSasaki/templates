#!/usr/bin/env python3
"""Smoke-test installed Composition skill acquisition, provenance, and offline cache reuse."""

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
        env["COMPOSITION_RUNTIME_CACHE"] = str(cache)
        env["COMPOSITION_VALIDATION_CACHE"] = str(validation_cache)
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
        if before_roles["consumer_lock"]["status"] != "absent":
            raise RuntimeError("unmanaged consumer unexpectedly reported a lock")
        if cache.exists():
            raise RuntimeError("provenance must not acquire a source or runtime cache")
        if validation_cache.exists():
            raise RuntimeError("provenance must not acquire a validation cache")

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

        after = run_json(
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
        after_roles = after["roles"]
        if not isinstance(after_roles, dict):
            raise RuntimeError("provenance roles must be an object")
        if after_roles["consumer_lock"]["source"] != source:
            raise RuntimeError("provenance did not report the materialized lock source")
        relationships = after["relationships"]
        if not isinstance(relationships, dict):
            raise RuntimeError("provenance relationships must be an object")
        if relationships["consumer_lock_matches_selected"] is not True:
            raise RuntimeError("provenance did not correlate lock and selected toolchain")

        source_entry = single_directory(cache / "sources", "source")
        runtime_entry = single_directory(cache / "runtimes", "runtime")
        if source_entry.name != expected_revision:
            raise RuntimeError(
                f"source cache key does not match stable revision: {source_entry.name}"
            )
        if not (source_entry / "source.json").is_file():
            raise RuntimeError("source cache marker is missing")
        if not (runtime_entry / "runtime.json").is_file():
            raise RuntimeError("runtime cache marker is missing")

        # Warm validation while network access is available. Toolchain generations
        # before self-contained validation do not create COMPOSITION_VALIDATION_CACHE;
        # generations that do must leave a validated runtime marker.
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
        validation_runtimes = validation_cache / "runtimes"
        if validation_runtimes.exists():
            validation_runtime_entry = single_directory(
                validation_runtimes, "validation runtime"
            )
            if not (validation_runtime_entry / "runtime.json").is_file():
                raise RuntimeError("validation runtime cache marker is missing")

        # After one successful online validation, the selected toolchain generation
        # must validate again with network acquisition disabled. For generations with
        # self-contained validation this proves validation-cache reuse; for older
        # generations it preserves the existing runner-cache offline assertion.
        run(
            [
                sys.executable,
                "-I",
                str(runner),
                "--repository",
                str(target),
                "validate",
            ],
            env=offline_environment(env),
            cwd=root,
        )

        validator = target / ".template-composition" / "validate_composition.py"
        run(
            [sys.executable, "-I", str(validator), str(target)],
            env=env,
        )

    print(
        "Composition installed-skill runner cache/provenance smoke test: OK "
        f"({expected_revision})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
