from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_policy_preflight.py"


def load_preflight():
    spec = importlib.util.spec_from_file_location("run_policy_preflight", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_foreign_snapshot_python_is_not_policy_lint_input() -> None:
    preflight = load_preflight()
    foreign = set(preflight.foreign_snapshot_python_paths(ROOT))
    owned = set(preflight.policy_owned_python_paths(ROOT))

    topology_validator = (
        ROOT / "src" / "agent_policy" / "_topology_contract" / "validator.py"
    ).resolve()
    assert topology_validator in foreign
    assert topology_validator not in owned
    assert (ROOT / "src" / "agent_policy" / "topology.py").resolve() in owned
    assert SCRIPT.resolve() in owned
    assert (ROOT / "repository-skills/land-templates-stack/scripts/plan_review_scope.py") in owned


def test_every_foreign_python_destination_is_classified_by_manifest() -> None:
    preflight = load_preflight()
    expected: set[Path] = set()
    manifests = (ROOT / "src" / "agent_policy").glob("_*_contract/source.json")
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["authority"] == "policy":
            continue
        for entry in manifest["files"]:
            destination = (manifest_path.parent / entry["destination"]).resolve()
            if destination.suffix == ".py":
                expected.add(destination)

    assert set(preflight.foreign_snapshot_python_paths(ROOT)) == expected


def test_fast_and_full_profiles_retain_distinct_validation_depth() -> None:
    preflight = load_preflight()
    assert preflight.PROFILES["fast"] == (
        "compile",
        "lint",
        "focused-tests",
        "self-check",
    )
    assert "tests" in preflight.PROFILES["full"]
    assert "runtime" in preflight.PROFILES["full"]
    assert "docs" in preflight.PROFILES["full"]
    assert "dependency-boundary" in preflight.PROFILES["full"]
    assert "focused-tests" not in preflight.PROFILES["full"]
    assert (ROOT / "scripts/smoke_test_policy_documentation.py").is_file()


def test_preflight_subprocesses_use_the_exact_worktree_package() -> None:
    preflight = load_preflight()
    environment = preflight.sanitized_environment()

    assert environment["PYTHONPATH"].split(os.pathsep) == [
        str(ROOT / "src"),
        str(ROOT),
    ]


def test_fast_profile_requires_local_checkout_behavioral_suite() -> None:
    preflight = load_preflight()
    assert "tests/test_local_checkout_discovery.py" in preflight.FOCUSED_TESTS
    assert "tests/test_local_checkout_contract_provenance.py" in preflight.FOCUSED_TESTS
    assert "tests/test_observe_pr_state.py" in preflight.FOCUSED_TESTS
    assert "tests/test_pr_state_observation.py" in preflight.FOCUSED_TESTS
    assert "tests/test_pr_state_observation_replay.py" in preflight.FOCUSED_TESTS
    assert "tests/test_review_scope_selection.py" in preflight.FOCUSED_TESTS
    assert "tests/test_matched_policy_delivery.py" in preflight.FOCUSED_TESTS
    assert "tests/test_policy_delivery_evidence_spec.py" in preflight.FOCUSED_TESTS
    assert all((ROOT / path).is_file() for path in preflight.FOCUSED_TESTS)


def test_released_compatibility_is_separate_from_current_self_qualification() -> None:
    workflow = (ROOT / ".github/workflows/check-agent-policy.yml").read_text(
        encoding="utf-8"
    )
    assert "current-head-self-qualification:" in workflow
    assert "released-action-compatibility:" in workflow
    assert "scripts/run_policy_preflight.py --check self-check" in workflow
    assert "classification=incompatible-with-released-version" in workflow
    assert workflow.count("continue-on-error: true") == 1


def test_ruff_has_no_foreign_snapshot_specific_suppression() -> None:
    configuration = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "_topology_contract/validator.py" not in configuration
    assert "_local_checkout_contract/validator.py" not in configuration


def test_documentation_smoke_always_unregisters_temporary_worktree() -> None:
    smoke = (ROOT / "scripts/smoke_test_policy_documentation.py").read_text(
        encoding="utf-8"
    )
    assert "if worktree is not None:" in smoke
    assert "worktree is not None and worktree.exists()" not in smoke
    assert '["git", "worktree", "prune"]' in smoke
