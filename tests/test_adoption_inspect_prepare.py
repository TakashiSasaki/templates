import hashlib
import json
from pathlib import Path

import pytest

from agent_policy.adoption import inspect_repository
from agent_policy.cli import parser
from agent_policy.commands import adopt, check, validate
from agent_policy.renderer import GENERATED_MARKER


def _initialize_repository(path: Path) -> None:
    (path / ".git").mkdir()


def _write_policy(path: Path, rule_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
id: {rule_id}
severity: mandatory
overridable: true
order: 1000
---
# Rule

Body.
""",
        encoding="utf-8",
    )


def test_inspect_classifies_empty_and_existing_repositories(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    assert inspect_repository(tmp_path).state == "unmanaged-empty"

    agents = tmp_path / "AGENTS.md"
    agents.write_text("handwritten instructions\n", encoding="utf-8")
    _write_policy(tmp_path / ".agents/policies/local.md", "project.local")

    inspection = inspect_repository(tmp_path)
    assert inspection.state == "unmanaged-existing"
    sources = {item.path: item for item in inspection.sources}
    assert set(sources) == {".agents/policies/local.md", "AGENTS.md"}
    assert sources["AGENTS.md"].sha256 == hashlib.sha256(agents.read_bytes()).hexdigest()
    assert sources["AGENTS.md"].generated is False


def test_inspect_and_prepare_preserve_symlink_source_names(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("shared handwritten instructions\n", encoding="utf-8")
    agents = tmp_path / "AGENTS.md"
    try:
        agents.symlink_to(claude.name)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    inspection = inspect_repository(tmp_path)
    sources = {item.path: item for item in inspection.sources}
    assert set(sources) == {"AGENTS.md", "CLAUDE.md"}
    assert sources["AGENTS.md"].sha256 == sources["CLAUDE.md"].sha256

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        primary_instructions="AGENTS.md",
        enabled_skills=[],
    )

    assert diagnostics == []
    assert agents.is_symlink()
    state = json.loads((tmp_path / ".agent-policy/adoption.json").read_text(encoding="utf-8"))
    assert state["primary_instructions"] == "AGENTS.md"
    assert [item["path"] for item in state["sources"]] == ["AGENTS.md", "CLAUDE.md"]


def test_inspect_classifies_partial_generated_state_as_inconsistent(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        f"<!-- {GENERATED_MARKER} -->\n",
        encoding="utf-8",
    )

    inspection = inspect_repository(tmp_path)
    assert inspection.state == "inconsistent"
    assert inspection.sources[0].generated is True


def test_prepare_dry_run_validates_without_writing(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
    )

    assert not any(item.level == "error" for item in diagnostics)
    assert {item.code for item in diagnostics} >= {"PRESERVE", "CREATE", "GENERATE"}
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".agent-policy").exists()
    assert not (tmp_path / "policy/project.md").exists()
    assert not (tmp_path / ".agent-policy.lock").exists()


def test_prepare_dry_run_rejects_unknown_profile_before_writing(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["missing-profile"],
    )

    assert any(item.code == "UNKNOWN_PROFILE" for item in diagnostics)
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".agent-policy").exists()


def test_prepare_preserves_primary_and_creates_preview_state(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text("handwritten instructions\n", encoding="utf-8")
    original = agents.read_bytes()

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core", "security-baseline"],
        verification_command="npm run verify:pr",
    )

    assert diagnostics == []
    assert agents.read_bytes() == original
    assert (tmp_path / ".agent-policy.yml").is_file()
    assert (tmp_path / ".agent-policy/adoption.json").is_file()
    assert (tmp_path / ".agent-policy/preview/AGENTS.md").is_file()
    assert (tmp_path / "policy/project.md").is_file()
    assert (tmp_path / ".agent-policy.lock").is_file()
    assert (tmp_path / ".agents/skills/validate-agent-policy/SKILL.md").is_file()

    state = json.loads((tmp_path / ".agent-policy/adoption.json").read_text(encoding="utf-8"))
    assert state["status"] == "prepared"
    assert state["primary_instructions"] == "AGENTS.md"
    assert state["preview_output"] == ".agent-policy/preview/AGENTS.md"
    assert state["verification_command"] == "npm run verify:pr"
    assert state["sources"] == [
        {
            "generated": False,
            "path": "AGENTS.md",
            "sha256": hashlib.sha256(original).hexdigest(),
        }
    ]
    assert validate.run(tmp_path, ".agent-policy.yml") == []
    assert check.run(tmp_path, ".agent-policy.yml") == []
    assert inspect_repository(tmp_path).state == "managed"


def test_prepare_reuses_multiple_existing_project_policies(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")
    first = tmp_path / ".agents/policies/first.md"
    second = tmp_path / ".agents/policies/second.md"
    _write_policy(first, "project.first")
    _write_policy(second, "project.second")
    originals = {first: first.read_bytes(), second: second.read_bytes()}

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        project_policy_files=[
            ".agents/policies/first.md",
            ".agents/policies/second.md",
        ],
        enabled_skills=[],
    )

    assert diagnostics == []
    assert all(path.read_bytes() == content for path, content in originals.items())
    assert check.run(tmp_path, ".agent-policy.yml") == []
    state = json.loads((tmp_path / ".agent-policy/adoption.json").read_text(encoding="utf-8"))
    assert state["project_policy_files"] == [
        ".agents/policies/first.md",
        ".agents/policies/second.md",
    ]
    assert state["generated_skills"] == []


def test_prepare_rejects_existing_generated_skill_tree_overlap(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")
    readme = tmp_path / ".agents/skills/validate-agent-policy/README.md"
    readme.parent.mkdir(parents=True)
    readme.write_text("handwritten skill documentation\n", encoding="utf-8")
    original = readme.read_bytes()

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
    )

    assert diagnostics[0].code == "ADOPT_PREPARE"
    assert ".agents/skills/validate-agent-policy/README.md" in diagnostics[0].message
    assert readme.read_bytes() == original
    assert not (tmp_path / ".agents/skills/validate-agent-policy/SKILL.md").exists()
    assert not (tmp_path / ".agent-policy.yml").exists()
    assert not (tmp_path / ".agent-policy.lock").exists()


def test_prepare_without_generated_skills_preserves_handwritten_default_skill(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_text("handwritten\n", encoding="utf-8")
    skill = tmp_path / ".agents/skills/validate-agent-policy/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("handwritten skill\n", encoding="utf-8")
    original = skill.read_bytes()

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=True,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        enabled_skills=[],
    )

    assert diagnostics == []
    assert skill.read_bytes() == original
    state = json.loads((tmp_path / ".agent-policy/adoption.json").read_text(encoding="utf-8"))
    assert state["generated_skills"] == []


def test_write_new_file_does_not_remove_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "concurrent.txt"
    target.write_bytes(b"created by another process\n")

    with pytest.raises(FileExistsError):
        adopt._write_new_file(target, b"agent-policy output\n")

    assert target.read_bytes() == b"created by another process\n"


def test_prepare_rejects_wrong_primary_and_managed_repository(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("handwritten\n", encoding="utf-8")

    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
    )
    assert diagnostics[0].code == "PRIMARY_INSTRUCTIONS"

    (tmp_path / ".agent-policy.yml").write_text("managed: true\n", encoding="utf-8")
    diagnostics = adopt.prepare_run(
        tmp_path,
        ".agent-policy.yml",
        apply=False,
        toolchain_revision="LOCAL-DEVELOPMENT",
        profiles=["core"],
        primary_instructions="CLAUDE.md",
    )
    assert diagnostics[0].code == "ALREADY_MANAGED"


def test_cli_parses_adoption_commands() -> None:
    inspect = parser().parse_args(["adopt", "inspect", "--state", "state.json"])
    assert inspect.command == "adopt"
    assert inspect.adopt_command == "inspect"
    assert inspect.state == "state.json"

    prepare = parser().parse_args(
        [
            "adopt",
            "prepare",
            "--primary-instructions",
            "CLAUDE.md",
            "--project-policy",
            ".agents/policies/first.md",
            "--project-policy",
            ".agents/policies/second.md",
            "--verification-command",
            "npm run verify:pr",
            "--preview-output-path",
            ".agent-policy/preview/AGENTS.md",
            "--skill",
            "validate-agent-policy",
            "--apply",
        ]
    )
    assert prepare.adopt_command == "prepare"
    assert prepare.primary_instructions == "CLAUDE.md"
    assert prepare.project_policy_files == [
        ".agents/policies/first.md",
        ".agents/policies/second.md",
    ]
    assert prepare.verification_command == "npm run verify:pr"
    assert prepare.enabled_skills == ["validate-agent-policy"]
    assert prepare.apply is True

    no_skills = parser().parse_args(["adopt", "prepare", "--no-skills"])
    assert no_skills.enabled_skills == []

    with pytest.raises(SystemExit):
        parser().parse_args(
            [
                "adopt",
                "prepare",
                "--skill",
                "validate-agent-policy",
                "--no-skills",
            ]
        )
