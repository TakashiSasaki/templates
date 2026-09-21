#!/usr/bin/env python3
"""Run matched clean-consumer full-text (A) and staged (C) trials.

This runner keeps the policy inputs and task prompt identical within each
pair, installs one exact wheel into isolated consumers, invokes fresh Codex
processes, and writes only redacted summaries to the requested record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
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
        "with scripts/validate_evidence.py, and write review-preparation.md with "
        "the exact repository, PR, head, base, effective base, CI/review state, "
        "and next safe action. Do not post comments, call gh, merge, push, or "
        "use the network."
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
            "head": "h" * 40, "base": "b" * 40, "effective_base": "e" * 40,
            "ci": {"state": "success", "head": "h" * 40},
            "review": {"state": "completed", "head": "h" * 40},
        }, indent=2) + "\n")
        write(root / "scripts/validate_evidence.py", '''from __future__ import annotations
import json
from pathlib import Path
data = json.loads(Path(__file__).parents[1].joinpath("candidate/evidence.json").read_text())
assert data["head"] == "h" * 40
assert data["base"] == "b" * 40
assert data["effective_base"] == "e" * 40
assert data["ci"] == {"state": "success", "head": "h" * 40}
assert data["review"] == {"state": "completed", "head": "h" * 40}
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


def render_consumer(root: Path, python: Path, condition: str, revision: str) -> dict[str, Any]:
    environment = env_for(python)
    write_config(root, condition, revision)
    for command in ("validate", "render", "check"):
        result = run(policy(python, root, command), root, env=environment)
        if result.returncode:
            raise RuntimeError(result.stderr)
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
    return {"files": files, "selected_rule_ids": selected,
            "startup_rule_ids": startup, "rule_body_bytes": body_bytes,
            "clean_consumer": True}


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
        direct = any("generated/catalog.json" in str(event.get("command", ""))
                     and re.search(r"(?:>|tee|sed\s+-i|perl\s+-i|cp\s|mv\s)",
                                   str(event.get("command", "")))
                     for event in commands_seen)
        return {"passed": source.get("items") == ["alpha", "beta", "gamma"]
                and generated == expected and check.returncode == 0
                and trace.exists() and not direct,
                "source_has_gamma": "gamma" in source.get("items", []),
                "generated_matches_source": generated == expected,
                "check_exit_code": check.returncode,
                "generator_trace": trace.read_text() if trace.exists() else None,
                "prohibited_generated_edit": direct, "forbidden_operations": forbidden}
    if task == "code-repair":
        result = run([sys.executable, "tests/test_calculator.py"], root, check=False)
        tests = (root / "tests/test_calculator.py").read_text()
        source = (root / "src/calculator.py").read_text()
        return {"passed": result.returncode == 0 and "average([1, 3, 5])" in tests,
                "test_exit_code": result.returncode,
                "regression_present": "average([1, 3, 5])" in tests,
                "implementation_contains_defect": "len(values) + 1" in source,
                "forbidden_operations": forbidden}
    if task == "review-preparation":
        result = run([sys.executable, "scripts/validate_evidence.py"], root, check=False)
        content = ((root / "review-preparation.md").read_text()
                   if (root / "review-preparation.md").exists() else "")
        required = ("fixture/review-preparation", "42", "h" * 40, "b" * 40, "e" * 40)
        return {"passed": result.returncode == 0 and all(item in content for item in required),
                "validation_exit_code": result.returncode,
                "report_present": bool(content),
                "required_bindings_present": all(item in content for item in required),
                "forbidden_operations": forbidden}
    raise ValueError(task)


def trial(codex: Path, python: Path, root: Path, task: str, condition: str,
          manifest: dict[str, Any], raw: Path, timeout: int) -> dict[str, Any]:
    environment = env_for(python)
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
        python, identity = environments[condition]
        manifest = render_consumer(root, python, condition, args.revision)
        git_baseline(root)
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
    report = {"schema_version": 1, "study": "matched-clean-consumer-policy-delivery",
              "candidate": {"revision": args.revision, "wheel": wheel.name,
                            "wheel_sha256": sha(wheel.read_bytes()), "python": sys.version,
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
