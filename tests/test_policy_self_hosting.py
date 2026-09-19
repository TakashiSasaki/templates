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
        ".agents/skills/orchestrate-repository-change/references/generated-artifact-transport.md",
        ".agents/skills/orchestrate-repository-change/references/github-review-finding-representation.md",
        ".agents/skills/orchestrate-repository-change/references/github-review-result-discovery.md",
        ".agents/skills/orchestrate-repository-change/references/human-handoff.md",
        ".agents/skills/orchestrate-repository-change/references/pr-workflow-selection.md",
        ".agents/skills/orchestrate-repository-change/references/repository-topology-discovery.md",
        ".agents/skills/orchestrate-repository-change/references/repository-tracked-work-ledger.md",
        ".agents/skills/orchestrate-repository-change/references/review-feedback-disposition.md",
        ".agents/skills/orchestrate-repository-change/references/review-finding-ledger.md",
        ".agents/skills/orchestrate-repository-change/references/serial-pr-workflow.md",
        ".agents/skills/orchestrate-repository-change/references/stacked-pr-workflow.md",
        ".agents/skills/orchestrate-repository-change/references/staged-ci-execution.md",
        ".agents/skills/orchestrate-repository-change/references/work-ledger.md",
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
        ".agents/skills/maintain-progressive-discovery/SKILL.md",
        ".agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py",
    }

    for relative, metadata in outputs.items():
        assert isinstance(relative, str)
        assert isinstance(metadata, dict)
        expected = metadata["sha256"]
        assert isinstance(expected, str)
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative

    assert not (ROOT / ".github" / "REVIEW_GUIDELINES.md").exists()


def test_core_context_delivers_local_checkout_discovery_rule() -> None:
    profile = load_yaml(ROOT / "profiles/core.yml")
    rule_path = "policy/core/local-checkout-topology-discovery.md"
    assert rule_path in profile["policy_files"]
    assert profile["policy_files"].index(rule_path) == (
        profile["policy_files"].index("policy/core/repository-topology-discovery.md") + 1
    )

    for output_path in (ROOT / "AGENTS.md", ROOT / ".review-authority/review-policy.md"):
        output = output_path.read_text(encoding="utf-8")
        assert "Discover local-checkout topology separately from repository topology" in output
        assert "core.discover-local-checkout-topology-fail-closed" in output


def test_repository_self_hosting_workflow_checks_with_released_pin() -> None:
    config = load_yaml(CONFIG_PATH)
    toolchain = config["toolchain"]
    assert isinstance(toolchain, dict)
    revision = toolchain["revision"]
    assert isinstance(revision, str)

    release = load_json(RELEASE_PATH)
    stable_toolchain = release["toolchain"]
    assert isinstance(stable_toolchain, dict)
    stable_revision = stable_toolchain["revision"]
    assert isinstance(stable_revision, str)

    workflow = SELF_HOST_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert f"uses: TakashiSasaki/templates@{stable_revision}" in workflow
    assert revision != stable_revision
    assert "uses: TakashiSasaki/templates@policy" not in workflow
    assert "uses: TakashiSasaki/templates@main" not in workflow
    assert "command: check" in workflow
    assert "config: .agent-policy.yml" in workflow


def test_coding_and_review_share_repository_local_authority() -> None:
    config = load_yaml(CONFIG_PATH)
    contexts = config["contexts"]
    coding = contexts["coding"]
    review = contexts["review"]

    assert coding["profiles"] == [
        "core",
        "security-baseline",
        "pull-request",
        "progressive-discovery",
    ]
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
        "enabled": [
            "pr-review",
            "orchestrate-repository-change",
            "maintain-progressive-discovery",
        ]
    }


def test_self_host_projection_contains_workflow_source_and_pin() -> None:
    config = load_yaml(CONFIG_PATH)
    revision = config["toolchain"]["revision"]
    assert isinstance(revision, str)
    release = load_json(RELEASE_PATH)
    stable_revision = release["toolchain"]["revision"]
    assert isinstance(stable_revision, str)
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow = SELF_HOST_WORKFLOW_PATH.read_text(encoding="utf-8")
    skill = (
        ROOT / ".agents/skills/orchestrate-repository-change/SKILL.md"
    ).read_text(encoding="utf-8")
    assert revision in agents
    assert stable_revision in workflow
    assert "strategy-neutral workflow dispatcher" in skill.lower()
    assert "references/stacked-pr-workflow.md" in skill


def test_self_host_projection_uses_the_canonical_progressive_discovery_skill() -> None:
    config = load_yaml(CONFIG_PATH)
    revision = config["toolchain"]["revision"]
    skill = (
        ROOT / ".agents/skills/maintain-progressive-discovery/SKILL.md"
    ).read_text(encoding="utf-8")
    script = (
        ROOT
        / ".agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py"
    )

    assert revision == "a53966ab02142795654fbda41d2c470c70db3422"
    assert script.is_file()
    assert "authoritative inventory" in skill
    assert "--apply" in skill


def test_every_distributable_skill_is_expected_and_reachable() -> None:
    import json
    adapter = json.loads((ROOT / '.progressive-discovery.json').read_text())
    skills = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'skills').glob('*/SKILL.md')}
    assert skills.issubset(adapter['expected_documents'])
    navigation = (ROOT / 'skills/index.md').read_text()
    for source in skills:
        assert f'({source.removeprefix("skills/")})' in navigation


def test_authoritative_inventories_are_declared_navigation_targets() -> None:
    import json
    adapter = json.loads((ROOT / '.progressive-discovery.json').read_text())
    assert set(adapter['authoritative_inventories']).issubset(adapter['expected_documents'])
    source_index = (ROOT / 'index.md').read_text()
    assert '(.agent-policy.yml)' in source_index
    assert '(docs/publication-catalog.json)' in source_index
    assert '(repository-policy/index.md)' in source_index


def test_self_host_manifest_routes_repository_policy_inputs() -> None:
    import json
    adapter = json.loads((ROOT / '.progressive-discovery.json').read_text())
    assert '.agent-policy.yml' in adapter['authoritative_inventories']
    assert '.agent-policy.yml' in adapter['expected_documents']
    policy_index = (ROOT / 'repository-policy/index.md').read_text()
    configured = set(load_yaml(CONFIG_PATH)['contexts']['coding']['project_policy']['files'])
    linked = {
        'repository-policy/' + line.split('(', 1)[1].split(')', 1)[0]
        for line in policy_index.splitlines()
        if '](' in line
    }
    assert configured <= linked


def _require_clean_repository_discovery(root: Path) -> None:
    import subprocess
    import sys
    script = (root / '.agents/skills/maintain-progressive-discovery/scripts'
              / 'maintain_progressive_discovery.py')
    result = subprocess.run(
        [sys.executable, str(script), '--root', str(root), '--format', 'json'],
        text=True, capture_output=True, check=False,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 0 and report['result'] == 'NO_UPDATE_REQUIRED', (
        report['result'], report['validation']['errors']
    )


def test_repository_progressive_discovery_is_clean() -> None:
    _require_clean_repository_discovery(ROOT)


def test_repository_discovery_gate_rejects_a_removed_navigation_entry(tmp_path: Path) -> None:
    import shutil
    import subprocess

    import pytest
    paths = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().split('\0')
    for relative in filter(None, paths):
        source = ROOT / relative
        if source.is_file():
            destination = tmp_path / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    _require_clean_repository_discovery(tmp_path)
    index = tmp_path / 'policy/core/index.md'
    text = index.read_text()
    assert '[Testing](testing.md)' in text
    index.write_text('\n'.join(
        line for line in text.splitlines() if '[Testing](testing.md)' not in line
    ) + '\n')
    with pytest.raises(AssertionError, match='UPDATE_REQUIRED'):
        _require_clean_repository_discovery(tmp_path)


def test_mkdocs_destinations_are_covered_by_repository_discovery() -> None:
    import subprocess
    import sys

    manifest = load_yaml(ROOT / 'mkdocs.yml')

    def destinations(value):
        if isinstance(value, str):
            if '://' not in value and not value.startswith('#'):
                yield value.split('#', 1)[0]
        elif isinstance(value, dict):
            for child in value.values():
                yield from destinations(child)
        elif isinstance(value, list):
            for child in value:
                yield from destinations(child)

    docs_root = manifest.get('docs_dir', 'docs')
    expected = {f'{docs_root}/{path}' for path in destinations(manifest['nav'])}
    script = (ROOT / '.agents/skills/maintain-progressive-discovery/scripts'
              / 'maintain_progressive_discovery.py')
    result = subprocess.run([sys.executable, str(script), '--root', str(ROOT), '--format', 'json'],
                            text=True, capture_output=True, check=True)
    report = json.loads(result.stdout)
    assert expected <= set(report['expected_documents'])
    assert expected <= set(report['validation']['reachable'])
