from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from ..config import load_config, validate_config
from ..lockfile import load_lock, resolve_lock_path
from ..paths import resolve_inside

GUIDANCE_SCRIPT = ".agents/skills/policy-guidance/scripts/policy_guidance.py"


def _validate_execution_surface(
    repository_root: Path,
    *,
    config_path: str,
    script: str,
    bundle: str | None,
    runtime_revision: str | None,
) -> tuple[bytes, str]:
    config = load_config(repository_root, config_path)
    errors = [
        item for item in validate_config(repository_root, config) if item.level == "error"
    ]
    if errors:
        rendered = "; ".join(f"{item.code}: {item.message}" for item in errors)
        raise ValueError(f"configuration is invalid: {rendered}")

    staged_outputs = [
        item
        for item in config.output_specs
        if item.enabled and item.renderer == "agents-md-staged"
    ]
    if len(staged_outputs) != 1 or staged_outputs[0].detail_bundle_path is None:
        raise ValueError(
            "guidance requires exactly one enabled agents-md-staged output"
        )
    expected_bundle = staged_outputs[0].detail_bundle_path
    if bundle is None:
        bundle = expected_bundle
    if bundle != expected_bundle:
        raise ValueError("guidance bundle does not match the enabled staged output")

    script_path = resolve_inside(repository_root, script, allow_missing=False)
    script_relative = script_path.relative_to(repository_root.resolve()).as_posix()
    if script_relative != GUIDANCE_SCRIPT:
        raise ValueError("guidance script is not the generated policy-guidance script")
    if (
        script_path.is_symlink()
        or not script_path.is_file()
        or script_path.stat(follow_symlinks=False).st_nlink != 1
    ):
        raise ValueError("guidance script must be a regular unlinked Python file")

    lock_path = resolve_lock_path(repository_root, allow_missing=False)
    lock = load_lock(lock_path)
    if runtime_revision is not None:
        if runtime_revision != lock["toolchain"]["revision"]:
            raise ValueError(
                "selected runtime revision does not match the repository lock"
            )
    expected_digest = lock["outputs"].get(script_relative)
    script_bytes = script_path.read_bytes()
    if (
        not isinstance(expected_digest, str)
        or hashlib.sha256(script_bytes).hexdigest() != expected_digest
    ):
        raise ValueError("guidance script does not match the generated-output lock")

    from . import check as check_command

    check_errors = [
        item
        for item in check_command.run(repository_root, config.relative_path)
        if item.level == "error"
    ]
    if check_errors:
        rendered = "; ".join(f"{item.code}: {item.message}" for item in check_errors)
        raise ValueError(f"generated policy outputs are stale: {rendered}")

    return script_bytes, bundle


def run(
    repository_root: Path,
    *,
    config_path: str,
    script: str,
    bundle: str | None,
    runtime_revision: str | None,
    operation: str | None,
    rule_id: str | None,
    all_rules: bool,
    output_format: str,
) -> int:
    try:
        script_bytes, bundle = _validate_execution_surface(
            repository_root,
            config_path=config_path,
            script=script,
            bundle=bundle,
            runtime_revision=runtime_revision,
        )
        # Execute authenticated bytes rather than reopening the mutable path
        # after validation, which also closes the check-to-use race.
        code = (
            "import sys\n"
            "filename = sys.argv[0]\n"
            "namespace = {'__name__': '__main__', '__file__': filename}\n"
            "exec(compile(sys.stdin.buffer.read(), filename, 'exec'), namespace)\n"
        )
        command = [
            sys.executable,
            "-I",
            "-c",
            code,
            "--root",
            str(repository_root),
            f"--config={config_path}",
        ]
        if bundle is not None:
            command.append(f"--bundle={bundle}")
        if runtime_revision is not None:
            command.append(f"--runtime-revision={runtime_revision}")
        if operation is not None:
            command.extend(["--operation", operation])
        if rule_id is not None:
            command.extend(["--rule-id", rule_id])
        if all_rules:
            command.append("--all")
        command.extend(["--format", output_format])
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        return subprocess.run(
            command,
            cwd=repository_root,
            env=environment,
            input=script_bytes,
            check=False,
        ).returncode
    except (OSError, ValueError) as exc:
        print(f"agent-policy guidance error: {exc}", file=sys.stderr)
        return 2
