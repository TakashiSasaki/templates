from __future__ import annotations

import json
from pathlib import Path

import yaml

from agent_policy.commands import check

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".agent-policy.yml"
RELEASE_PATH = ROOT / "release/toolchain.json"
RUNTIME_MANIFEST_PATH = ROOT / "skills/agent-policy/runtime-manifest.json"


def load_yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_self_host_uses_current_stable_full_sha() -> None:
    config = load_yaml(CONFIG_PATH)
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    runtime_manifest = json.loads(RUNTIME_MANIFEST_PATH.read_text(encoding="utf-8"))

    revision = config["toolchain"]["revision"]
    assert revision == release["toolchain"]["revision"]
    assert revision == runtime_manifest["toolchain"]["revision"]
    assert isinstance(revision, str)
    assert len(revision) == 40
    assert all(character in "0123456789abcdef" for character in revision)


def test_repository_self_hosting_check_passes() -> None:
    assert check.run(ROOT, ".agent-policy.yml") == []


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


def test_generated_outputs_have_distinct_coding_and_review_adapters() -> None:
    config = load_yaml(CONFIG_PATH)
    outputs = config["outputs"]

    assert outputs["agents"] == {
        "enabled": True,
        "path": "AGENTS.md",
        "context": "coding",
        "renderer": "agents-md",
    }
    assert outputs["review"] == {
        "enabled": True,
        "path": ".github/REVIEW_GUIDELINES.md",
        "context": "review",
        "renderer": "github-review-json-v1",
    }
