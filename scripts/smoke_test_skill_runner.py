#!/usr/bin/env python3
"""Smoke-test the installed Composition skill runner against its stable full-SHA source."""

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


def run(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path | None = None,
) -> None:
    subprocess.run(command, env=env, cwd=cwd, check=True)


def main() -> int:
    env = clean_environment()
    manifest = json.loads((SKILL / "runtime-manifest.json").read_text(encoding="utf-8"))
    expected_revision = manifest["toolchain"]["revision"]

    with tempfile.TemporaryDirectory(prefix="composition-skill-smoke-") as temporary:
        root = Path(temporary)
        installed = root / "installed-composition"
        target = root / "consumer"
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

        validator = target / ".template-composition" / "validate_composition.py"
        run(
            [sys.executable, "-I", str(validator), str(target)],
            env=env,
        )

    print(
        "Composition installed-skill runner smoke test: OK "
        f"({expected_revision})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
