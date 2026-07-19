from agent_policy.config import package_root


def test_validation_skill_uses_pinned_toolchain_fallback() -> None:
    skill = (
        package_root() / "skills" / "validate-agent-policy" / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "toolchain.repository" in skill
    assert "toolchain.revision" in skill
    assert "git+https://github.com/<repository>.git@<revision>" in skill
    assert "Do not substitute `main`" in skill
    assert "command: check" in skill


def test_consumer_workflow_checks_every_pull_request() -> None:
    workflow = (
        package_root() / "templates" / "workflows" / "check-agent-policy.yml.j2"
    ).read_text(encoding="utf-8")

    assert "pull_request: {}" in workflow
    assert "workflow_dispatch: {}" in workflow
    assert "paths:" not in workflow
    assert "TakashiSasaki/agent-policy@{{ revision }}" in workflow
    assert "command: check" in workflow
