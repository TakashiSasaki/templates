#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SKILL_SCRIPTS = ROOT / "skills" / "agent-policy" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

import runtime  # noqa: E402


def verify_self_host(repository_root: Path, config_file: str = ".agent-policy.yml") -> None:
    config_path = repository_root / config_file
    lock_path = repository_root / ".agent-policy.lock"
    if not config_path.is_file():
        raise FileNotFoundError(f"Missing configuration: {config_path}")
    if not lock_path.is_file():
        raise FileNotFoundError(f"Missing lockfile: {lock_path}")

    # 1. Fail closed on lock/config disagreement or malformed pin
    config_repo, config_rev = runtime.config_toolchain(config_path)
    lock_repo, lock_rev = runtime.lock_toolchain(lock_path)
    if (config_repo, config_rev) != (lock_repo, lock_rev):
        raise ValueError(
            f"Configuration toolchain ({config_repo}@{config_rev}) "
            f"does not match lock toolchain ({lock_repo}@{lock_rev})"
        )

    # 2. Establish runtime identity using existing repository-pinned Skill machinery
    pin, runtime_path = runtime.runtime_selection(repository_root)
    if pin.revision != lock_rev:
        raise ValueError(f"Selected runtime pin {pin.revision} does not match lock {lock_rev}")

    # 3. Execute check command via the adopted immutable runtime
    command = [
        *runtime.cli_command(runtime_path),
        "--repository",
        str(repository_root),
        "check",
        "--config",
        config_file,
    ]
    env = runtime.sanitized_environment()
    result = subprocess.run(
        command,
        cwd=repository_root,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(
            f"Self-host check failed against adopted toolchain {pin.revision}:\n{output}"
        )


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify adopted Policy self-host consistency.")
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--config", default=".agent-policy.yml")
    args = parser.parse_args(arguments)
    try:
        verify_self_host(args.repository.resolve(), args.config)
        print(f"POLICY_SELF_HOST_PASS repository={args.repository.resolve()}")
        return 0
    except Exception as exc:
        print(f"POLICY_SELF_HOST_FAIL error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
