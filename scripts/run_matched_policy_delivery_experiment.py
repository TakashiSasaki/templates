#!/usr/bin/env python3
"""Run matched clean-consumer full-text (A) and staged (C) trials.

This runner keeps the policy inputs and task prompt identical within each
pair, installs one exact wheel into isolated consumers, invokes fresh Codex
processes, and writes only redacted summaries to the requested record.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

POLICY_FILES = (
    "repository-policy/authority-boundary.md",
    "repository-policy/history-boundary.md",
    "repository-policy/architecture-decisions.md",
    "repository-policy/release-trust.md",
    "repository-policy/toolchain-safety.md",
    "repository-policy/maintainer-validation.md",
    "repository-policy/maintainer-merge-routing.md",
    "repository-policy/documentation-boundary.md",
)
PROFILES = ("core", "security-baseline", "pull-request", "progressive-discovery")
MODEL = "gpt-reserve"
EFFORT = "xhigh"
GUIDANCE = re.compile(r"policy_guidance\.py")
OPERATION = re.compile(r"--operation(?:=|\s+)([\w-]+)")
RULE_ID = re.compile(r"rule ID:\s*([^\s|]+)")
FORBIDDEN = re.compile(r"(?:^|[;&|\s])(?:gh\b|curl\b|wget\b|git\s+(?:push|pull|merge|rebase)\b)")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
REVIEW_HEAD = "1" * 40
REVIEW_BASE = "2" * 40
REVIEW_EFFECTIVE_BASE = "3" * 40

TASK_PROMPTS = {
    "generated-artifact": (
        "In this disposable repository, add gamma to source/catalog.json. "
        "The generated/catalog.json file is derived output and must not be edited "
        "directly. Update the source, run scripts/generate_catalog.py, then run "
        "scripts/check_catalog.py. Work locally only; do not use network access, "
        "git push, merge, or review commands. Finish with the generated output "
        "and check passing."
    ),
    "code-repair": (
        "Repair the deterministic average() defect. Add a regression proving "
        "average([1, 3, 5]) == 3.0, run tests/test_calculator.py, and leave the "
        "implementation and regression passing. Work locally only; do not use "
        "network access, git push, merge, or review commands."
    ),
    "review-preparation": (
        "Prepare the local review-qualification handoff. Follow applicable review "
        "guidance before the review operation, validate candidate/evidence.json "
        "with scripts/validate_evidence.py, and write review-preparation.txt as "
        "strict key=value lines for repository, pull_request, head, base, "
        "effective_base, ci_state, ci_head, review_state, review_head, and "
        "next_safe_action. Use the validated values and do not omit any key. "
        "Do not post comments, call gh, merge, push, or use the network."
    ),
}


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable(value: Any) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def run(argv: list[str], cwd: Path, *, env: dict[str, str] | None = None,
        timeout: int | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                            text=True, timeout=timeout, check=False)
    if check and result.returncode:
        raise RuntimeError(f"{argv!r} failed: {result.stderr[-2000:]}")
    return result


def setup_task(root: Path, task: str) -> None:
    if task == "generated-artifact":
        write(root / "source/catalog.json", '{\n  "items": ["alpha", "beta"]\n}\n')
        write(
            root / "generated/catalog.json",
            '{\n  "generated_by": "scripts/generate_catalog.py",\n'
            '  "items": ["alpha", "beta"]\n}\n',
        )
        write(root / "scripts/generate_catalog.py", '''from __future__ import annotations
import json
import os
from pathlib import Path
root = Path(__file__).parents[1]
items = json.loads((root / "source/catalog.json").read_text())["items"]
(root / "generated/catalog.json").write_text(json.dumps(
    {"generated_by": "scripts/generate_catalog.py", "items": sorted(items)}, indent=2
) + "\\n")
trace = os.environ.get("POLICY_EXPERIMENT_TRACE")
if trace:
    path = Path(trace)
    path.write_text((path.read_text() if path.exists() else "") + "generate_catalog.py\\n")
''')
        write(root / "scripts/check_catalog.py", '''from __future__ import annotations
import json
from pathlib import Path
root = Path(__file__).parents[1]
source = json.loads((root / "source/catalog.json").read_text())["items"]
generated = json.loads((root / "generated/catalog.json").read_text())
assert generated == {"generated_by": "scripts/generate_catalog.py", "items": sorted(source)}
print("catalog check passed")
''')
    elif task == "code-repair":
        write(root / "src/calculator.py",
              "def average(values: list[float]) -> float:\n"
              "    return sum(values) / (len(values) + 1)\n")
        write(root / "tests/test_calculator.py", '''from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from calculator import average
class AverageTests(unittest.TestCase):
    def test_single_value(self) -> None:
        self.assertEqual(average([4]), 4.0)
if __name__ == "__main__":
    unittest.main()
''')
    elif task == "review-preparation":
        write(root / "candidate/evidence.json", json.dumps({
            "repository": "fixture/review-preparation", "pull_request": 42,
            "head": REVIEW_HEAD, "base": REVIEW_BASE,
            "effective_base": REVIEW_EFFECTIVE_BASE,
            "ci": {"state": "success", "head": REVIEW_HEAD},
            "review": {"state": "completed", "head": REVIEW_HEAD},
        }, indent=2) + "\n")
        write(root / "scripts/validate_evidence.py", '''from __future__ import annotations
import json
from pathlib import Path
data = json.loads(Path(__file__).parents[1].joinpath("candidate/evidence.json").read_text())
assert data["head"] == "1" * 40
assert data["base"] == "2" * 40
assert data["effective_base"] == "3" * 40
assert data["ci"] == {"state": "success", "head": "1" * 40}
assert data["review"] == {"state": "completed", "head": "1" * 40}
print("evidence is applicable")
''')
    else:
        raise ValueError(task)


def write_config(root: Path, condition: str, revision: str) -> None:
    files = "\n".join(f"        - {path}" for path in POLICY_FILES)
    profiles = "\n".join(f"      - {profile}" for profile in PROFILES)
    if condition == "A":
        output = ("  agents:\n    enabled: true\n    path: AGENTS.md\n"
                  "    context: coding\n    renderer: agents-md\n")
        skills = "  enabled: []\n"
    else:
        output = ("  agents:\n    enabled: true\n    path: AGENTS.md\n"
                  "    detail_bundle: .agent-policy/preview/policy-details.json\n"
                  "    context: coding\n    renderer: agents-md-staged\n")
        skills = "  enabled:\n    - policy-guidance\n"
    write(root / ".agent-policy.yml", f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {revision}
contexts:
  coding:
    profiles:
{profiles}
    project_policy:
      files:
{files}
outputs:
{output}skills:
{skills}""")


def env_for(python: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    return env


def git_baseline(root: Path) -> None:
    run(["git", "init", "-q"], root)
    run(["git", "config", "user.email", "experiment@example.invalid"], root)
    run(["git", "config", "user.name", "Policy experiment"], root)
    run(["git", "add", "."], root)
    run(["git", "commit", "-qm", "fixture baseline"], root)


def skill_tree_manifest(skill_root: Path) -> dict[str, str]:
    """Return a deterministic manifest of the executable Skill source tree."""

    skill_root = skill_root.resolve()
    if not skill_root.is_dir() or skill_root.is_symlink():
        raise RuntimeError(f"candidate Skill root is not a regular directory: {skill_root}")
    files: dict[str, str] = {}
    for path in sorted(skill_root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"candidate Skill source contains a symlink: {path}")
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(skill_root).as_posix()
        files[relative] = sha(path.read_bytes())
    if not files:
        raise RuntimeError(f"candidate Skill root is empty: {skill_root}")
    return files


def resolve_candidate_skill(provider_root: Path) -> tuple[Path, dict[str, Any]]:
    provider_root = provider_root.resolve()
    skill_root = provider_root / "skills/agent-policy"
    try:
        skill_root.relative_to(provider_root)
    except ValueError as exc:
        raise RuntimeError("candidate Skill path escaped provider root") from exc
    files = skill_tree_manifest(skill_root)
    return skill_root, {
        "source_path": skill_root.relative_to(provider_root).as_posix(),
        "file_sha256": files,
        "tree_sha256": stable(files),
    }


def candidate_package_manifest(provider_root: Path) -> dict[str, str]:
    """Map every wheel payload file to the exact candidate source bytes."""

    source_roots = [(provider_root / "src/agent_policy", "agent_policy")]
    for directory in ("schemas", "profiles", "policy", "templates", "skills", "delivery"):
        source_roots.append((provider_root / directory, f"agent_policy/_data/{directory}"))

    manifest: dict[str, str] = {}
    for source_root, wheel_root in source_roots:
        if not source_root.is_dir() or source_root.is_symlink():
            raise RuntimeError(
                "candidate package source is missing or not a directory: "
                f"{source_root}"
            )
        for path in sorted(source_root.rglob("*")):
            if path.is_symlink():
                raise RuntimeError(f"candidate package source contains a symlink: {path}")
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(source_root).as_posix()
            manifest[f"{wheel_root}/{relative}"] = sha(path.read_bytes())
    if not manifest:
        raise RuntimeError("candidate package source is empty")
    return manifest


def _wheel_payload_manifest(wheel: Path) -> dict[str, str]:
    """Read only regular, non-metadata wheel members into a content manifest."""

    if not wheel.is_file() or wheel.is_symlink():
        raise RuntimeError(f"candidate wheel is not a regular file: {wheel}")
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts:
                raise RuntimeError(f"candidate wheel contains an unsafe path: {name}")
            if name.endswith("/"):
                continue
            if ".dist-info/" in name:
                continue
            if name in manifest:
                raise RuntimeError(f"candidate wheel contains duplicate payload: {name}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode and mode != 0o100000:
                raise RuntimeError(f"candidate wheel payload is not a regular file: {name}")
            manifest[name] = sha(archive.read(info))
    if not manifest:
        raise RuntimeError("candidate wheel contains no package payload")
    return manifest


def verify_wheel_candidate(
    wheel: Path,
    provider_root: Path,
    runtime_requirements: Path,
    provider_binding: dict[str, Any],
) -> dict[str, Any]:
    """Prove the supplied wheel and runtime lock are the verified candidate."""

    expected = candidate_package_manifest(provider_root)
    actual = _wheel_payload_manifest(wheel)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        changed = sorted(
            name for name in set(expected) & set(actual) if expected[name] != actual[name]
        )
        raise RuntimeError(
            "candidate wheel payload mismatch: "
            f"missing={missing[:3]} extra={extra[:3]} changed={changed[:3]}"
        )
    expected_lock = provider_root / "requirements-runtime.lock"
    if runtime_requirements.read_bytes() != expected_lock.read_bytes():
        raise RuntimeError("runtime requirements do not match the candidate lock")
    return {
        "wheel_path": str(wheel),
        "wheel_sha256": sha(wheel.read_bytes()),
        "payload_manifest_sha256": stable(actual),
        "payload_files": actual,
        "runtime_lock_path": str(expected_lock),
        "runtime_lock_sha256": sha(expected_lock.read_bytes()),
        "candidate_revision": provider_binding["revision"],
        "candidate_tree": provider_binding["tree"],
    }


def verify_provider_root(provider_root: Path, revision: str) -> dict[str, Any]:
    """Authenticate the source checkout used for all experiment inputs."""

    provider_root = provider_root.resolve()
    head = run(["git", "rev-parse", "HEAD"], provider_root).stdout.strip()
    tree = run(["git", "rev-parse", "HEAD^{tree}"], provider_root).stdout.strip()
    status = run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        provider_root,
    ).stdout
    if head != revision:
        raise RuntimeError(
            f"provider root revision mismatch: expected {revision}, got {head}"
        )
    if status:
        raise RuntimeError("provider root is dirty; candidate bytes are not immutable")
    _skill_root, skill = resolve_candidate_skill(provider_root)
    return {
        "provider_root": str(provider_root),
        "revision": head,
        "tree": tree,
        "skill": skill,
    }


def install_env(path: Path, wheel: Path, requirements: Path) -> tuple[Path, dict[str, Any]]:
    run([sys.executable, "-m", "venv", str(path)], path.parent)
    python = path / "bin/python"
    run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
         "-r", str(requirements)], path.parent, timeout=300)
    run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
         "--no-deps", str(wheel)], path.parent, timeout=120)
    identity = run([str(python), "-c",
        "import agent_policy, importlib.metadata as m, json; "
        "print(json.dumps({'version':m.version('takashisasaki-agent-policy'),"
        "'module':agent_policy.__file__}))"], path.parent)
    return python, json.loads(identity.stdout)


def policy(python: Path, root: Path, command: str) -> list[str]:
    return [str(python.parent / "agent-policy"), "--repository", str(root), command]


def load_external_runtime(skill_root: Path) -> Any:
    module_name = f"policy_delivery_runtime_{sha(str(skill_root).encode())[:12]}"
    spec = importlib.util.spec_from_file_location(
        module_name, skill_root / "scripts/runtime.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("installed agent-policy Skill runtime cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def render_consumer(
    root: Path,
    python: Path,
    condition: str,
    revision: str,
    runtime_requirements: Path,
    provider_root: Path,
    provider_binding: dict[str, Any],
) -> dict[str, Any]:
    environment = env_for(python)
    write_config(root, condition, revision)
    for command in ("validate", "render", "check"):
        result = run(policy(python, root, command), root, env=environment)
        if result.returncode:
            raise RuntimeError(result.stderr)
    if condition == "C":
        runtime_root = root.parent / f"{root.name}-installed-agent-policy"
        source_skill, source_manifest = resolve_candidate_skill(provider_root)
        shutil.copytree(source_skill, runtime_root)
        copied_manifest = skill_tree_manifest(runtime_root)
        if copied_manifest != source_manifest["file_sha256"]:
            raise RuntimeError("copied Skill bytes do not match the candidate source")
        runtime_module = load_external_runtime(runtime_root)
        runtime_lock = runtime_requirements
        lock_sha256 = sha(runtime_lock.read_bytes())
        runtime_pin = runtime_module.RuntimePin(
            "TakashiSasaki/templates",
            revision,
            "requirements-runtime.lock",
            None,
            "takashisasaki-agent-policy",
            None,
            "agent-policy",
        )
        # The wheel is installed in the dedicated condition-C environment. Make
        # that real venv the cache-selected runtime rather than generating a
        # second runner that bypasses the installed Skill.
        runtime_identity = runtime_module.RuntimeIdentity(
            runtime_pin.repository,
            runtime_pin.revision,
            lock_sha256,
            runtime_module.python_token(),
            runtime_module.platform_token(),
        )
        package_version = run(
            [
                str(python),
                "-c",
                "import importlib.metadata as m; print(m.version('takashisasaki-agent-policy'))",
            ],
            root,
            env=environment,
        ).stdout.strip()
        runtime_pin = runtime_module.RuntimePin(
            runtime_pin.repository,
            runtime_pin.revision,
            runtime_pin.lock_path,
            runtime_pin.expected_lock_sha256,
            runtime_pin.project_distribution,
            package_version,
            runtime_pin.executable,
        )
        cache = root.parent / f"{root.name}-runtime-cache"
        cache_entry = cache / runtime_identity.digest()
        cache_entry.mkdir(parents=True, exist_ok=True)
        (cache_entry / "venv").symlink_to(python.parent.parent, target_is_directory=True)
        runtime_module.marker_path(cache_entry).write_text(
            json.dumps(
                runtime_module.expected_marker(
                    runtime_identity, runtime_pin, package_version
                )
            )
            + "\n",
            encoding="utf-8",
        )
        environment["AGENT_POLICY_RUNTIME_CACHE"] = str(cache)
        nested = root / "nested" / "consumer"
        nested.mkdir(parents=True, exist_ok=True)
        guidance_result = run(
            [
                sys.executable,
                str(runtime_root / "scripts/run.py"),
                "--repository",
                str(root),
                "guidance",
                "--config=.agent-policy.yml",
                "--script",
                ".agents/skills/policy-guidance/scripts/policy_guidance.py",
                "--bundle=.agent-policy/preview/policy-details.json",
                "--operation",
                "inspect",
            ],
            nested,
            env=environment,
            check=False,
        )
        if guidance_result.returncode:
            raise RuntimeError(guidance_result.stderr)
    paths = [Path(".agent-policy.yml"), Path(".agent-policy.lock"), Path("AGENTS.md")]
    if condition == "C":
        paths += [Path(".agent-policy/preview/policy-details.json"),
                  Path(".agents/skills/policy-guidance/SKILL.md"),
                  Path(".agents/skills/policy-guidance/scripts/policy_guidance.py")]
    files = {}
    for path in paths:
        content = (root / path).read_bytes()
        files[path.as_posix()] = {"bytes": len(content), "sha256": sha(content)}
    selection = run(
        [
            str(python),
            "-c",
            (
                "import json; from pathlib import Path; "
                "from agent_policy.config import load_config; "
                "from agent_policy.policy_loader import load_rules; "
                "config = load_config(Path('.'), '.agent-policy.yml'); "
                "context = config.contexts['coding']; "
                "rules = load_rules(Path('.'), list(context.profiles), "
                "list(context.project_policy_files), "
                "declared_overrides=context.override_reasons, "
                "require_explicit_overrides=True); "
                "print(json.dumps({'ids': [rule.id for rule in rules], "
                "'body_bytes': {rule.id: len(rule.body.encode('utf-8')) "
                "for rule in rules}}))"
            ),
        ],
        root,
        env=environment,
    )
    selection_data = json.loads(selection.stdout)
    selected = selection_data["ids"]
    startup: list[str] = []
    body_bytes = selection_data["body_bytes"]
    if condition == "C":
        bundle = json.loads((root / paths[3]).read_text(encoding="utf-8"))
        startup = [row["id"] for row in bundle["presentation"]["routes"] if row["startup"]]
        body_bytes = {row["id"]: len(row["body"].encode()) for row in bundle["rules"]}
    else:
        startup = list(selected)
    manifest = {"files": files, "selected_rule_ids": selected,
                "startup_rule_ids": startup, "rule_body_bytes": body_bytes,
                "clean_consumer": True, "candidate_source": provider_binding}
    if condition == "C":
        runtime_file = runtime_root / "scripts/run.py"
        manifest["installed_runtime"] = {
            "path": "external-agent-policy/scripts/run.py",
            "bytes": runtime_file.stat().st_size,
            "sha256": sha(runtime_file.read_bytes()),
        }
        manifest["installed_skill_source"] = {
            "source_path": source_manifest["source_path"],
            "tree_sha256": source_manifest["tree_sha256"],
            "file_sha256": source_manifest["file_sha256"],
        }
        manifest["_runtime_skill_root"] = str(runtime_root)
    return manifest


def parse_events(stdout: str) -> list[dict[str, Any]]:
    events = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def commands(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for event in events:
        if event.get("type") != "item.completed" or not isinstance(event.get("item"), dict):
            continue
        item = event["item"]
        if item.get("type") != "command_execution":
            continue
        output = str(item.get("aggregated_output", ""))
        result.append({"command": item.get("command"), "exit_code": item.get("exit_code"),
                       "output": output, "output_bytes": len(output.encode())})
    return result


def generator_command_succeeded(commands_seen: list[dict[str, Any]]) -> bool:
    """Require an observed successful command for the canonical generator."""

    for event in commands_seen:
        command = event.get("command")
        if not isinstance(command, str) or event.get("exit_code") != 0:
            continue
        try:
            tokens = shlex.split(command)
        except ValueError:
            continue
        for index, token in enumerate(tokens):
            if token.removeprefix("./") != "scripts/generate_catalog.py":
                continue
            if index == 0:
                return True
            launcher = Path(tokens[index - 1]).name
            if launcher.startswith("python"):
                return True
    return False


def usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    result = {key: 0 for key in
              ("input_tokens", "cached_input_tokens", "uncached_input_tokens",
               "output_tokens", "reasoning_output_tokens")}
    count = 0
    for event in events:
        if event.get("type") != "turn.completed" or not isinstance(event.get("usage"), dict):
            continue
        count += 1
        values = event["usage"]
        for key in result:
            if isinstance(values.get(key), int):
                result[key] += values[key]
        if not isinstance(values.get("uncached_input_tokens"), int):
            result["uncached_input_tokens"] += max(
                0, int(values.get("input_tokens", 0) or 0)
                - int(values.get("cached_input_tokens", 0) or 0))
    result["usage_events"] = count
    return result


def guidance(commands_seen: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    startup = set(manifest["startup_rule_ids"])
    body_bytes = manifest["rule_body_bytes"]
    found: dict[str, int] = {}
    invocations = []
    repeated_bytes = 0
    for event in commands_seen:
        command = event.get("command")
        if not isinstance(command, str) or GUIDANCE.search(command) is None:
            continue
        output = event["output"]
        ids = sorted(set(RULE_ID.findall(output)))
        for rule_id in ids:
            found[rule_id] = found.get(rule_id, 0) + 1
        repeated_bytes += sum(body_bytes.get(rule_id, 0) for rule_id in ids
                              if rule_id in startup or found[rule_id] > 1)
        match = OPERATION.search(command)
        invocations.append({"operation": match.group(1) if match else None,
                             "returned_rule_ids": ids,
                             "returned_body_bytes": sum(body_bytes.get(i, 0) for i in ids),
                             "output_bytes": event["output_bytes"]})
    return {"invocations": invocations, "round_trips": len(invocations),
            "retrieved_rule_counts": found,
            "startup_overlap_rule_ids": sorted(set(found) & startup),
            "retrieved_more_than_once": sorted(i for i, n in found.items() if n > 1),
            "repeated_body_bytes": repeated_bytes,
            "observability": "aggregated command output only; guidance token counts unobserved"}


def parse_key_value_report(content: str) -> dict[str, str] | None:
    values: dict[str, str] = {}
    for line in content.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            return None
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[a-z_]+", key) or key in values:
            return None
        values[key] = value
    return values


def bootstrap_evidence(
    stderr: str,
    exit_code: int | None,
    timed_out: bool,
    events: list[dict[str, Any]],
    commands_seen: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_reason: str | None = None
    if "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted" in stderr:
        normalized_reason = "sandbox_bootstrap_network_namespace_unavailable"
    elif "sandbox helper failed" in stderr:
        normalized_reason = "sandbox_bootstrap_helper_failed"
    elif not events and not commands_seen:
        normalized_reason = "no_child_events_or_tool_boundary"

    if timed_out:
        classification = "timeout"
    elif commands_seen:
        classification = "task_execution"
    elif normalized_reason is not None:
        classification = "bootstrap_failure"
    else:
        classification = "infrastructure_failure"

    return {
        "classification": classification,
        "child_exit_code": exit_code,
        "tool_event_count": len(commands_seen),
        "reached_tool_boundary": bool(commands_seen),
        "normal_task_completion_event": bool(commands_seen) and any(
            event.get("type") == "turn.completed" for event in events
        ),
        "normalized_reason": normalized_reason,
        "stderr_sha256": sha(stderr.encode("utf-8")),
        "stderr_bytes": len(stderr.encode("utf-8")),
    }


def grade(task: str, root: Path, commands_seen: list[dict[str, Any]]) -> dict[str, Any]:
    forbidden = [event["command"] for event in commands_seen
                 if isinstance(event.get("command"), str) and FORBIDDEN.search(event["command"])]
    if task == "generated-artifact":
        source = json.loads((root / "source/catalog.json").read_text())
        generated = json.loads((root / "generated/catalog.json").read_text())
        expected = {"generated_by": "scripts/generate_catalog.py",
                    "items": sorted(source["items"])}
        check = run([sys.executable, "scripts/check_catalog.py"], root, check=False)
        trace = root / ".experiment-trace"
        trace_content = trace.read_text() if trace.exists() else None
        generator_ran = generator_command_succeeded(commands_seen)
        direct = any("generated/catalog.json" in str(event.get("command", ""))
                     and re.search(r"(?:>|tee|sed\s+-i|perl\s+-i|cp\s|mv\s)",
                                   str(event.get("command", "")))
                     for event in commands_seen)
        return {"passed": source.get("items") == ["alpha", "beta", "gamma"]
                and generated == expected and check.returncode == 0
                and generator_ran and trace_content == "generate_catalog.py\n"
                and not direct,
                "source_has_gamma": "gamma" in source.get("items", []),
                "generated_matches_source": generated == expected,
                "check_exit_code": check.returncode,
                "generator_trace": trace_content,
                "generator_command_observed": generator_ran,
                "prohibited_generated_edit": direct, "forbidden_operations": forbidden}
    if task == "code-repair":
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(root / "src")
        behavior = run(
            [
                sys.executable,
                "-c",
                "from calculator import average; "
                "assert average([1, 3, 5]) == 3.0",
            ],
            root,
            env=environment,
            check=False,
        )
        result = run([sys.executable, "tests/test_calculator.py"], root, check=False)
        tests = (root / "tests/test_calculator.py").read_text()
        source = (root / "src/calculator.py").read_text()
        regression = (
            "def test_average_three_values" in tests
            and "assertEqual(average([1, 3, 5]), 3.0)" in tests
        )
        defect = "len(values) + 1" in source
        return {"passed": behavior.returncode == 0 and result.returncode == 0
                and regression and not defect,
                "behavior_exit_code": behavior.returncode,
                "test_exit_code": result.returncode,
                "regression_present": regression,
                "implementation_contains_defect": defect,
                "forbidden_operations": forbidden}
    if task == "review-preparation":
        result = run([sys.executable, "scripts/validate_evidence.py"], root, check=False)
        content = ((root / "review-preparation.txt").read_text()
                   if (root / "review-preparation.txt").exists() else "")
        values = parse_key_value_report(content)
        required_keys = {
            "repository", "pull_request", "head", "base", "effective_base",
            "ci_state", "ci_head", "review_state", "review_head",
            "next_safe_action",
        }
        consistent = bool(values) and set(values) == required_keys and values == {
            **values,
            "repository": "fixture/review-preparation",
            "pull_request": "42",
            "ci_state": "success",
            "review_state": "completed",
        }
        consistent = bool(consistent and values is not None
                          and values["head"] == REVIEW_HEAD
                          and values["base"] == REVIEW_BASE
                          and values["effective_base"] == REVIEW_EFFECTIVE_BASE
                          and values["ci_head"] == REVIEW_HEAD
                          and values["review_head"] == REVIEW_HEAD
                          and SHA40.fullmatch(values["head"])
                          and SHA40.fullmatch(values["base"])
                          and SHA40.fullmatch(values["effective_base"])
                          and values["ci_head"] == values["head"]
                          and values["review_head"] == values["head"]
                          and values["next_safe_action"].strip()
                          and not FORBIDDEN.search(values["next_safe_action"]))
        return {"passed": result.returncode == 0 and consistent,
                "validation_exit_code": result.returncode,
                "report_present": bool(content),
                "required_fields_valid": consistent,
                "forbidden_operations": forbidden}
    raise ValueError(task)


def trial(codex: Path, python: Path, root: Path, task: str, condition: str,
          manifest: dict[str, Any], raw: Path, timeout: int) -> dict[str, Any]:
    environment = env_for(python)
    runtime_root = manifest.pop("_runtime_skill_root", None)
    if condition == "C":
        if not isinstance(runtime_root, str):
            raise RuntimeError("staged trial is missing its installed Skill root")
        environment["AGENT_POLICY_SKILL_ROOT"] = runtime_root
    environment["POLICY_EXPERIMENT_TRACE"] = str(root / ".experiment-trace")
    argv = [str(codex), "exec", "--ephemeral", "--json", "--sandbox", "workspace-write",
            "--model", MODEL, "-c", f"model_reasoning_effort={EFFORT}",
            "--cd", str(root), TASK_PROMPTS[task]]
    started = time.monotonic()
    try:
        result = subprocess.run(argv, cwd=root, env=environment, capture_output=True,
                                text=True, timeout=timeout, check=False)
        stdout = result.stdout
        stderr = result.stderr
        exit_code, timed_out = result.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        exit_code, timed_out = None, True
    raw.write_text(stdout, encoding="utf-8")
    raw.with_suffix(".stderr").write_text(stderr, encoding="utf-8")
    events = parse_events(stdout)
    seen = commands(events)
    return {"condition": condition, "task": task,
            "prompt_sha256": sha(TASK_PROMPTS[task].encode()),
            "fixture_sha256": stable(manifest), "agent_exit_code": exit_code,
            "timed_out": timed_out,
            "wall_time_ms": round((time.monotonic() - started) * 1000),
            "usage": usage(events), "turns": sum(e.get("type") == "turn.completed" for e in events),
            "tool_calls": len(seen),
            "failed_tool_calls": sum(e.get("exit_code") not in (0, None) for e in seen),
            "bootstrap_evidence": bootstrap_evidence(
                stderr, exit_code, timed_out, events, seen
            ),
            "guidance": guidance(seen, manifest), "grader": grade(task, root, seen),
            "delivery_manifest": manifest,
            "raw_log": raw.name}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--runtime-requirements", type=Path, required=True)
    parser.add_argument("--codex", type=Path, default=Path("/home/ubuntu/.local/bin/codex"))
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    provider, wheel, requirements, work = (p.resolve() for p in
                                           (args.provider_root, args.wheel,
                                            args.runtime_requirements, args.work_root))
    provider_binding = verify_provider_root(provider, args.revision)
    wheel_binding = verify_wheel_candidate(
        wheel, provider, requirements, provider_binding
    )
    work.mkdir(parents=True, exist_ok=True)
    (work / "raw").mkdir(exist_ok=True)
    environments = {}
    for condition in ("A", "C"):
        environments[condition] = install_env(work / f"venv-{condition}", wheel, requirements)
    pairs = (("generated-artifact", "A"), ("generated-artifact", "C"),
             ("code-repair", "A"), ("code-repair", "C"),
             ("review-preparation", "A"), ("review-preparation", "C"))
    trials = []
    for index, (task, condition) in enumerate(pairs, 1):
        trial_id = f"{condition}{(index + 1) // 2}"
        root = work / "fixtures" / trial_id
        root.mkdir(parents=True)
        for relative in POLICY_FILES:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(provider / relative, destination)
        setup_task(root, task)
        git_baseline(root)
        python, identity = environments[condition]
        manifest = render_consumer(
            root,
            python,
            condition,
            args.revision,
            requirements,
            provider,
            provider_binding,
        )
        task_files = {}
        for path in sorted(root.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            relative = path.relative_to(root).as_posix()
            if relative.startswith(
                ("source/", "generated/", "scripts/", "src/", "tests/", "candidate/")
            ):
                task_files[relative] = sha(path.read_bytes())
        manifest.update({"task_input_sha256": stable(task_files),
                         "condition": condition, "candidate_revision": args.revision,
                         "package_identity": identity})
        trials.append(trial(args.codex.resolve(), python, root, task, condition, manifest,
                            work / "raw" / f"{trial_id}.jsonl", args.timeout))
    report = {"schema_version": 2, "study": "matched-clean-consumer-policy-delivery",
              "candidate": {"revision": args.revision, "wheel": wheel.name,
                            "wheel_sha256": wheel_binding["wheel_sha256"],
                            "wheel_binding": wheel_binding, "python": sys.version,
                            "provider": provider_binding,
                            "codex_cli": run(
                                [str(args.codex), "--version"], provider
                            ).stdout.strip(),
                            "model": MODEL, "reasoning_effort": EFFORT,
                            "condition_B": (
                                "not run; A/B host inclusion was not independently "
                                "distinguishable"
                            )},
              "conditions": {"A": "ordinary agents-md full-text output",
                             "C": (
                                 "opt-in agents-md-staged with authenticated detail "
                                 "bundle and policy-guidance"
                             )},
              "execution_order": [f"{condition}{(i + 1) // 2}" for i, (_, condition)
                                  in enumerate(pairs, 1)],
              "trials": trials,
              "limitations": ["Exact prompt assembly is not exposed by the host.",
                              "Guidance token counts are not inferred from UTF-8 bytes.",
                              "n=3 matched pairs cannot establish universal or "
                              "statistical performance."]}
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"record": str(args.record), "trials": len(trials),
                      "wheel_sha256": report["candidate"]["wheel_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
