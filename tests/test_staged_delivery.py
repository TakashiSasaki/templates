from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from agent_policy import delivery
from agent_policy.commands import check, render, validate
from agent_policy.config import load_config
from agent_policy.delivery import load_presentation_map
from agent_policy.policy_loader import load_rules
from agent_policy.renderer import render_agents
from agent_policy.yamlutil import dump_yaml, load_yaml

TEST_REVISION = "a" * 40
GUIDANCE = "project.generated-delivery"


def _write_staged_repository(root: Path) -> None:
    (root / ".git").mkdir()
    (root / "policy").mkdir()
    (root / "policy/project.md").write_text(
        """---
id: project.generated-delivery
severity: mandatory
overridable: true
order: 1000
---
# Generated delivery rule

Retrieve this rule before changing generated files.
""",
        encoding="utf-8",
    )
    (root / ".agent-policy.yml").write_text(
        f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {TEST_REVISION}
contexts:
  coding:
    profiles:
      - core
    project_policy:
      files:
        - policy/project.md
outputs:
  agents-staged:
    enabled: true
    path: .agent-policy/preview/AGENTS.md
    detail_bundle: .agent-policy/preview/policy-details.json
    context: coding
    renderer: agents-md-staged
skills:
  enabled:
    - policy-guidance
""",
        encoding="utf-8",
    )


def _run_guidance(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    skill = root / ".agents/skills/policy-guidance/scripts/policy_guidance.py"
    environment = dict(os.environ)
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = ":".join(
        item for item in (source_root, environment.get("PYTHONPATH", "")) if item
    )
    return subprocess.run(
        [sys.executable, str(skill), "--root", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _rewrite_bundle_and_lock(root: Path, mutate) -> None:
    bundle_path = root / ".agent-policy/preview/policy-details.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    mutate(bundle)
    bundle_path.write_text(
        json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lock_path = root / ".agent-policy.lock"
    lock = load_yaml(lock_path)
    lock["outputs"][".agent-policy/preview/policy-details.json"]["sha256"] = (
        hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    )
    lock_path.write_text(dump_yaml(lock), encoding="utf-8")


def test_staged_delivery_preserves_full_rule_set_and_supports_clean_retrieval(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert render.run(tmp_path, ".agent-policy.yml") == []

    config = load_config(tmp_path, ".agent-policy.yml")
    context = config.contexts["coding"]
    rules = load_rules(
        tmp_path,
        list(context.profiles),
        list(context.project_policy_files),
        declared_overrides=context.override_reasons,
        require_explicit_overrides=True,
    )
    bundle = json.loads(
        (tmp_path / ".agent-policy/preview/policy-details.json").read_text(
            encoding="utf-8"
        )
    )
    startup = (tmp_path / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )
    expected_full = render_agents(
        config,
        rules,
        context_name="coding",
        project_policy_files=context.project_policy_files,
    )
    generated_skill = (
        tmp_path / ".agents/skills/policy-guidance/scripts/policy_guidance.py"
    )

    assert [item["id"] for item in bundle["rules"]] == [rule.id for rule in rules]
    assert "project.generated-delivery" in startup
    assert len(startup.encode("utf-8")) < len(expected_full.encode("utf-8"))
    assert "{{ policy_delivery_bundle_path" not in generated_skill.read_text(
        encoding="utf-8"
    )
    assert set(load_yaml(tmp_path / ".agent-policy.lock")["outputs"]) == {
        ".agent-policy/preview/AGENTS.md",
        ".agent-policy/preview/policy-details.json",
        ".agents/skills/policy-guidance/SKILL.md",
        ".agents/skills/policy-guidance/scripts/policy_guidance.py",
    }

    result = _run_guidance(tmp_path, "--rule-id", GUIDANCE)
    assert result.returncode == 0
    assert "Retrieve this rule before changing generated files." in result.stdout

    blocked = _run_guidance(tmp_path, "--operation", "edit")
    assert blocked.returncode == 2
    assert "route is incomplete" in blocked.stderr


def test_staged_delivery_rejects_missing_guidance_skill(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "skills:\n  enabled:\n    - policy-guidance\n",
            "skills:\n  enabled: []\n",
        ),
        encoding="utf-8",
    )

    diagnostics = validate.run(tmp_path, ".agent-policy.yml")

    assert any(item.code == "STAGED_GUIDANCE_SKILL" for item in diagnostics)


def test_staged_guidance_rejects_bundle_digest_drift(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    bundle_path = tmp_path / ".agent-policy/preview/policy-details.json"
    bundle_path.write_text(
        bundle_path.read_text(encoding="utf-8").replace(
            "Retrieve this rule before changing generated files.",
            "Tampered rule text.",
        ),
        encoding="utf-8",
    )
    result = _run_guidance(tmp_path, "--rule-id", GUIDANCE)

    assert result.returncode == 2
    assert "does not match .agent-policy.lock" in result.stderr


def test_staged_render_is_deterministic_and_check_detects_input_drift(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    first_outputs = {
        relative: (tmp_path / relative).read_bytes()
        for relative in load_yaml(tmp_path / ".agent-policy.lock")["outputs"]
    }

    assert render.run(tmp_path, ".agent-policy.yml") == []
    second_outputs = {
        relative: (tmp_path / relative).read_bytes()
        for relative in load_yaml(tmp_path / ".agent-policy.lock")["outputs"]
    }
    assert first_outputs == second_outputs

    policy = tmp_path / "policy/project.md"
    policy.write_text(
        policy.read_text(encoding="utf-8") + "\nAdditional requirement.\n",
        encoding="utf-8",
    )
    stale = check.run(tmp_path, ".agent-policy.yml")
    assert any(item.code == "STALE_OUTPUT" for item in stale)


def test_presentation_map_covers_current_coding_selection() -> None:
    repository_root = Path(__file__).parents[1]
    config = load_config(repository_root, ".agent-policy.yml")
    context = config.contexts["coding"]
    rules = load_rules(
        repository_root,
        list(context.profiles),
        list(context.project_policy_files),
        declared_overrides=context.override_reasons,
        require_explicit_overrides=True,
    )
    presentation_map, _ = load_presentation_map()

    assert {rule.id for rule in rules} <= set(presentation_map["rules"])


@pytest.mark.parametrize(
    ("selector", "expected_returncode"),
    [
        (["--rule-id", GUIDANCE], 0),
        (["--operation", "edit"], 2),
        (["--all"], 0),
    ],
)
def test_every_guidance_selector_revalidates_unchanged_inputs(
    tmp_path: Path, selector: list[str], expected_returncode: int
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    result = _run_guidance(tmp_path, *selector)

    assert result.returncode == expected_returncode
    if expected_returncode == 2:
        assert "operation route is incomplete" in result.stderr


@pytest.mark.parametrize("mutation", ["config", "policy", "delete-policy"])
def test_guidance_rejects_current_input_drift(
    tmp_path: Path, mutation: str
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    if mutation == "config":
        config = tmp_path / ".agent-policy.yml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(TEST_REVISION, "b" * 40),
            encoding="utf-8",
        )
    elif mutation == "policy":
        policy = tmp_path / "policy/project.md"
        policy.write_text(policy.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8")
    else:
        (tmp_path / "policy/project.md").unlink()

    result = _run_guidance(tmp_path, "--rule-id", GUIDANCE)

    assert result.returncode == 2
    assert "current" in result.stderr


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Tampered title"),
        ("severity", "advisory"),
        ("overridable", False),
        ("overridable", 1),
        ("order", 9999),
        ("order", 1000.0),
    ],
)
def test_guidance_rejects_policy_metadata_drift_after_lock_update(
    tmp_path: Path, field: str, value: object
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    def mutate(bundle: dict) -> None:
        rule = next(item for item in bundle["rules"] if item["id"] == GUIDANCE)
        rule[field] = value

    _rewrite_bundle_and_lock(tmp_path, mutate)
    result = _run_guidance(tmp_path, "--rule-id", GUIDANCE)

    assert result.returncode == 2
    assert "metadata" in result.stderr


@pytest.mark.parametrize("mutation", ["configuration", "project_policy", "renderer"])
def test_guidance_rejects_contradictory_bundle_identity(
    tmp_path: Path, mutation: str
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    def mutate(bundle: dict) -> None:
        if mutation == "configuration":
            bundle["bindings"]["configuration"][".agent-policy.yml"] = "f" * 64
        elif mutation == "project_policy":
            bundle["bindings"]["project_policy"]["policy/project.md"] = "f" * 64
        else:
            bundle["renderer"] = "agents-md"

    _rewrite_bundle_and_lock(tmp_path, mutate)
    result = _run_guidance(tmp_path, "--all")

    assert result.returncode == 2
    assert "identity" in result.stderr or "projections" in result.stderr


def test_guidance_discovers_repository_root_from_nested_directory(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    nested = tmp_path / "nested" / "work"
    nested.mkdir(parents=True)
    skill = tmp_path / ".agents/skills/policy-guidance/scripts/policy_guidance.py"
    environment = dict(os.environ)
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = ":".join(
        item for item in (source_root, environment.get("PYTHONPATH", "")) if item
    )

    result = subprocess.run(
        [sys.executable, str(skill), "--rule-id", GUIDANCE],
        cwd=nested,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0
    assert "Retrieve this rule before changing generated files." in result.stdout


def test_guidance_discovers_root_without_default_config_name(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    default_config = tmp_path / ".agent-policy.yml"
    custom_config = tmp_path / "policy config &.yml"
    default_config.rename(custom_config)
    assert render.run(tmp_path, custom_config.name) == []
    nested = tmp_path / "nested" / "work"
    nested.mkdir(parents=True)
    skill = tmp_path / ".agents/skills/policy-guidance/scripts/policy_guidance.py"
    environment = dict(os.environ)
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = ":".join(
        item for item in (source_root, environment.get("PYTHONPATH", "")) if item
    )

    result = subprocess.run(
        [sys.executable, str(skill), "--rule-id", GUIDANCE],
        cwd=nested,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0
    assert "Retrieve this rule before changing generated files." in result.stdout


@pytest.mark.parametrize(
    "bundle_path",
    [
        ".agent-policy/preview/policy details &copy.json",
        "-details.json",
    ],
)
def test_generated_guidance_commands_quote_bundle_paths(
    tmp_path: Path, bundle_path: str
) -> None:
    _write_staged_repository(tmp_path)
    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "detail_bundle: .agent-policy/preview/policy-details.json",
            f"detail_bundle: {json.dumps(bundle_path)}",
        ),
        encoding="utf-8",
    )

    assert render.run(tmp_path, ".agent-policy.yml") == []
    startup = (tmp_path / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )
    skill = (tmp_path / ".agents/skills/policy-guidance/SKILL.md").read_text(
        encoding="utf-8"
    )
    quoted = shlex.quote(bundle_path)
    assert f"--bundle={quoted} --operation" in startup
    assert f"--bundle={quoted} --operation" in skill
    assert ".agents/skills/agent-policy/scripts/run.py" in startup
    assert ".agents/skills/agent-policy/scripts/run.py" in skill

    environment = dict(os.environ)
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = ":".join(
        item for item in (source_root, environment.get("PYTHONPATH", "")) if item
    )
    result = subprocess.run(
        [
            "sh",
            "-c",
            f"{shlex.quote(sys.executable)} "
            ".agents/skills/policy-guidance/scripts/policy_guidance.py "
            f"--bundle={quoted} --rule-id {GUIDANCE}",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.returncode == 0

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    runtime_runner = tmp_path / ".agents/skills/agent-policy/scripts/run.py"
    runtime_runner.parent.mkdir(parents=True, exist_ok=True)
    runtime_runner.write_text(
        "from agent_policy.cli import main\n"
        "raise SystemExit(main())\n",
        encoding="utf-8",
    )
    nested = tmp_path / "nested" / "work"
    nested.mkdir(parents=True)
    command = next(
        line.strip()
        for line in startup.splitlines()
        if line.strip().startswith("python ")
    )
    command = command.replace("python ", f"{shlex.quote(sys.executable)} ", 1)
    command = command.replace(
        "--operation <inspect|plan|edit|generate|validate|review|merge|publish>",
        f"--rule-id {shlex.quote(GUIDANCE)}",
    )
    nested_result = subprocess.run(
        ["sh", "-c", command],
        cwd=nested,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert nested_result.returncode == 0


def test_guidance_uses_structural_lock_for_quoted_output_path(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "detail_bundle: .agent-policy/preview/policy-details.json",
            "detail_bundle: 'true'",
        ),
        encoding="utf-8",
    )
    assert render.run(tmp_path, ".agent-policy.yml") == []

    result = _run_guidance(tmp_path, "--rule-id", GUIDANCE)

    assert result.returncode == 0
    assert "'true':" in (tmp_path / ".agent-policy.lock").read_text(encoding="utf-8")


@pytest.mark.parametrize("route_case", ["unknown", "missing", "duplicate"])
def test_guidance_rejects_inconsistent_operation_routes(
    tmp_path: Path, route_case: str
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    def mutate(bundle: dict) -> None:
        route = bundle["presentation"]["operation_routes"]["edit"]
        if route_case == "unknown":
            bundle["presentation"]["operation_routes"]["edit"] = ["nonexistent.rule"]
        elif route_case == "missing":
            bundle["presentation"]["operation_routes"]["edit"] = route[:-1]
        else:
            bundle["presentation"]["operation_routes"]["edit"] = route + [route[0]]

    _rewrite_bundle_and_lock(tmp_path, mutate)
    result = _run_guidance(tmp_path, "--operation", "edit")

    assert result.returncode == 2
    assert "operation routes" in result.stderr


def test_guidance_rejects_presentation_map_drift(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    def mutate(bundle: dict) -> None:
        bundle["presentation"]["map"]["fallback"]["reason"] = "untrusted change"

    _rewrite_bundle_and_lock(tmp_path, mutate)
    result = _run_guidance(tmp_path, "--all")

    assert result.returncode == 2
    assert "installed presentation map" in result.stderr


@pytest.mark.parametrize("startup", [1, 0.0])
def test_guidance_rejects_presentation_flag_type_coercion(
    tmp_path: Path, startup: object
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    def mutate(bundle: dict) -> None:
        rule_id = next(iter(bundle["presentation"]["map"]["rules"]))
        bundle["presentation"]["map"]["rules"][rule_id]["startup"] = startup

    _rewrite_bundle_and_lock(tmp_path, mutate)
    result = _run_guidance(tmp_path, "--all")

    assert result.returncode == 2
    assert "presentation map rule metadata" in result.stderr


@pytest.mark.parametrize("location", ["bundle", "presentation"])
def test_guidance_rejects_schema_version_type_coercion(
    tmp_path: Path, location: str
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    def mutate(bundle: dict) -> None:
        if location == "bundle":
            bundle["schema_version"] = True
        else:
            bundle["presentation"]["map"]["schema_version"] = True

    _rewrite_bundle_and_lock(tmp_path, mutate)
    result = _run_guidance(tmp_path, "--all")

    assert result.returncode == 2
    assert "schema" in result.stderr


def test_staged_output_rejects_non_coding_context(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8")
        .replace("  coding:\n", "  review:\n")
        .replace("context: coding", "context: review"),
        encoding="utf-8",
    )

    diagnostics = validate.run(tmp_path, ".agent-policy.yml")

    assert any(item.code == "STAGED_CONTEXT" for item in diagnostics)
    assert any(
        item.code == "STAGED_CONTEXT"
        for item in render.run(tmp_path, ".agent-policy.yml")
    )


def test_presentation_map_rejects_boolean_schema_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        delivery,
        "load_yaml",
        lambda _path: {"schema_version": True},
    )

    with pytest.raises(ValueError, match="Unsupported policy-delivery presentation map"):
        delivery.load_presentation_map()


def test_guidance_rejects_duplicate_lock_section(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    lock = tmp_path / ".agent-policy.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8") + "outputs: {}\n",
        encoding="utf-8",
    )

    result = _run_guidance(tmp_path, "--all")

    assert result.returncode == 2
    assert "Duplicate YAML key" in result.stderr


def test_guidance_rejects_boolean_lock_version(tmp_path: Path) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    lock = load_yaml(tmp_path / ".agent-policy.lock")
    lock["lock_version"] = True
    (tmp_path / ".agent-policy.lock").write_text(
        dump_yaml(lock), encoding="utf-8"
    )

    result = _run_guidance(tmp_path, "--all")

    assert result.returncode == 2
    assert "Unsupported lock file version" in result.stderr


def test_disabled_staged_output_with_guidance_is_rejected_before_render(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "enabled: true\n    path: .agent-policy/preview/AGENTS.md",
            "enabled: false\n    path: .agent-policy/preview/AGENTS.md",
        ),
        encoding="utf-8",
    )

    diagnostics = validate.run(tmp_path, ".agent-policy.yml")
    rendered = render.run(tmp_path, ".agent-policy.yml")

    assert any(item.code == "STAGED_GUIDANCE_OUTPUT" for item in diagnostics)
    assert any(item.code == "STAGED_GUIDANCE_OUTPUT" for item in rendered)
    assert not (tmp_path / ".agent-policy.lock").exists()
