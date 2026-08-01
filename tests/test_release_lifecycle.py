from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from jsonschema import Draft202012Validator

from agent_policy.adoption import AdoptionSource, build_adoption_state
from agent_policy.manifest import build_manifest
from agent_policy.renderer import render_consumer_workflow

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release/toolchain.json"
RELEASE_SCHEMA = ROOT / "schemas/toolchain-release.schema.json"
CONFIG_SCHEMA = ROOT / "schemas/agent-policy.schema.json"
ADOPTION_SCHEMA = ROOT / "schemas/adoption-state.schema.json"
BOOTSTRAP = ROOT / "skills/bootstrap-agent-policy/bootstrap-manifest.yml"
WORKFLOW = ROOT / ".github/workflows/ci.yml"
VERIFIER_REQUIREMENTS = ROOT / "release/verifier-requirements.lock"


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def load_script() -> ModuleType:
    path = ROOT / "scripts/verify-release-state.py"
    spec = importlib.util.spec_from_file_location("verify_release_state", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_script()


def non_comment_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_stable_release_descriptor_is_valid_and_matches_bootstrap() -> None:
    release = load_object(RELEASE)
    schema = load_object(RELEASE_SCHEMA)
    bootstrap = load_object(BOOTSTRAP)

    Draft202012Validator(schema).validate(release)
    assert release["toolchain"] == bootstrap["toolchain"]
    assert release["channel"] == "stable"
    assert release["verifier"] == {
        "requirements": "release/verifier-requirements.lock"
    }


def test_release_schema_allows_prior_stable_contract_versions() -> None:
    schema = load_object(RELEASE_SCHEMA)
    contract_properties = schema["properties"]["contracts"]["properties"]  # type: ignore[index]

    assert isinstance(contract_properties, dict)
    for name in (
        "agent_policy_schema",
        "adoption_state_schema",
        "bootstrap_manifest",
        "lock",
    ):
        assert contract_properties[name] == {"type": "integer", "minimum": 1}


def test_stable_release_verifier_dependencies_are_fully_locked() -> None:
    expected = [
        "attrs==26.1.0",
        "Jinja2==3.1.6",
        "jsonschema==4.26.0",
        "jsonschema-specifications==2025.9.1",
        "MarkupSafe==3.0.3",
        "PyYAML==6.0.3",
        "referencing==0.37.0",
        "rpds-py==2026.6.3",
        "typing_extensions==4.16.0",
    ]

    assert non_comment_lines(VERIFIER_REQUIREMENTS) == expected
    assert verifier.locked_requirements(VERIFIER_REQUIREMENTS) == tuple(expected)


def test_release_verifier_rejects_non_exact_or_duplicate_requirements(
    tmp_path: Path,
) -> None:
    non_exact = tmp_path / "non-exact.lock"
    non_exact.write_text("PyYAML>=6\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact name==version"):
        verifier.locked_requirements(non_exact)

    duplicate = tmp_path / "duplicate.lock"
    duplicate.write_text("PyYAML==6.0.3\npyyaml==6.0.3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicated"):
        verifier.locked_requirements(duplicate)


def test_configuration_and_adoption_schemas_share_the_toolchain_contract() -> None:
    config_schema = load_object(CONFIG_SCHEMA)
    adoption_schema = load_object(ADOPTION_SCHEMA)

    config_toolchain = config_schema["properties"]["toolchain"]  # type: ignore[index]
    adoption_toolchain = adoption_schema["properties"]["toolchain"]  # type: ignore[index]
    assert config_toolchain == adoption_toolchain


def test_generated_release_artifacts_share_one_full_sha() -> None:
    release = load_object(RELEASE)
    toolchain = release["toolchain"]
    assert isinstance(toolchain, dict)
    revision = toolchain["revision"]
    assert isinstance(revision, str)

    manifest = build_manifest(
        toolchain_revision=revision,
        profiles=["core"],
        project_policy_files=["policy/project.md"],
        verification_command=None,
        agents_output_enabled=True,
        agents_output_path="AGENTS.md",
        enabled_skills=[],
    )
    adoption = build_adoption_state(
        toolchain_revision=revision,
        config_path=".agent-policy.yml",
        state_path=".agent-policy/adoption.json",
        primary_instructions="AGENTS.md",
        sources=(AdoptionSource("AGENTS.md", "a" * 64, False),),
        preview_output=".agent-policy/preview/AGENTS.md",
        selected_profiles=["core"],
        project_policy_files=["policy/project.md"],
        verification_command=None,
        generated_skills=[],
    )
    workflow = render_consumer_workflow(revision)

    assert manifest["toolchain"] == toolchain
    assert adoption["toolchain"] == toolchain
    assert f"uses: {toolchain['repository']}@{revision}" in workflow
    assert "{{ revision }}" not in workflow


def test_policy_ci_fetches_only_the_current_source_history() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "refs/pull/${PR_NUMBER}/head" in workflow
    assert "PUSH_REF: ${{ github.ref }}" in workflow
    assert 'source_ref="$PUSH_REF"' in workflow
    assert "refs/remotes/origin/policy-source" in workflow
    assert "refs/heads/main" not in workflow
    assert "refs/heads/site" not in workflow
    assert "refs/heads/webapp" not in workflow
    assert "python scripts/verify-release-state.py" in workflow


def test_pinned_probe_environment_installs_only_the_release_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_create(_self: object, environment_root: Path) -> None:
        python = verifier.probe_python_path(Path(environment_root))
        python.parent.mkdir(parents=True)
        python.write_text("", encoding="utf-8")

    def fake_run(
        arguments: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(verifier.venv.EnvBuilder, "create", fake_create)
    monkeypatch.setattr(verifier.subprocess, "run", fake_run)

    with verifier.pinned_probe_environment() as python:
        assert python.name in {"python", "python.exe"}

    install = calls[0]
    assert install[0] == str(python)
    assert install[1:4] == ["-m", "pip", "install"]
    assert "--no-deps" in install
    assert "--only-binary=:all:" in install
    assert install[-2:] == ["-r", str(VERIFIER_REQUIREMENTS)]
    assert calls[1] == [str(python), "-m", "pip", "check"]


def test_pinned_probe_uses_the_supplied_isolated_python(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    probe_python = tmp_path / "probe-venv/bin/python"
    tree = tmp_path / "tree"
    tree.mkdir()
    observed: dict[str, object] = {}

    def fake_check_output(
        arguments: list[str],
        **kwargs: object,
    ) -> str:
        observed["arguments"] = arguments
        observed["environment"] = kwargs["env"]
        return "{}"

    monkeypatch.setattr(verifier.subprocess, "check_output", fake_check_output)

    assert verifier.run_pinned_probe(tree, "a" * 40, probe_python) == {}
    assert observed["arguments"] == [
        str(probe_python),
        "-s",
        "-c",
        verifier.PINNED_PROBE,
    ]
    environment = observed["environment"]
    assert isinstance(environment, dict)
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert environment["PYTHONPATH"] == str(tree / "src")
    assert environment["RELEASE_REVISION"] == "a" * 40
