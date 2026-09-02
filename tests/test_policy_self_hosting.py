from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".agent-policy.yml"
LOCK_PATH = ROOT / ".agent-policy.lock"
SELF_HOST_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "check-agent-policy.yml"
RELEASE_PATH = ROOT / "release/toolchain.json"
RUNTIME_MANIFEST_PATH = ROOT / "skills/agent-policy/runtime-manifest.json"


def load_yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def assert_immutable_toolchain(toolchain: object) -> None:
    assert isinstance(toolchain, dict)
    assert toolchain["repository"] == "TakashiSasaki/templates"
    revision = toolchain["revision"]
    assert isinstance(revision, str)
    assert len(revision) == 40
    assert all(character in "0123456789abcdef" for character in revision)


def test_self_host_and_stable_pins_follow_separate_authority_boundaries() -> None:
    config = load_yaml(CONFIG_PATH)
    lock = load_yaml(LOCK_PATH)
    release = load_json(RELEASE_PATH)
    runtime_manifest = load_json(RUNTIME_MANIFEST_PATH)

    consumer_toolchain = config["toolchain"]
    assert lock["toolchain"] == consumer_toolchain
    assert_immutable_toolchain(consumer_toolchain)

    stable_toolchain = release["toolchain"]
    assert runtime_manifest["toolchain"] == stable_toolchain
    assert_immutable_toolchain(stable_toolchain)


def test_repository_self_hosting_outputs_match_recorded_lock() -> None:
    lock = load_yaml(LOCK_PATH)
    outputs = lock["outputs"]
    assert isinstance(outputs, dict)
    assert set(outputs) == {
        "AGENTS.md",
        ".review-authority/review-policy.md",
        ".agents/skills/orchestrate-repository-change/SKILL.md",
        ".agents/skills/pr-review/SKILL.md",
        ".agents/skills/pr-review/references/github-pull-request-review-api.md",
        ".agents/skills/pr-review/references/risk-domains/build-provenance-and-ci.md",
        ".agents/skills/pr-review/references/risk-domains/concurrency-and-temporal-consistency.md",
        ".agents/skills/pr-review/references/risk-domains/consumer-and-execution-paths.md",
        ".agents/skills/pr-review/references/risk-domains/external-interaction.md",
        ".agents/skills/pr-review/references/risk-domains/identity-and-authority.md",
        ".agents/skills/pr-review/references/risk-domains/index.md",
        ".agents/skills/pr-review/references/risk-domains/namespace-and-indirection.md",
        ".agents/skills/pr-review/references/risk-domains/persistence-and-integrity.md",
        ".agents/skills/pr-review/references/risk-domains/privileged-execution.md",
        ".agents/skills/pr-review/references/risk-domains/resource-behavior.md",
        ".agents/skills/pr-review/references/risk-domains/state-mutation-and-recovery.md",
    }

    for relative, metadata in outputs.items():
        assert isinstance(relative, str)
        assert isinstance(metadata, dict)
        expected = metadata["sha256"]
        assert isinstance(expected, str)
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative

    assert not (ROOT / ".github" / "REVIEW_GUIDELINES.md").exists()


def test_repository_self_hosting_workflow_checks_with_consumer_pin() -> None:
    config = load_yaml(CONFIG_PATH)
    toolchain = config["toolchain"]
    assert isinstance(toolchain, dict)
    revision = toolchain["revision"]
    assert isinstance(revision, str)

    workflow = SELF_HOST_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert f"uses: TakashiSasaki/templates@{revision}" in workflow
    assert "uses: TakashiSasaki/templates@policy" not in workflow
    assert "uses: TakashiSasaki/templates@main" not in workflow
    assert "command: check" in workflow
    assert "config: .agent-policy.yml" in workflow


def test_coding_and_review_share_repository_local_authority() -> None:
    config = load_yaml(CONFIG_PATH)
    contexts = config["contexts"]
    coding = contexts["coding"]
    review = contexts["review"]

    assert coding["profiles"] == ["core", "security-baseline", "pull-request"]
    assert review["profiles"] == ["core", "security-baseline", "review"]

    coding_files = coding["project_policy"]["files"]
    review_files = review["project_policy"]["files"]
    assert coding_files == review_files
    assert coding_files
    assert all(path.startswith("repository-policy/") for path in coding_files)
    assert all((ROOT / path).is_file() for path in coding_files)


def test_repository_policy_is_not_part_of_shared_profiles() -> None:
    for profile_path in sorted((ROOT / "profiles").glob("*.yml")):
        profile = load_yaml(profile_path)
        policy_files = profile.get("policy_files", [])
        assert isinstance(policy_files, list)
        assert all(
            not str(path).startswith("repository-policy/")
            for path in policy_files
        ), profile_path.name


def test_generated_outputs_use_provider_neutral_review_authority() -> None:
    config = load_yaml(CONFIG_PATH)
    outputs = config["outputs"]

    assert set(outputs) == {"agents", "review-authority"}
    assert outputs["agents"] == {
        "enabled": True,
        "path": "AGENTS.md",
        "context": "coding",
        "renderer": "agents-md",
    }
    assert outputs["review-authority"] == {
        "enabled": True,
        "path": ".review-authority/review-policy.md",
        "context": "review",
        "renderer": "policy-context-md",
    }
    assert config["skills"] == {
        "enabled": ["pr-review", "orchestrate-repository-change"]
    }
