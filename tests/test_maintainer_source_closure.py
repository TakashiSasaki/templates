from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from scripts.verify_maintainer_source_reference import (
    CANONICAL_LIVE_ADAPTER_PATH,
    CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
    CANONICAL_OBSERVER_LIBRARY_PATH,
    CANONICAL_OBSERVER_PATH,
    CANONICAL_PLANNER_PATH,
    CANONICAL_PUBLISHER_PATH,
    CANONICAL_RENDERER_PATH,
    CANONICAL_RULE_PATH,
    CANONICAL_SKILL_PATH,
    CANONICAL_SOURCE_MANIFEST_PATH,
    EXPECTED_REPOSITORY,
    IsolatedClosureEnvironment,
    SourceReferenceError,
    load_closure_module,
    load_source_reference_from_trusted_base,
    required_source_closure_paths,
    run_verified_closure_entrypoint,
    verify_source_reference,
    verify_trusted_source_reference,
)

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.PIPE
    ).strip()


@pytest.fixture
def current_head_verified_source():
    revision = _git("rev-parse", "HEAD")
    skill_blob = _git("rev-parse", f"{revision}:{CANONICAL_SKILL_PATH}")
    rule_blob = _git("rev-parse", f"{revision}:{CANONICAL_RULE_PATH}")
    planner_blob = _git("rev-parse", f"{revision}:{CANONICAL_PLANNER_PATH}")

    # Skill at commit revision
    skill_bytes = subprocess.check_output(
        ["git", "show", f"{revision}:{CANONICAL_SKILL_PATH}"], cwd=ROOT
    )
    required_paths = required_source_closure_paths(skill_bytes)

    source = {
        "schema_version": 2,
        "kind": "repository-maintainer-skill-reference",
        "repository": EXPECTED_REPOSITORY,
        "revision": revision,
        "path": CANONICAL_SKILL_PATH,
        "blob_sha": skill_blob,
        "closure": [
            {
                "path": path,
                "blob_sha": _git("rev-parse", f"{revision}:{path}"),
            }
            for path in required_paths
        ],
    }

    verified = verify_source_reference(
        source,
        repo=ROOT,
        expected_skill_blob=skill_blob,
        expected_rule_blob=rule_blob,
        expected_planner_blob=planner_blob,
    )
    return verified, source, skill_blob, rule_blob, planner_blob


def test_clean_consumer_loads_real_modules_from_verified_closure(
    current_head_verified_source,
) -> None:
    verified, _, _, _, _ = current_head_verified_source
    with IsolatedClosureEnvironment(verified) as env:
        observer_mod = env.load_module(CANONICAL_OBSERVER_PATH)
        assert hasattr(observer_mod, "capture_once")
        assert hasattr(observer_mod, "CandidateBinding")
        # Ensure sibling library was loaded from verified closure
        assert observer_mod.DEFAULT_SURFACES == (
            "metadata",
            "checks",
            "reviews",
            "comments",
            "threads",
            "reactions",
        )

        planner_mod = env.load_module(CANONICAL_PLANNER_PATH)
        assert hasattr(planner_mod, "plan")


def test_clean_consumer_helper_function_load_closure_module(
    current_head_verified_source,
) -> None:
    verified, _, _, _, _ = current_head_verified_source
    module = load_closure_module(verified, CANONICAL_PLANNER_PATH)
    assert callable(getattr(module, "plan", None))


def test_clean_consumer_refuses_shadowed_local_module(
    current_head_verified_source, tmp_path: Path
) -> None:
    verified, _, _, _, _ = current_head_verified_source

    # Create a malicious shadowed file in a temporary directory
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir()
    shadow_file = shadow_dir / "pr_state_observation.py"
    shadow_file.write_text(
        "raise RuntimeError('MALICIOUS_SHADOW_CODE_EXECUTED')", encoding="utf-8"
    )

    # Insert shadow_dir at the front of sys.path
    orig_sys_path = list(sys.path)
    orig_cwd = os.getcwd()
    sys.path.insert(0, str(shadow_dir))
    os.chdir(str(shadow_dir))

    try:
        with IsolatedClosureEnvironment(verified) as env:
            # Must load cleanly from verified closure without executing the shadowed file
            mod = env.load_module(CANONICAL_OBSERVER_PATH)
            assert hasattr(mod, "capture_once")
    finally:
        os.chdir(orig_cwd)
        sys.path = orig_sys_path


def test_clean_consumer_refuses_missing_closure_dependency(
    current_head_verified_source,
) -> None:
    _, source, skill_blob, rule_blob, planner_blob = current_head_verified_source

    # Omit observer library from closure while skill references observer
    incomplete_source = dict(source)
    incomplete_source["closure"] = [
        entry
        for entry in source["closure"]
        if entry["path"] != CANONICAL_OBSERVER_LIBRARY_PATH
    ]

    with pytest.raises(SourceReferenceError, match="source closure is incomplete"):
        verify_source_reference(
            incomplete_source,
            repo=ROOT,
            expected_skill_blob=skill_blob,
            expected_rule_blob=rule_blob,
            expected_planner_blob=planner_blob,
        )


def test_clean_consumer_refuses_altered_closure_blob(
    current_head_verified_source,
) -> None:
    _, source, skill_blob, rule_blob, planner_blob = current_head_verified_source

    tampered_source = dict(source)
    tampered_source["closure"] = [
        {
            **entry,
            "blob_sha": "0" * 40 if entry["path"] == CANONICAL_PLANNER_PATH else entry["blob_sha"],
        }
        for entry in source["closure"]
    ]

    match_regex = "declared closure blob does not match|planner blob does not match"
    with pytest.raises(SourceReferenceError, match=match_regex):
        verify_source_reference(
            tampered_source,
            repo=ROOT,
            expected_skill_blob=skill_blob,
            expected_rule_blob=rule_blob,
            expected_planner_blob=planner_blob,
        )


def test_clean_consumer_refuses_mutable_reference(
    current_head_verified_source,
) -> None:
    _, source, skill_blob, rule_blob, planner_blob = current_head_verified_source

    mutable_source = dict(source)
    mutable_source["revision"] = "policy"

    with pytest.raises(
        SourceReferenceError, match="source revision must be a full lowercase SHA"
    ):
        verify_source_reference(
            mutable_source,
            repo=ROOT,
            expected_skill_blob=skill_blob,
            expected_rule_blob=rule_blob,
            expected_planner_blob=planner_blob,
        )


def test_clean_consumer_refuses_unexpected_repository(
    current_head_verified_source,
) -> None:
    _, source, skill_blob, rule_blob, planner_blob = current_head_verified_source

    foreign_source = dict(source)
    foreign_source["repository"] = "attacker/templates"

    with pytest.raises(SourceReferenceError, match="unexpected source repository"):
        verify_source_reference(
            foreign_source,
            repo=ROOT,
            expected_skill_blob=skill_blob,
            expected_rule_blob=rule_blob,
            expected_planner_blob=planner_blob,
        )


def test_clean_consumer_refuses_tampered_materialized_bytes(
    current_head_verified_source,
) -> None:
    verified, _, _, _, _ = current_head_verified_source

    with IsolatedClosureEnvironment(verified) as env:
        # Tamper with the materialized file on disk before loading
        target_file = env.root / CANONICAL_PLANNER_PATH
        target_file.write_text("# tampered\n", encoding="utf-8")

        with pytest.raises(SourceReferenceError, match="closure bytes altered"):
            env.load_module(CANONICAL_PLANNER_PATH)


def test_clean_consumer_closure_paths_include_all_workflow_modules() -> None:
    # Test that skill referencing renderer, publisher, adapter, and entrypoint requires them
    skill_with_all = (
        b"Use render_review_artifacts.py and publish_review_artifacts.py and "
        b"live_review_adapter.py and maintain_review_stack.py."
    )
    required = required_source_closure_paths(skill_with_all)
    assert CANONICAL_RULE_PATH in required
    assert CANONICAL_PLANNER_PATH in required
    assert CANONICAL_RENDERER_PATH in required
    assert CANONICAL_PUBLISHER_PATH in required
    assert CANONICAL_LIVE_ADAPTER_PATH in required
    assert CANONICAL_MAINTAINER_ENTRYPOINT_PATH in required


def test_clean_consumer_closure_paths_include_references() -> None:
    # Test that skill referencing progressive disclosure references requires them
    skill_with_refs = b"See references/source-trust.md and references/landing-and-resume.md."
    required = required_source_closure_paths(skill_with_refs)
    assert CANONICAL_RULE_PATH in required
    assert CANONICAL_PLANNER_PATH in required
    assert (
        "repository-skills/land-templates-stack/references/source-trust.md"
        in required
    )
    assert (
        "repository-skills/land-templates-stack/references/landing-and-resume.md"
        in required
    )
    assert (
        "repository-skills/land-templates-stack/references/maintainer-entrypoint.md"
        not in required
    )


def test_closure_environment_isolates_preloaded_sibling_in_sys_modules(
    current_head_verified_source,
) -> None:
    verified, _, _, _, _ = current_head_verified_source

    alien_module = ModuleType("pr_state_observation")
    alien_module.ATTACKER_CONTROLLED = True
    alien_module.__file__ = "/tmp/fake/pr_state_observation.py"

    orig_pr_state_obs = sys.modules.get("pr_state_observation")
    orig_observe_pr_state = sys.modules.get("observe_pr_state")

    sys.modules["pr_state_observation"] = alien_module

    try:
        with IsolatedClosureEnvironment(verified) as env:
            obs_mod = env.load_module(CANONICAL_OBSERVER_PATH)
            assert hasattr(obs_mod, "DEFAULT_SURFACES")
            sibling_in_env = sys.modules.get("pr_state_observation")
            assert sibling_in_env is not None
            assert sibling_in_env is not alien_module
            assert not hasattr(sibling_in_env, "ATTACKER_CONTROLLED")
            assert Path(sibling_in_env.__file__).resolve().is_relative_to(
                env.root.resolve()
            )

        assert sys.modules.get("pr_state_observation") is alien_module
        assert sys.modules.get("observe_pr_state") is orig_observe_pr_state
    finally:
        if orig_pr_state_obs is not None:
            sys.modules["pr_state_observation"] = orig_pr_state_obs
        else:
            sys.modules.pop("pr_state_observation", None)
        if orig_observe_pr_state is not None:
            sys.modules["observe_pr_state"] = orig_observe_pr_state
        else:
            sys.modules.pop("observe_pr_state", None)


def test_closure_environment_prevents_cross_revision_module_reuse(
    current_head_verified_source,
) -> None:
    verified_a, _, _, _, _ = current_head_verified_source

    rev_b = "1" * 40
    tampered_bytes = (
        verified_a.closure[CANONICAL_OBSERVER_LIBRARY_PATH]
        + b"\nCUSTOM_MARKER = 'REVISION_B_PAYLOAD'\n"
    )
    closure_b = dict(verified_a.closure)
    closure_b[CANONICAL_OBSERVER_LIBRARY_PATH] = tampered_bytes
    verified_b = type(verified_a)(
        revision=rev_b,
        skill=verified_a.skill,
        rule=verified_a.rule,
        skill_blob=verified_a.skill_blob,
        rule_blob=verified_a.rule_blob,
        closure=closure_b,
    )

    with IsolatedClosureEnvironment(verified_a) as env_a:
        env_a.load_module(CANONICAL_OBSERVER_PATH)
        lib_a = sys.modules["pr_state_observation"]
        assert not hasattr(lib_a, "CUSTOM_MARKER")

    with IsolatedClosureEnvironment(verified_b) as env_b:
        env_b.load_module(CANONICAL_OBSERVER_PATH)
        lib_b = sys.modules["pr_state_observation"]
        assert hasattr(lib_b, "CUSTOM_MARKER")
        assert lib_b.CUSTOM_MARKER == "REVISION_B_PAYLOAD"
        assert lib_b is not lib_a

    env_a_unclosed = IsolatedClosureEnvironment(verified_a)
    try:
        env_a_unclosed.load_module(CANONICAL_OBSERVER_PATH)
        lib_a_unclosed = sys.modules["pr_state_observation"]
        assert Path(lib_a_unclosed.__file__).resolve().is_relative_to(
            env_a_unclosed.root.resolve()
        )

        with IsolatedClosureEnvironment(verified_b) as env_b2:
            env_b2.load_module(CANONICAL_OBSERVER_PATH)
            lib_b2 = sys.modules["pr_state_observation"]
            assert lib_b2.CUSTOM_MARKER == "REVISION_B_PAYLOAD"
            assert Path(lib_b2.__file__).resolve().is_relative_to(
                env_b2.root.resolve()
            )
            assert not Path(lib_b2.__file__).resolve().is_relative_to(
                env_a_unclosed.root.resolve()
            )
    finally:
        env_a_unclosed.close()


def test_closure_environment_cleans_up_and_restores_sys_modules(
    current_head_verified_source,
) -> None:
    verified, _, _, _, _ = current_head_verified_source

    orig_pr_state_obs = sys.modules.get("pr_state_observation")
    orig_observe_pr_state = sys.modules.get("observe_pr_state")

    sentinel_mod = ModuleType("pr_state_observation")
    sentinel_mod.SENTINEL = "original_caller_value"
    sys.modules["pr_state_observation"] = sentinel_mod

    try:
        # 1. Normal exit
        with IsolatedClosureEnvironment(verified) as env:
            env.load_module(CANONICAL_OBSERVER_PATH)
            assert sys.modules["pr_state_observation"] is not sentinel_mod
            assert Path(
                sys.modules["pr_state_observation"].__file__
            ).resolve().is_relative_to(env.root.resolve())

        assert sys.modules.get("pr_state_observation") is sentinel_mod
        assert sys.modules.get("observe_pr_state") is orig_observe_pr_state

        # 2. Exception exit
        with pytest.raises(RuntimeError, match="deliberate_error"):
            with IsolatedClosureEnvironment(verified) as env:
                env.load_module(CANONICAL_OBSERVER_PATH)
                raise RuntimeError("deliberate_error")

        assert sys.modules.get("pr_state_observation") is sentinel_mod
        assert sys.modules.get("observe_pr_state") is orig_observe_pr_state
    finally:
        if orig_pr_state_obs is not None:
            sys.modules["pr_state_observation"] = orig_pr_state_obs
        else:
            sys.modules.pop("pr_state_observation", None)
        if orig_observe_pr_state is not None:
            sys.modules["observe_pr_state"] = orig_observe_pr_state
        else:
            sys.modules.pop("observe_pr_state", None)


def test_closure_environment_refuses_module_provenance_violation(
    current_head_verified_source, tmp_path: Path
) -> None:
    verified, _, _, _, _ = current_head_verified_source

    with IsolatedClosureEnvironment(verified) as env:
        alien_mod = ModuleType("plan_review_scope")
        alien_mod.__file__ = str(tmp_path / "plan_review_scope.py")
        sys.modules["plan_review_scope"] = alien_mod

        with pytest.raises(
            SourceReferenceError,
            match="loaded from outside isolated root|closure module 'plan_review_scope'",
        ):
            env._verify_provenance()

        sys.modules.pop("plan_review_scope", None)


def test_isolated_closure_environment_run_entrypoint_executes_within_active_isolation(
    current_head_verified_source,
) -> None:
    verified_base, _, _, _, _ = current_head_verified_source

    entrypoint_code = b"""
import sys
from pathlib import Path

def main(argv=None):
    # Verify we are running inside the isolated environment root
    cur_mod = sys.modules.get("maintain_review_stack")
    assert cur_mod is not None
    assert "maintainer_closure_" in getattr(cur_mod, "__file__", "")
    return 42
"""
    closure = dict(verified_base.closure)
    closure[CANONICAL_MAINTAINER_ENTRYPOINT_PATH] = entrypoint_code
    verified = type(verified_base)(
        revision=verified_base.revision,
        skill=verified_base.skill,
        rule=verified_base.rule,
        skill_blob=verified_base.skill_blob,
        rule_blob=verified_base.rule_blob,
        closure=closure,
    )

    exit_code = run_verified_closure_entrypoint(
        verified,
        ["--arg1", "val1"],
        entrypoint_path=CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
    )
    assert exit_code == 42
    # Ensure entrypoint module is cleaned up after execution
    assert sys.modules.get("maintain_review_stack") is None


def test_isolated_closure_environment_run_entrypoint_restores_on_exception(
    current_head_verified_source,
) -> None:
    verified_base, _, _, _, _ = current_head_verified_source

    entrypoint_code = b"""
def main(argv=None):
    raise ValueError("deliberate_entrypoint_failure")
"""
    closure = dict(verified_base.closure)
    closure[CANONICAL_MAINTAINER_ENTRYPOINT_PATH] = entrypoint_code
    verified = type(verified_base)(
        revision=verified_base.revision,
        skill=verified_base.skill,
        rule=verified_base.rule,
        skill_blob=verified_base.skill_blob,
        rule_blob=verified_base.rule_blob,
        closure=closure,
    )

    with pytest.raises(ValueError, match="deliberate_entrypoint_failure"):
        run_verified_closure_entrypoint(
            verified,
            entrypoint_path=CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
        )

    # Ensure cleanup happened despite the exception
    assert sys.modules.get("maintain_review_stack") is None


def test_load_source_reference_from_trusted_base_and_verify(
    current_head_verified_source,
) -> None:
    verified, source, _, _, _ = current_head_verified_source
    revision = verified.revision

    # Load source reference from current HEAD commit
    loaded_manifest = load_source_reference_from_trusted_base(
        ROOT, revision, manifest_path=CANONICAL_SOURCE_MANIFEST_PATH
    )
    assert loaded_manifest["schema_version"] == 2
    assert loaded_manifest["repository"] == EXPECTED_REPOSITORY

    # verify_trusted_source_reference automatically resolves planner blob from manifest
    verified_loaded = verify_trusted_source_reference(loaded_manifest, repo=ROOT)
    assert verified_loaded.revision == loaded_manifest["revision"]
    assert CANONICAL_PLANNER_PATH in verified_loaded.closure

    # Test error cases: invalid SHA format
    with pytest.raises(
        SourceReferenceError, match="trusted base SHA must be a full lowercase SHA"
    ):
        load_source_reference_from_trusted_base(ROOT, "invalid-sha")
