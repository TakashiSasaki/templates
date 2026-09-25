from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

from agent_policy import delivery, generated_mutation
from agent_policy.commands import check, render, validate
from agent_policy.commands import guidance as guidance_command
from agent_policy.config import load_config, package_root
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
    if not skill.is_file():
        return subprocess.CompletedProcess(
            args=[sys.executable, str(skill), "--root", str(root), *arguments],
            returncode=1,
            stdout="",
            stderr=f"No such file: {skill}\n",
        )
    spec = importlib.util.spec_from_file_location("dynamic_guidance_execution", skill)
    if spec is None or spec.loader is None:
        return subprocess.CompletedProcess(
            args=[sys.executable, str(skill), "--root", str(root), *arguments],
            returncode=1,
            stdout="",
            stderr="Could not load guidance module\n",
        )
    module = importlib.util.module_from_spec(spec)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    saved_argv = sys.argv
    sys.argv = [str(skill), "--root", str(root), *arguments]
    returncode = 0
    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            try:
                spec.loader.exec_module(module)
                returncode = module.main()
            except SystemExit as exc:
                if isinstance(exc.code, int):
                    returncode = exc.code
                else:
                    returncode = 0 if exc.code is None else 1
    finally:
        sys.argv = saved_argv
    return subprocess.CompletedProcess(
        args=[sys.executable, str(skill), "--root", str(root), *arguments],
        returncode=returncode,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
    )


def _run_pinned_guidance(
    root: Path,
    *arguments: str,
    config: str = ".agent-policy.yml",
    runtime_revision: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = ":".join(
        item for item in (source_root, environment.get("PYTHONPATH", "")) if item
    )
    command = [
            sys.executable,
            "-c",
            "from agent_policy.cli import main; raise SystemExit(main())",
            "--repository",
            str(root),
            "guidance",
            "--config",
            config,
            "--script",
            ".agents/skills/policy-guidance/scripts/policy_guidance.py",
            *arguments,
        ]
    if runtime_revision is not None:
        command.extend(["--runtime-revision", runtime_revision])
    return subprocess.run(
        command,
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


def test_render_rejects_nested_json_generated_marker_before_overwrite(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    bundle_path = tmp_path / ".agent-policy/preview/policy-details.json"
    authored = {
        "metadata": {"agent-policy-generated": True},
        "user_data": "KEEP: agent-policy-generated: true",
    }
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps(authored, indent=2) + "\n"
    bundle_path.write_text(original, encoding="utf-8")

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert "non-generated file" in diagnostics[0].message
    assert bundle_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / ".agent-policy/preview/AGENTS.md").exists()


def test_render_rejects_malformed_json_marker_before_overwrite(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    bundle_path = tmp_path / ".agent-policy/preview/policy-details.json"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    original = '{"user_data":"agent-policy-generated: true"} trailing\n'
    bundle_path.write_text(original, encoding="utf-8")

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert "non-generated file" in diagnostics[0].message
    assert bundle_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / ".agent-policy/preview/AGENTS.md").exists()


@pytest.mark.parametrize(
    "original",
    [
        '\ufeff{"user_data":"agent-policy-generated: true"}\n',
        '/* authored */ {"user_data":"agent-policy-generated: true"}\n',
    ],
    ids=["bom", "comment"],
)
def test_render_rejects_parse_failed_json_bundle_before_overwrite(
    tmp_path: Path,
    original: str,
) -> None:
    _write_staged_repository(tmp_path)
    bundle_path = tmp_path / ".agent-policy/preview/policy-details.json"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(original, encoding="utf-8")

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert "non-generated file" in diagnostics[0].message
    assert bundle_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / ".agent-policy/preview/AGENTS.md").exists()


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


def test_pinned_guidance_rejects_tampered_script_before_execution(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    script = tmp_path / ".agents/skills/policy-guidance/scripts/policy_guidance.py"
    script.write_text("print('FORGED GUIDANCE')\n", encoding="utf-8")

    result = _run_pinned_guidance(tmp_path, "--rule-id", GUIDANCE)

    assert result.returncode == 2
    assert "generated-output lock" in result.stderr
    assert "FORGED GUIDANCE" not in result.stdout


def test_pinned_guidance_binds_bundle_to_enabled_staged_output(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    bundle_a = tmp_path / ".agent-policy/preview/policy-details.json"
    original = bundle_a.read_bytes()
    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "detail_bundle: .agent-policy/preview/policy-details.json",
            "detail_bundle: .agent-policy/preview/policy-details-b.json",
        ),
        encoding="utf-8",
    )
    assert render.run(tmp_path, ".agent-policy.yml") == []
    bundle_a.write_bytes(original)
    lock_path = tmp_path / ".agent-policy.lock"
    lock = load_yaml(lock_path)
    lock["outputs"][bundle_a.relative_to(tmp_path).as_posix()] = {
        "sha256": hashlib.sha256(original).hexdigest()
    }
    lock_path.write_text(dump_yaml(lock), encoding="utf-8")

    result = _run_pinned_guidance(
        tmp_path,
        "--bundle=.agent-policy/preview/policy-details.json",
        "--rule-id",
        GUIDANCE,
    )

    assert result.returncode == 2
    assert "enabled staged output" in result.stderr


def test_generated_guidance_rebinds_bundle_to_current_output_at_child_boundary(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    bundle_path = tmp_path / ".agent-policy/preview/policy-details.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "detail_bundle: .agent-policy/preview/policy-details.json",
            "detail_bundle: .agent-policy/preview/policy-details-b.json",
        ),
        encoding="utf-8",
    )
    config_digest = hashlib.sha256(config.read_bytes()).hexdigest()
    bundle["bindings"]["inputs"][".agent-policy.yml"] = config_digest
    bundle["bindings"]["configuration"][".agent-policy.yml"] = config_digest
    bundle_bytes = (json.dumps(bundle, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    bundle_path.write_bytes(bundle_bytes)

    lock_path = tmp_path / ".agent-policy.lock"
    lock = load_yaml(lock_path)
    lock["inputs"][".agent-policy.yml"] = {"sha256": config_digest}
    lock["outputs"][bundle_path.relative_to(tmp_path).as_posix()] = {
        "sha256": hashlib.sha256(bundle_bytes).hexdigest()
    }
    lock_path.write_text(dump_yaml(lock), encoding="utf-8")

    result = _run_guidance(
        tmp_path,
        "--bundle=.agent-policy/preview/policy-details.json",
        "--rule-id",
        GUIDANCE,
    )

    assert result.returncode == 2
    assert "enabled staged output" in result.stderr


def test_generated_guidance_rebinds_selected_config_at_child_boundary(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    alternate = tmp_path / ".agent-policy-alternate.yml"
    alternate.write_text(
        (tmp_path / ".agent-policy.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = _run_guidance(
        tmp_path,
        "--config=.agent-policy-alternate.yml",
        "--rule-id",
        GUIDANCE,
    )

    assert result.returncode == 2
    assert "configuration path" in result.stderr


def test_render_rolls_back_owned_outputs_after_late_ownership_conflict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    bundle_path = tmp_path / ".agent-policy/preview/policy-details.json"
    authored = '{"user_data":"KEEP"}\n'
    injected = False
    original_rename = generated_mutation._native_rename_noreplace

    def replace_bundle_at_install_boundary(
        source_fd: int, source: str, destination_fd: int, destination: str
    ) -> None:
        nonlocal injected
        if destination == "policy-details.json" and not injected:
            bundle_path.write_text(authored, encoding="utf-8")
            injected = True
        original_rename(source_fd, source, destination_fd, destination)

    monkeypatch.setattr(
        generated_mutation,
        "_native_rename_noreplace",
        replace_bundle_at_install_boundary,
    )

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert "created concurrently" in diagnostics[0].message
    assert injected
    assert not (tmp_path / ".agent-policy/preview/AGENTS.md").exists()
    assert bundle_path.read_text(encoding="utf-8") == authored
    assert not (tmp_path / ".agent-policy.lock").exists()


def test_render_rejects_replacement_after_last_ownership_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    startup_path = tmp_path / ".agent-policy/preview/AGENTS.md"
    startup_before = startup_path.read_text(encoding="utf-8")
    lock_path = tmp_path / ".agent-policy.lock"
    lock_before = lock_path.read_text(encoding="utf-8")
    bundle_path = tmp_path / ".agent-policy/preview/policy-details.json"
    authored = '{"user_data":"KEEP"}\n'
    injected = False
    original_rename = generated_mutation._native_rename_noreplace

    def replace_before_bundle_detach(
        source_fd: int, source: str, destination_fd: int, destination: str
    ) -> None:
        nonlocal injected
        if source == "policy-details.json" and not injected:
            bundle_path.write_text(authored, encoding="utf-8")
            injected = True
        original_rename(source_fd, source, destination_fd, destination)

    monkeypatch.setattr(
        generated_mutation,
        "_native_rename_noreplace",
        replace_before_bundle_detach,
    )

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert "content or ownership" in diagnostics[0].message
    assert injected
    assert startup_path.read_text(encoding="utf-8") == startup_before
    assert bundle_path.read_text(encoding="utf-8") == authored
    assert lock_path.read_text(encoding="utf-8") == lock_before


def test_render_revalidates_obsolete_output_before_unlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    old_startup = tmp_path / ".agent-policy/preview/AGENTS.md"
    old_bundle = tmp_path / ".agent-policy/preview/policy-details.json"
    old_startup_content = old_startup.read_text(encoding="utf-8")

    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8")
        .replace(
            ".agent-policy/preview/AGENTS.md",
            ".agent-policy/preview/new-AGENTS.md",
        )
        .replace(
            ".agent-policy/preview/policy-details.json",
            ".agent-policy/preview/new-policy-details.json",
        ),
        encoding="utf-8",
    )
    authored = '{"user_data":"KEEP"}\n'
    original_rename = generated_mutation._native_rename_noreplace
    injected = False

    def replace_obsolete_before_detach(
        source_fd: int, source: str, destination_fd: int, destination: str
    ) -> None:
        nonlocal injected
        if source == "policy-details.json" and not injected:
            old_bundle.write_text(authored, encoding="utf-8")
            injected = True
        original_rename(source_fd, source, destination_fd, destination)

    monkeypatch.setattr(
        generated_mutation,
        "_native_rename_noreplace",
        replace_obsolete_before_detach,
    )

    diagnostics = render.run(tmp_path, ".agent-policy.yml")

    assert len(diagnostics) == 1
    assert diagnostics[0].code == "RENDER"
    assert "content or ownership" in diagnostics[0].message
    assert injected
    assert old_startup.read_text(encoding="utf-8") == old_startup_content
    assert old_bundle.read_text(encoding="utf-8") == authored
    assert not (tmp_path / ".agent-policy/preview/new-AGENTS.md").exists()
    assert not (tmp_path / ".agent-policy/preview/new-policy-details.json").exists()


def test_pinned_guidance_rejects_runtime_lock_revision_drift(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    result = _run_pinned_guidance(
        tmp_path,
        "--rule-id",
        GUIDANCE,
        runtime_revision="b" * 40,
    )

    assert result.returncode == 2
    assert "selected runtime revision" in result.stderr


def test_generated_guidance_rechecks_selected_runtime_revision_at_use_boundary(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    config = tmp_path / ".agent-policy.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(TEST_REVISION, "b" * 40),
        encoding="utf-8",
    )
    assert render.run(tmp_path, ".agent-policy.yml") == []

    result = _run_guidance(
        tmp_path,
        "--runtime-revision",
        TEST_REVISION,
        "--rule-id",
        GUIDANCE,
    )

    assert result.returncode == 2
    assert "selected runtime revision" in result.stderr


def test_pinned_guidance_executes_the_authenticated_script_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []
    script = tmp_path / ".agents/skills/policy-guidance/scripts/policy_guidance.py"
    authenticated = script.read_bytes()
    observed: dict[str, object] = {}

    def mutate_during_check(_root: Path, _config: str) -> list[object]:
        script.write_text("print('FORGED AFTER CHECK')\n", encoding="utf-8")
        return []

    def capture_execution(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["input"] = kwargs["input"]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check, "run", mutate_during_check)
    monkeypatch.setattr(guidance_command.subprocess, "run", capture_execution)

    assert (
        guidance_command.run(
            tmp_path,
            config_path=".agent-policy.yml",
            script=".agents/skills/policy-guidance/scripts/policy_guidance.py",
            bundle=None,
            runtime_revision=TEST_REVISION,
            operation=None,
            rule_id=GUIDANCE,
            all_rules=False,
            output_format="text",
        )
        == 0
    )
    assert observed["input"] == authenticated
    assert f"--runtime-revision={TEST_REVISION}" in observed["command"]


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
    ("bundle_path", "config_path"),
    [
        (".agent-policy/preview/policy details &copy.json", ".agent-policy.yml"),
        ("-details.json", ".agent-policy.yml"),
        (".agent-policy/preview/policy-details.json", "-policy.yml"),
    ],
)
def test_generated_guidance_commands_quote_bundle_paths(
    tmp_path: Path, bundle_path: str, config_path: str
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
    if config_path != ".agent-policy.yml":
        config.rename(tmp_path / config_path)

    assert render.run(tmp_path, config_path) == []
    startup = (tmp_path / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )
    skill = (tmp_path / ".agents/skills/policy-guidance/SKILL.md").read_text(
        encoding="utf-8"
    )
    quoted = shlex.quote(bundle_path)
    assert f"--bundle={quoted} --operation" in startup
    assert f"--bundle={quoted} --operation" in skill
    assert "AGENT_POLICY_SKILL_ROOT" in startup
    assert "AGENT_POLICY_SKILL_ROOT" in skill
    assert ".agents/skills/agent-policy/scripts/run.py" not in startup
    assert ".agents/skills/agent-policy/scripts/run.py" not in skill
    config_token = shlex.quote(config_path)
    assert f"--config={config_token}" in startup
    assert f"--config={config_token}" in skill
    assert "--repository <repository>" in startup
    assert "--repository <repository>" in skill
    assert "--root <repository>" not in startup
    assert "--root <repository>" not in skill

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
    source_skill = Path(__file__).parents[1] / "skills/agent-policy"
    runtime_root = tmp_path.parent / f"{tmp_path.name}-installed-agent-policy"
    shutil.copytree(source_skill, runtime_root)
    runtime_module_spec = importlib.util.spec_from_file_location(
        "test_external_agent_policy_runtime",
        runtime_root / "scripts/runtime.py",
    )
    assert runtime_module_spec and runtime_module_spec.loader
    runtime_module = importlib.util.module_from_spec(runtime_module_spec)
    sys.modules[runtime_module_spec.name] = runtime_module
    runtime_module_spec.loader.exec_module(runtime_module)

    cache = tmp_path.parent / f"{tmp_path.name}-runtime-cache"
    pin = runtime_module.RuntimePin(
        "TakashiSasaki/templates",
        TEST_REVISION,
        "requirements-runtime.lock",
        None,
        "takashisasaki-agent-policy",
        None,
        "agent-policy",
    )
    identity = runtime_module.RuntimeIdentity(
        pin.repository,
        pin.revision,
        "c" * 64,
        runtime_module.python_token(),
        runtime_module.platform_token(),
    )
    cached_runtime = cache / identity.digest()
    venv.EnvBuilder(with_pip=False, system_site_packages=True).create(
        cached_runtime / "venv"
    )
    runtime_python = runtime_module.venv_python(cached_runtime)
    site_packages = Path(
        subprocess.check_output(
            [str(runtime_python), "-I", "-c", "import site; print(site.getsitepackages()[0])"],
            text=True,
        ).strip()
    )
    installed_package = site_packages / "agent_policy"
    shutil.copytree(
        Path(__file__).parents[1] / "src/agent_policy",
        installed_package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    data_root = installed_package / "_data"
    for resource in ("schemas", "profiles", "policy", "templates", "skills", "delivery"):
        shutil.copytree(Path(__file__).parents[1] / resource, data_root / resource)
    executable = runtime_module.executable_path(cached_runtime, pin.executable)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    runtime_module.marker_path(cached_runtime).write_text(
        json.dumps(runtime_module.expected_marker(identity, pin, "0.1.0")) + "\n",
        encoding="utf-8",
    )

    package_location = subprocess.check_output(
        [str(runtime_python), "-I", "-c", "import agent_policy; print(agent_policy.__file__)"],
        text=True,
    ).strip()
    assert str(installed_package) in package_location
    assert str(Path(__file__).parents[1] / "src") not in package_location
    nested = tmp_path / "nested" / "work"
    nested.mkdir(parents=True)
    nested_result = subprocess.run(
        [
            sys.executable,
            str(runtime_root / "scripts/run.py"),
            "--repository",
            str(tmp_path),
            "guidance",
            f"--config={config_path}",
            "--script",
            ".agents/skills/policy-guidance/scripts/policy_guidance.py",
            f"--bundle={bundle_path}",
            "--rule-id",
            GUIDANCE,
        ],
        cwd=nested,
        check=False,
        capture_output=True,
        text=True,
        env={
            key: value
            for key, value in {
                **environment,
                "AGENT_POLICY_RUNTIME_CACHE": str(cache),
            }.items()
            if key != "PYTHONPATH"
        },
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


def _write_dual_output_repository(
    root: Path,
    *,
    profiles: list[str] | None = None,
    project_policy_files: list[str] | None = None,
    overrides: list[dict[str, str]] | None = None,
) -> None:
    (root / ".git").mkdir(exist_ok=True)
    if project_policy_files is None:
        project_policy_files = ["policy/project.md"]
        (root / "policy").mkdir(parents=True, exist_ok=True)
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
    profile_items = profiles if profiles is not None else ["core"]
    profiles_yaml = "\n".join(f"      - {p}" for p in profile_items)
    files_yaml = (
        "\n".join(f"        - {f}" for f in project_policy_files)
        if project_policy_files
        else "        []"
    )
    overrides_block = ""
    if overrides:
        overrides_yaml = "\n".join(
            f"      - id: {item['id']}\n        reason: {json.dumps(item['reason'])}"
            for item in overrides
        )
        overrides_block = f"    overrides:\n{overrides_yaml}\n"
    (root / ".agent-policy.yml").write_text(
        f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {TEST_REVISION}
contexts:
  coding:
    profiles:
{profiles_yaml}
    project_policy:
      files:
{files_yaml}
{overrides_block}outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: coding
    renderer: agents-md
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


def test_full_and_staged_renderer_semantic_parity_for_identical_context(
    tmp_path: Path,
) -> None:
    _write_dual_output_repository(tmp_path)

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []

    config = load_config(tmp_path, ".agent-policy.yml")
    context = config.contexts["coding"]
    canonical_rules = load_rules(
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
    full_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    startup_text = (tmp_path / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )

    bundled_rules = bundle["rules"]
    assert len(bundled_rules) == len(canonical_rules)
    canonical_selected_ids = [rule.id for rule in canonical_rules]
    staged_detail_ids = [item["id"] for item in bundled_rules]
    full_rendered_ids = re.findall(r"rule ID: `([^`]+)`", full_text)

    # Prove canonical selected rule IDs == staged detail-bundle rule IDs
    # == full AGENTS.md rule IDs in rendered order
    assert canonical_selected_ids == staged_detail_ids == full_rendered_ids

    # Verify field-by-field parity across real loaded rules, bundle rules, and full projection
    for bundled, canonical in zip(bundled_rules, canonical_rules, strict=True):
        assert bundled["id"] == canonical.id
        assert bundled["title"] == canonical.title
        assert bundled["severity"] == canonical.severity
        assert bundled["overridable"] == canonical.overridable
        assert bundled["order"] == canonical.order
        assert bundled["origin"] == canonical.origin
        assert bundled["source"] == canonical.source
        assert bundled["body"] == canonical.body
        assert bundled["body_sha256"] == hashlib.sha256(canonical.body.encode("utf-8")).hexdigest()

        # Full AGENTS.md represents the same final selected rule
        assert f"## {canonical.title}" in full_text
        body_snippet = (
            canonical.body.split("\n", 1)[1].strip()
            if "\n" in canonical.body
            else canonical.body
        )
        assert body_snippet in full_text

        if canonical.origin == "toolchain":
            expected_provenance = (
                f"_Source: `TakashiSasaki/templates@{TEST_REVISION}:{canonical.source}`; "
                f"rule ID: `{canonical.id}`; severity: `{canonical.severity}`._"
            )
            assert expected_provenance in full_text
        else:
            expected_provenance = (
                f"_Source: `{canonical.source}` in this repository; "
                f"rule ID: `{canonical.id}`; severity: `{canonical.severity}`._"
            )
            assert expected_provenance in full_text

    # Bindings match the configuration context
    assert bundle["bindings"]["context"]["name"] == "coding"
    assert bundle["bindings"]["context"]["profiles"] == ["core"]
    assert bundle["bindings"]["context"]["project_policy_files"] == ["policy/project.md"]
    assert bundle["bindings"]["context"]["overrides"] == {}

    # Startup file presents a subset of already-selected rules
    startup_rules = [
        r for r in bundled_rules if any(
            route["id"] == r["id"] and route["startup"]
            for route in bundle["presentation"]["routes"]
        )
    ]
    assert len(startup_rules) < len(bundled_rules)
    for s_rule in startup_rules:
        assert s_rule["title"] in startup_text


def test_full_and_staged_renderer_override_parity(tmp_path: Path) -> None:
    (tmp_path / "policy").mkdir(parents=True, exist_ok=True)
    override_path = tmp_path / "policy/override.md"
    override_path.write_text(
        """---
id: testing.require-adversarial-invariant-coverage
severity: mandatory
overridable: false
order: 33
---
# Local specialized requirement for adversarial coverage

Repository-local specialized adversarial test coverage is mandatory.
""",
        encoding="utf-8",
    )
    _write_dual_output_repository(
        tmp_path,
        profiles=["core"],
        project_policy_files=["policy/override.md"],
        overrides=[
            {
                "id": "testing.require-adversarial-invariant-coverage",
                "reason": "Specialized repository-local invariant coverage rules",
            }
        ],
    )

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []

    bundle = json.loads(
        (tmp_path / ".agent-policy/preview/policy-details.json").read_text(
            encoding="utf-8"
        )
    )
    full_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    # Prove ordering parity under overrides across all representations
    config = load_config(tmp_path, ".agent-policy.yml")
    context = config.contexts["coding"]
    canonical_rules = load_rules(
        tmp_path,
        list(context.profiles),
        list(context.project_policy_files),
        declared_overrides=context.override_reasons,
        require_explicit_overrides=True,
    )
    canonical_selected_ids = [rule.id for rule in canonical_rules]
    staged_detail_ids = [item["id"] for item in bundle["rules"]]
    full_rendered_ids = re.findall(r"rule ID: `([^`]+)`", full_text)
    assert canonical_selected_ids == staged_detail_ids == full_rendered_ids

    # In bundle: exactly one rule with the overridden ID, with project origin
    matching_bundle_rules = [
        r for r in bundle["rules"]
        if r["id"] == "testing.require-adversarial-invariant-coverage"
    ]
    assert len(matching_bundle_rules) == 1
    overridden_rule = matching_bundle_rules[0]
    assert overridden_rule["origin"] == "repository"
    assert overridden_rule["source"] == "policy/override.md"
    assert overridden_rule["title"] == "Local specialized requirement for adversarial coverage"
    assert overridden_rule["body"] == (
        "# Local specialized requirement for adversarial coverage\n\n"
        "Repository-local specialized adversarial test coverage is mandatory."
    )
    assert bundle["bindings"]["context"]["overrides"] == {
        "testing.require-adversarial-invariant-coverage": (
            "Specialized repository-local invariant coverage rules"
        )
    }

    # In full AGENTS.md: replacement appears, original does not; rule appears exactly once
    assert "Local specialized requirement for adversarial coverage" in full_text
    assert "Repository-local specialized adversarial test coverage is mandatory." in full_text
    expected_override_source = (
        "_Source: `policy/override.md` in this repository; "
        "rule ID: `testing.require-adversarial-invariant-coverage`"
    )
    assert expected_override_source in full_text
    # Original toolchain rule content must NOT be present
    original_toolchain_fragment = (
        "Adversarial and boundary test coverage is required for policy and security invariants."
    )
    assert original_toolchain_fragment not in full_text
    assert full_text.count("rule ID: `testing.require-adversarial-invariant-coverage`") == 1

    # Guidance retrieval serves the overridden replacement rule
    result = _run_guidance(
        tmp_path, "--rule-id", "testing.require-adversarial-invariant-coverage"
    )
    assert result.returncode == 0
    assert "Local specialized requirement for adversarial coverage" in result.stdout
    assert "Repository-local specialized adversarial test coverage is mandatory." in result.stdout
    assert "Source: policy/override.md" in result.stdout


def test_scenario_a_ordinary_full_consumer(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".agent-policy.yml").write_text(
        f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {TEST_REVISION}
contexts:
  coding:
    profiles:
      - core
    project_policy:
      files: []
outputs:
  agents:
    enabled: true
    path: AGENTS.md
    context: coding
    renderer: agents-md
skills:
  enabled: []
""",
        encoding="utf-8",
    )

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []

    agents_path = tmp_path / "AGENTS.md"
    assert agents_path.is_file()
    agents_text = agents_path.read_text(encoding="utf-8")
    assert "core.discover-repository-topology-fail-closed" in agents_text
    assert "policy-repo." not in agents_text

    # No staged artifacts exist or are required
    assert not (tmp_path / ".agent-policy/preview/policy-details.json").exists()
    assert not (tmp_path / ".agents/skills/policy-guidance").exists()


def test_scenario_b_equivalent_staged_consumer(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".agent-policy.yml").write_text(
        f"""schema_version: 2
toolchain:
  repository: TakashiSasaki/templates
  revision: {TEST_REVISION}
contexts:
  coding:
    profiles:
      - core
    project_policy:
      files: []
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

    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert render.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []

    bundle = json.loads(
        (tmp_path / ".agent-policy/preview/policy-details.json").read_text(
            encoding="utf-8"
        )
    )
    startup_text = (tmp_path / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )

    # Identical normative selected rules as Scenario A
    canonical_rules = load_rules(tmp_path, ["core"], [])
    assert [r["id"] for r in bundle["rules"]] == [r.id for r in canonical_rules]

    # No provider-maintainer rules leak
    assert not any(r["id"].startswith("policy-repo.") for r in bundle["rules"])
    assert "policy-repo." not in startup_text

    # Operation-specific guidance retrieves from authenticated bundle
    result = _run_guidance(tmp_path, "--operation", "edit")
    assert result.returncode == 0
    assert "core.discover-repository-topology-fail-closed" in result.stdout


def _isolate_package_root(
    destination: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    canonical = package_root()
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("schemas", "templates", "delivery", "policy", "profiles", "skills"):
        shutil.copytree(canonical / name, destination / name)

    import agent_policy.adoption
    import agent_policy.commands.adopt
    import agent_policy.commands.init
    import agent_policy.config
    import agent_policy.delivery
    import agent_policy.policy_loader
    import agent_policy.renderer

    for module in (
        agent_policy.adoption,
        agent_policy.commands.adopt,
        agent_policy.commands.init,
        agent_policy.config,
        agent_policy.delivery,
        agent_policy.policy_loader,
        agent_policy.renderer,
    ):
        monkeypatch.setattr(module, "package_root", lambda: destination)

    monkeypatch.setattr(
        agent_policy.delivery,
        "DELIVERY_MAP_PATH",
        destination / agent_policy.delivery.DELIVERY_MAP_RELATIVE,
    )
    return destination


def test_scenario_c_applicability_rule_selected_as_startup_boundary_and_in_every_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root = package_root()
    # Guard: canonical worktree profile must NOT exist before, during, or after test
    assert not (canonical_root / "profiles/fixture-applicability-p2.yml").exists()

    isolated_pkg = _isolate_package_root(tmp_path / "pkg", monkeypatch)
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    fixture_profile_path = isolated_pkg / "profiles/fixture-applicability-p2.yml"
    fixture_profile_path.write_text(
        """policy_files:
  - policy/core/repository-topology-discovery.md
  - policy/core/local-checkout-topology-discovery.md
  - policy/core/change-contract.md
  - policy/core/acceptance-baseline.md
  - policy/core/change-scope.md
  - policy/core/semantic-decision-gates.md
  - policy/core/regression-safety.md
  - policy/core/testing.md
  - policy/core/adversarial-invariant-testing.md
  - policy/core/evidence-layers.md
  - policy/core/generated-artifacts.md
  - policy/core/compatibility.md
  - policy/core/destructive-actions.md
  - policy/core/validation-operation-binding.md
  - policy/core/transaction-ownership.md
  - policy/core/truthful-reporting.md
  - policy/core/repository-change-completion.md
  - policy/core/repository-change-anti-stall.md
  - policy/core/policy-applicability.md
""",
        encoding="utf-8",
    )
    # Regression guard: writing to isolated package root does not touch canonical root
    assert not (canonical_root / "profiles/fixture-applicability-p2.yml").exists()

    _write_dual_output_repository(
        repo_root,
        profiles=["fixture-applicability-p2"],
        project_policy_files=[],
    )

    assert validate.run(repo_root, ".agent-policy.yml") == []
    assert render.run(repo_root, ".agent-policy.yml") == []
    assert check.run(repo_root, ".agent-policy.yml") == []

    bundle = json.loads(
        (repo_root / ".agent-policy/preview/policy-details.json").read_text(
            encoding="utf-8"
        )
    )
    full_text = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    startup_text = (repo_root / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )

    # 1. Applicability rule is selected
    assert "core.scope-applicability-to-target" in [r["id"] for r in bundle["rules"]]

    # 1b. Ordering parity: canonical selected rule IDs == staged detail rule IDs
    # == full AGENTS.md rendered order
    config = load_config(repo_root, ".agent-policy.yml")
    context = config.contexts["coding"]
    canonical_rules = load_rules(
        repo_root,
        list(context.profiles),
        list(context.project_policy_files),
        declared_overrides=context.override_reasons,
        require_explicit_overrides=True,
    )
    canonical_selected_ids = [rule.id for rule in canonical_rules]
    staged_detail_ids = [r["id"] for r in bundle["rules"]]
    full_rendered_ids = re.findall(r"rule ID: `([^`]+)`", full_text)
    assert canonical_selected_ids == staged_detail_ids == full_rendered_ids

    # 2. Present in full AGENTS.md with toolchain origin
    expected_title = "Scope policy and instruction applicability to the governed target"
    assert expected_title in full_text
    provenance = (
        f"TakashiSasaki/templates@{TEST_REVISION}:policy/core/policy-applicability.md"
    )
    assert provenance in full_text
    assert "rule ID: `core.scope-applicability-to-target`" in full_text

    # 3. Startup presentation: included in startup_rules as an essential startup boundary
    assert f"### {expected_title}" in startup_text
    assert "rule ID: `core.scope-applicability-to-target`" in startup_text

    # 4. Detail bundle carries full text and metadata
    p1_rule = next(
        r for r in bundle["rules"] if r["id"] == "core.scope-applicability-to-target"
    )
    assert p1_rule["title"] == expected_title
    assert p1_rule["severity"] == "mandatory"
    assert p1_rule["overridable"] is False
    assert p1_rule["order"] == 48
    assert p1_rule["origin"] == "toolchain"
    assert p1_rule["source"] == "policy/core/policy-applicability.md"
    assert "Distinguish four operational relationships:" in p1_rule["body"]

    # 5. Every single supported operation route includes the applicability rule
    supported_operations = [
        "inspect",
        "plan",
        "edit",
        "generate",
        "validate",
        "review",
        "merge",
        "publish",
    ]
    for operation in supported_operations:
        result = _run_guidance(repo_root, "--operation", operation)
        assert result.returncode == 0, f"--operation {operation} failed: {result.stderr}"
        assert "core.scope-applicability-to-target" in result.stdout
        assert expected_title in result.stdout

    # 6. Fallback and single-rule retrieval also include it
    result_all = _run_guidance(repo_root, "--all")
    assert result_all.returncode == 0
    assert "core.scope-applicability-to-target" in result_all.stdout

    result_single = _run_guidance(repo_root, "--rule-id", "core.scope-applicability-to-target")
    assert result_single.returncode == 0
    assert expected_title in result_single.stdout

    # 7. Regression check: canonical package root remained completely clean
    assert not (canonical_root / "profiles/fixture-applicability-p2.yml").exists()


def test_scenario_c_preserves_canonical_package_root_isolation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical_root = package_root()
    fixture_in_canonical = canonical_root / "profiles/fixture-applicability-p2.yml"
    assert not fixture_in_canonical.exists()

    core_profile_bytes = (canonical_root / "profiles/core.yml").read_bytes()
    presentation_map_bytes = (canonical_root / "delivery/presentation-map.yml").read_bytes()

    test_scenario_c_applicability_rule_selected_as_startup_boundary_and_in_every_operation(
        tmp_path, monkeypatch
    )

    assert not fixture_in_canonical.exists()
    assert (canonical_root / "profiles/core.yml").read_bytes() == core_profile_bytes
    assert (canonical_root / "delivery/presentation-map.yml").read_bytes() == presentation_map_bytes


def test_scenario_d_presentation_map_entry_alone_does_not_select_applicability_rule(
    tmp_path: Path,
) -> None:
    _write_dual_output_repository(tmp_path, profiles=["security-baseline"], project_policy_files=[])

    assert render.run(tmp_path, ".agent-policy.yml") == []

    full_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    startup_text = (tmp_path / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )
    bundle = json.loads(
        (tmp_path / ".agent-policy/preview/policy-details.json").read_text(
            encoding="utf-8"
        )
    )

    # Negative assertion: P1 is not in full output
    assert "core.scope-applicability-to-target" not in full_text
    assert "Scope policy and instruction applicability to the governed target" not in full_text

    # Negative assertion: P1 is not in staged startup
    assert "core.scope-applicability-to-target" not in startup_text
    assert "Scope policy and instruction applicability to the governed target" not in startup_text

    # Negative assertion: P1 is not in bundle rules or operation routes
    assert "core.scope-applicability-to-target" not in [r["id"] for r in bundle["rules"]]
    for _op, ids in bundle["presentation"]["operation_routes"].items():
        assert "core.scope-applicability-to-target" not in ids

    # Negative assertion: Guidance retrieval rejects unselected rule
    result = _run_guidance(tmp_path, "--rule-id", "core.scope-applicability-to-target")
    assert result.returncode == 2
    assert "unknown selected rule: core.scope-applicability-to-target" in result.stderr


def test_candidate_core_profile_selects_applicability_rule_with_staged_delivery_parity(
    tmp_path: Path,
) -> None:
    """Candidate core profile selects applicability rule with full parity across outputs."""
    _write_dual_output_repository(tmp_path, profiles=["core"], project_policy_files=[])

    assert render.run(tmp_path, ".agent-policy.yml") == []

    full_text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    startup_text = (tmp_path / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )
    bundle = json.loads(
        (tmp_path / ".agent-policy/preview/policy-details.json").read_text(
            encoding="utf-8"
        )
    )

    # 1. Full AGENTS.md includes the applicability rule
    assert "core.scope-applicability-to-target" in full_text
    assert "Scope policy and instruction applicability to the governed target" in full_text

    # 2. Staged startup AGENTS.md includes the applicability rule
    assert "core.scope-applicability-to-target" in startup_text
    assert "Scope policy and instruction applicability to the governed target" in startup_text

    # 3. Detail bundle contains rule with proper metadata
    bundled_rules = bundle["rules"]
    matching = [r for r in bundled_rules if r["id"] == "core.scope-applicability-to-target"]
    assert len(matching) == 1
    rule_entry = matching[0]
    assert rule_entry["origin"] == "toolchain"
    assert rule_entry["severity"] == "mandatory"
    assert rule_entry["overridable"] is False
    assert rule_entry["order"] == 48

    # 4. Route parity: applicability rule mapped across all 8 operation routes
    expected_operations = [
        "inspect", "plan", "edit", "generate",
        "validate", "review", "merge", "publish",
    ]
    operation_routes = bundle["presentation"]["operation_routes"]
    for op in expected_operations:
        assert op in operation_routes
        assert "core.scope-applicability-to-target" in operation_routes[op]

    # 5. Exact ID ordering: order 48 placed between order 46 and order 50
    bundle_ids = [r["id"] for r in bundled_rules]
    idx_46 = bundle_ids.index("core.discover-local-checkout-topology-fail-closed")
    idx_48 = bundle_ids.index("core.scope-applicability-to-target")
    idx_50 = bundle_ids.index("changes.define-contract")
    assert idx_46 + 1 == idx_48
    assert idx_48 + 1 == idx_50

    # 6. Retrieval via guidance command succeeds
    result = _run_guidance(tmp_path, "--rule-id", "core.scope-applicability-to-target")
    assert result.returncode == 0
    assert "Scope policy and instruction applicability to the governed target" in result.stdout



def test_scenario_f_unmapped_selected_rule_fails_closed_for_operation_retrieval(
    tmp_path: Path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "policy").mkdir(parents=True, exist_ok=True)
    (tmp_path / "policy/unmapped.md").write_text(
        """---
id: project.unmapped-custom-rule
severity: mandatory
overridable: false
order: 9999
---
# Unmapped custom rule

This local rule is selected but intentionally unmapped in presentation-map.yml.
""",
        encoding="utf-8",
    )
    (tmp_path / ".agent-policy.yml").write_text(
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
        - policy/unmapped.md
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

    assert render.run(tmp_path, ".agent-policy.yml") == []

    bundle = json.loads(
        (tmp_path / ".agent-policy/preview/policy-details.json").read_text(
            encoding="utf-8"
        )
    )
    assert bundle["presentation"]["unmapped_rule_ids"] == ["project.unmapped-custom-rule"]

    # Operation-specific guidance fails closed
    blocked = _run_guidance(tmp_path, "--operation", "edit")
    assert blocked.returncode == 2
    assert "operation route is incomplete for selected rules; rerun with --all" in blocked.stderr

    # Fallback complete retrieval remains available
    allowed = _run_guidance(tmp_path, "--all")
    assert allowed.returncode == 0
    assert "project.unmapped-custom-rule" in allowed.stdout
    assert "Unmapped custom rule" in allowed.stdout

    # Single-rule retrieval remains available
    single = _run_guidance(tmp_path, "--rule-id", "project.unmapped-custom-rule")
    assert single.returncode == 0
    assert "Unmapped custom rule" in single.stdout


def test_staged_startup_framing_identifies_presentation_boundaries(
    tmp_path: Path,
) -> None:
    _write_staged_repository(tmp_path)
    assert render.run(tmp_path, ".agent-policy.yml") == []

    startup = (tmp_path / ".agent-policy/preview/AGENTS.md").read_text(
        encoding="utf-8"
    )

    assert "- Semantic configuration: `.agent-policy.yml`" in startup
    assert "- Selected context: `coding`" in startup
    assert "- Presentation mode: staged (`agents-md-staged`)" in startup
    assert f"- Pinned shared toolchain: `TakashiSasaki/templates@{TEST_REVISION}`" in startup
    assert "- Detail bundle: `.agent-policy/preview/policy-details.json`" in startup
    assert "This file presents rules already selected by the configured Policy context" in startup
    assert "Presentation metadata cannot select, add, or change rule applicability" in startup

