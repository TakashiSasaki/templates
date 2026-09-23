from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS_DIR = ROOT / "repository-skills" / "land-templates-stack" / "scripts"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


maintainer_entrypoint = _load_module(
    "maintain_review_stack", SCRIPTS_DIR / "maintain_review_stack.py"
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.PIPE
    ).strip()


@pytest.fixture
def current_trusted_base():
    return _git("rev-parse", "HEAD")


def test_assemble_review_artifacts_input_validates_and_constructs(
    current_trusted_base: str,
) -> None:
    head = current_trusted_base
    base = current_trusted_base

    assembled = maintainer_entrypoint.assemble_review_artifacts_input(
        repository="TakashiSasaki/templates",
        target_pr=100,
        candidate_head=head,
        candidate_base=base,
        trusted_base_sha=current_trusted_base,
        repository_root=ROOT,
        gate_status="passed",
    )

    assert assembled["schema_version"] == 1
    assert assembled["repository"] == "TakashiSasaki/templates"
    assert assembled["candidate"]["pull_request"]["number"] == 100
    assert assembled["candidate"]["head_sha"] == head
    assert assembled["candidate"]["base_sha"] == base
    assert assembled["gate"]["status"] == "passed"
    assert len(assembled["revision_bindings"]) == 5


def test_execute_maintainer_stack_preview_mode_without_writes(
    current_trusted_base: str, tmp_path: Path
) -> None:
    head = current_trusted_base
    base = current_trusted_base
    output_dir = tmp_path / "artifacts"

    assembled = maintainer_entrypoint.assemble_review_artifacts_input(
        repository="TakashiSasaki/templates",
        target_pr=100,
        candidate_head=head,
        candidate_base=base,
        trusted_base_sha=current_trusted_base,
        repository_root=ROOT,
    )

    summary = maintainer_entrypoint.execute_maintainer_stack(
        input_data=assembled,
        trusted_base_sha=current_trusted_base,
        repository_root=ROOT,
        output_dir=output_dir,
        apply=False,
    )

    assert summary["status"] == "preview"
    assert summary["candidate"]["pull_request_number"] == 100
    assert (output_dir / "review-packet.json").is_file()
    assert (output_dir / "review-request.md").is_file()
    assert (output_dir / "pr-generated-region.md").is_file()
    assert (output_dir / "work-ledger-checkpoint.md").is_file()
    assert (output_dir / "manifest.json").is_file()
    assert (output_dir / "publication-result.json").is_file()


def test_execute_maintainer_stack_refuses_unauthorized_apply(
    current_trusted_base: str, tmp_path: Path
) -> None:
    head = current_trusted_base
    base = current_trusted_base
    output_dir = tmp_path / "artifacts"

    assembled = maintainer_entrypoint.assemble_review_artifacts_input(
        repository="TakashiSasaki/templates",
        target_pr=100,
        candidate_head=head,
        candidate_base=base,
        trusted_base_sha=current_trusted_base,
        repository_root=ROOT,
    )

    # Calling with apply=True but without authorize=True and serialized_writer=True must fail closed
    with pytest.raises(
        maintainer_entrypoint.MaintainerWorkflowError,
        match="remote apply requires explicit --authorize and --serialized-writer",
    ):
        maintainer_entrypoint.execute_maintainer_stack(
            input_data=assembled,
            trusted_base_sha=current_trusted_base,
            repository_root=ROOT,
            output_dir=output_dir,
            apply=True,
            authorize=False,
            serialized_writer=False,
        )


def test_maintainer_stack_cli_main_preview(
    current_trusted_base: str, tmp_path: Path
) -> None:
    head = current_trusted_base
    output_dir = tmp_path / "cli_artifacts"

    exit_code = maintainer_entrypoint.main(
        [
            "--pr",
            "100",
            "--head-sha",
            head,
            "--base-sha",
            head,
            "--trusted-base-sha",
            current_trusted_base,
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "publication-result.json").is_file()
    res = json.loads((output_dir / "publication-result.json").read_text(encoding="utf-8"))
    assert res["status"] == "preview"


def _make_source_manifest(revision: str, skill_bytes: bytes) -> dict[str, object]:
    from scripts.verify_maintainer_source_reference import (
        CANONICAL_SKILL_PATH,
        EXPECTED_REPOSITORY,
        required_source_closure_paths,
    )

    skill_blob = _git("hash-object", "-w", "--stdin")
    # Actually hash the provided skill_bytes
    proc = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=ROOT,
        input=skill_bytes,
        capture_output=True,
        check=True,
    )
    skill_blob = proc.stdout.decode("utf-8").strip()

    required_paths = required_source_closure_paths(skill_bytes)
    return {
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


def test_altered_worktree_entrypoint_is_ignored(
    current_trusted_base: str, tmp_path: Path
) -> None:
    from scripts.verify_maintainer_source_reference import CANONICAL_MAINTAINER_ENTRYPOINT_PATH

    entrypoint_file = ROOT / CANONICAL_MAINTAINER_ENTRYPOINT_PATH
    orig_bytes = entrypoint_file.read_bytes()

    # Read current worktree SKILL bytes which reference all 8 closure files
    skill_bytes = (ROOT / "repository-skills" / "land-templates-stack" / "SKILL.md").read_bytes()
    # We construct a verified object dictionary directly
    from scripts.verify_maintainer_source_reference import (
        CANONICAL_RULE_PATH,
        CANONICAL_SKILL_PATH,
        IsolatedClosureEnvironment,
        VerifiedSource,
        required_source_closure_paths,
    )

    required_paths = required_source_closure_paths(skill_bytes)
    closure: dict[str, bytes] = {}
    for p in required_paths:
        closure[p] = (ROOT / p).read_bytes()

    verified = VerifiedSource(
        revision=current_trusted_base,
        skill=skill_bytes,
        rule=closure[CANONICAL_RULE_PATH],
        skill_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_SKILL_PATH)),
        rule_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_RULE_PATH)),
        closure=closure,
    )

    try:
        # Poison worktree entrypoint with fatal error
        entrypoint_file.write_text(
            "raise RuntimeError('WORKTREE ENTRYPOINT POISONED!')\n", encoding="utf-8"
        )

        output_dir = tmp_path / "artifacts"
        # Executing inside IsolatedClosureEnvironment must execute closure bytes,
        # ignoring any poisoned worktree file.
        with IsolatedClosureEnvironment(verified) as env:
            ret = env.run_entrypoint(
                CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
                [
                    "--pr",
                    "100",
                    "--head-sha",
                    current_trusted_base,
                    "--base-sha",
                    current_trusted_base,
                    "--trusted-base-sha",
                    current_trusted_base,
                    "--output-dir",
                    str(output_dir),
                    "--repository-root",
                    str(ROOT),
                ],
            )
            assert ret == 0
            assert (output_dir / "publication-result.json").is_file()
            res = json.loads((output_dir / "publication-result.json").read_text(encoding="utf-8"))
            assert res["status"] == "preview"
    finally:
        entrypoint_file.write_bytes(orig_bytes)


def test_altered_worktree_sibling_is_ignored(
    current_trusted_base: str, tmp_path: Path
) -> None:
    from scripts.verify_maintainer_source_reference import (
        CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
        CANONICAL_RENDERER_PATH,
        CANONICAL_RULE_PATH,
        CANONICAL_SKILL_PATH,
        IsolatedClosureEnvironment,
        VerifiedSource,
        required_source_closure_paths,
    )

    sibling_file = ROOT / CANONICAL_RENDERER_PATH
    orig_bytes = sibling_file.read_bytes()

    skill_bytes = (ROOT / "repository-skills" / "land-templates-stack" / "SKILL.md").read_bytes()
    required_paths = required_source_closure_paths(skill_bytes)
    closure: dict[str, bytes] = {}
    for p in required_paths:
        closure[p] = (ROOT / p).read_bytes()

    verified = VerifiedSource(
        revision=current_trusted_base,
        skill=skill_bytes,
        rule=closure[CANONICAL_RULE_PATH],
        skill_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_SKILL_PATH)),
        rule_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_RULE_PATH)),
        closure=closure,
    )

    try:
        # Poison worktree sibling with fatal error
        sibling_file.write_text(
            "raise RuntimeError('WORKTREE SIBLING POISONED!')\n", encoding="utf-8"
        )

        output_dir = tmp_path / "artifacts"
        with IsolatedClosureEnvironment(verified) as env:
            ret = env.run_entrypoint(
                CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
                [
                    "--pr",
                    "100",
                    "--head-sha",
                    current_trusted_base,
                    "--base-sha",
                    current_trusted_base,
                    "--trusted-base-sha",
                    current_trusted_base,
                    "--output-dir",
                    str(output_dir),
                    "--repository-root",
                    str(ROOT),
                ],
            )
            assert ret == 0
            assert (output_dir / "publication-result.json").is_file()
            res = json.loads((output_dir / "publication-result.json").read_text(encoding="utf-8"))
            assert res["status"] == "preview"
    finally:
        sibling_file.write_bytes(orig_bytes)


def test_preloaded_sys_modules_isolation_and_restoration(
    current_trusted_base: str, tmp_path: Path
) -> None:
    import sys
    from types import ModuleType

    from scripts.verify_maintainer_source_reference import (
        CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
        CANONICAL_RULE_PATH,
        CANONICAL_SKILL_PATH,
        IsolatedClosureEnvironment,
        VerifiedSource,
        required_source_closure_paths,
    )

    skill_bytes = (ROOT / "repository-skills" / "land-templates-stack" / "SKILL.md").read_bytes()
    required_paths = required_source_closure_paths(skill_bytes)
    closure = {p: (ROOT / p).read_bytes() for p in required_paths}

    verified = VerifiedSource(
        revision=current_trusted_base,
        skill=skill_bytes,
        rule=closure[CANONICAL_RULE_PATH],
        skill_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_SKILL_PATH)),
        rule_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_RULE_PATH)),
        closure=closure,
    )

    alien_entrypoint = ModuleType("maintain_review_stack")
    alien_entrypoint.is_alien = True
    alien_sibling = ModuleType("templates_render_review_artifacts")
    alien_sibling.is_alien = True

    sys.modules["maintain_review_stack"] = alien_entrypoint
    sys.modules["templates_render_review_artifacts"] = alien_sibling

    try:
        output_dir = tmp_path / "artifacts"
        with IsolatedClosureEnvironment(verified) as env:
            ret = env.run_entrypoint(
                CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
                [
                    "--pr",
                    "100",
                    "--head-sha",
                    current_trusted_base,
                    "--base-sha",
                    current_trusted_base,
                    "--trusted-base-sha",
                    current_trusted_base,
                    "--output-dir",
                    str(output_dir),
                    "--repository-root",
                    str(ROOT),
                ],
            )
            assert ret == 0

        # Caller sys.modules must have the preloaded alien modules restored
        assert sys.modules.get("maintain_review_stack") is alien_entrypoint
        assert getattr(sys.modules.get("maintain_review_stack"), "is_alien", False) is True
        assert sys.modules.get("templates_render_review_artifacts") is alien_sibling
    finally:
        sys.modules.pop("maintain_review_stack", None)
        sys.modules.pop("templates_render_review_artifacts", None)


def test_cross_revision_isolation_no_module_leak(
    current_trusted_base: str,
) -> None:
    import sys

    from scripts.verify_maintainer_source_reference import (
        CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
        CANONICAL_RULE_PATH,
        CANONICAL_SKILL_PATH,
        IsolatedClosureEnvironment,
        VerifiedSource,
        required_source_closure_paths,
    )

    skill_bytes = (ROOT / "repository-skills" / "land-templates-stack" / "SKILL.md").read_bytes()
    required_paths = required_source_closure_paths(skill_bytes)
    closure = {p: (ROOT / p).read_bytes() for p in required_paths}

    verified1 = VerifiedSource(
        revision=current_trusted_base,
        skill=skill_bytes,
        rule=closure[CANONICAL_RULE_PATH],
        skill_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_SKILL_PATH)),
        rule_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_RULE_PATH)),
        closure=closure,
    )
    verified2 = VerifiedSource(
        revision="a" * 40,
        skill=skill_bytes,
        rule=closure[CANONICAL_RULE_PATH],
        skill_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_SKILL_PATH)),
        rule_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_RULE_PATH)),
        closure=closure,
    )

    with IsolatedClosureEnvironment(verified1) as env1:
        mod1 = env1.load_module(CANONICAL_MAINTAINER_ENTRYPOINT_PATH)
        assert Path(mod1.__file__).resolve().is_relative_to(env1.root.resolve())

    # After env1 exits, closure module is removed
    assert sys.modules.get("maintain_review_stack") is None

    with IsolatedClosureEnvironment(verified2) as env2:
        mod2 = env2.load_module(CANONICAL_MAINTAINER_ENTRYPOINT_PATH)
        assert Path(mod2.__file__).resolve().is_relative_to(env2.root.resolve())
        assert mod1 is not mod2


def test_workflow_lifetime_closure_active(
    current_trusted_base: str,
) -> None:
    from scripts.verify_maintainer_source_reference import (
        CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
        CANONICAL_RULE_PATH,
        CANONICAL_SKILL_PATH,
        IsolatedClosureEnvironment,
        VerifiedSource,
        required_source_closure_paths,
    )

    skill_bytes = (ROOT / "repository-skills" / "land-templates-stack" / "SKILL.md").read_bytes()
    required_paths = required_source_closure_paths(skill_bytes)
    closure = {p: (ROOT / p).read_bytes() for p in required_paths}

    verified = VerifiedSource(
        revision=current_trusted_base,
        skill=skill_bytes,
        rule=closure[CANONICAL_RULE_PATH],
        skill_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_SKILL_PATH)),
        rule_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_RULE_PATH)),
        closure=closure,
    )

    with IsolatedClosureEnvironment(verified) as env:
        entrypoint_mod = env.load_module(CANONICAL_MAINTAINER_ENTRYPOINT_PATH)
        assert hasattr(entrypoint_mod, "main")
        entry_path = Path(entrypoint_mod.__file__).resolve()
        assert entry_path.is_relative_to(env.root.resolve())
        assert not entry_path.is_relative_to(ROOT.resolve() / "repository-skills")

        # Sibling modules loaded via entrypoint must also be inside env.root
        renderer_mod = entrypoint_mod.renderer
        renderer_path = Path(renderer_mod.__file__).resolve()
        assert renderer_path.is_relative_to(env.root.resolve())
        assert not renderer_path.is_relative_to(ROOT.resolve() / "repository-skills")


def test_closure_environment_cleanup_on_success_and_exception(
    current_trusted_base: str,
) -> None:
    import sys

    from scripts.verify_maintainer_source_reference import (
        CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
        CANONICAL_RULE_PATH,
        CANONICAL_SKILL_PATH,
        IsolatedClosureEnvironment,
        VerifiedSource,
        required_source_closure_paths,
    )

    skill_bytes = (ROOT / "repository-skills" / "land-templates-stack" / "SKILL.md").read_bytes()
    required_paths = required_source_closure_paths(skill_bytes)
    closure = {p: (ROOT / p).read_bytes() for p in required_paths}

    verified = VerifiedSource(
        revision=current_trusted_base,
        skill=skill_bytes,
        rule=closure[CANONICAL_RULE_PATH],
        skill_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_SKILL_PATH)),
        rule_blob=_git("hash-object", "-w", str(ROOT / CANONICAL_RULE_PATH)),
        closure=closure,
    )

    orig_sys_path = list(sys.path)

    # Success case
    with IsolatedClosureEnvironment(verified) as env:
        root_path = env.root
        assert root_path.is_dir()
        env.load_module(CANONICAL_MAINTAINER_ENTRYPOINT_PATH)
    assert not root_path.is_dir()
    assert sys.modules.get("maintain_review_stack") is None
    assert sys.path == orig_sys_path

    # Exception case
    try:
        with IsolatedClosureEnvironment(verified) as env:
            root_path = env.root
            assert root_path.is_dir()
            env.load_module(CANONICAL_MAINTAINER_ENTRYPOINT_PATH)
            raise RuntimeError("deliberate test exception")
    except RuntimeError:
        pass
    assert not root_path.is_dir()
    assert sys.modules.get("maintain_review_stack") is None
    assert sys.path == orig_sys_path


def test_invalid_source_binding_fails_closed(
    current_trusted_base: str,
) -> None:
    from scripts.verify_maintainer_source_reference import (
        CANONICAL_PLANNER_PATH,
        SourceReferenceError,
        verify_source_reference,
    )

    skill_path_in_tree = (
        f"{current_trusted_base}:repository-skills/land-templates-stack/SKILL.md"
    )
    committed_skill_bytes = subprocess.check_output(
        ["git", "cat-file", "-p", skill_path_in_tree],
        cwd=ROOT,
    )
    manifest = _make_source_manifest(current_trusted_base, committed_skill_bytes)
    planner_file_path = (
        f"{current_trusted_base}:repository-skills/land-templates-stack/scripts/plan_review_scope.py"
    )
    expected_planner = _git("rev-parse", planner_file_path)

    # Mutable revision
    bad_manifest = dict(manifest)
    bad_manifest["revision"] = "policy"
    with pytest.raises(SourceReferenceError, match="source revision must be a full lowercase SHA"):
        verify_source_reference(
            bad_manifest,
            repo=ROOT,
            expected_planner_blob=expected_planner,
        )

    # Wrong repository
    bad_repo = dict(manifest)
    bad_repo["repository"] = "other-org/templates"
    with pytest.raises(SourceReferenceError, match="unexpected source repository"):
        verify_source_reference(
            bad_repo,
            repo=ROOT,
            expected_planner_blob=expected_planner,
        )

    # Mismatched blob
    bad_blob = dict(manifest)
    bad_blob["blob_sha"] = "0" * 40
    with pytest.raises(SourceReferenceError, match="declared Skill blob does not match"):
        verify_source_reference(
            bad_blob,
            repo=ROOT,
            expected_planner_blob=expected_planner,
        )

    # Incomplete closure
    bad_closure = dict(manifest)
    bad_closure["closure"] = [
        item for item in manifest["closure"] if item["path"] != CANONICAL_PLANNER_PATH
    ]
    with pytest.raises(SourceReferenceError, match="source closure is incomplete"):
        verify_source_reference(
            bad_closure,
            repo=ROOT,
            expected_planner_blob=expected_planner,
        )


def test_bootstrap_runner_cli_refuses_unauthorized_apply(
    current_trusted_base: str, tmp_path: Path
) -> None:
    from scripts.run_maintainer_workflow import run_maintainer_workflow

    output_dir = tmp_path / "cli_artifacts"
    exit_code = run_maintainer_workflow(
        [
            "--trusted-base-sha",
            current_trusted_base,
            "--pr",
            "100",
            "--head-sha",
            current_trusted_base,
            "--base-sha",
            current_trusted_base,
            "--output-dir",
            str(output_dir),
            "--repository-root",
            str(ROOT),
            "--apply",
        ]
    )
    # Must fail closed with error code (either 2 or 1)
    assert exit_code != 0


def make_prospective_manifest(
    repo: Path, candidate_revision: str
) -> dict[str, Any]:
    """Derive a prospective source manifest strictly from immutable Git objects."""
    from scripts.verify_maintainer_source_reference import (
        CANONICAL_SKILL_PATH,
        EXPECTED_REPOSITORY,
        required_source_closure_paths,
    )

    cand_sha = _git("rev-parse", candidate_revision)
    skill_bytes = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{cand_sha}:{CANONICAL_SKILL_PATH}"]
    )
    skill_blob = _git("rev-parse", f"{cand_sha}:{CANONICAL_SKILL_PATH}")
    required_paths = required_source_closure_paths(skill_bytes)
    closure_entries = [
        {
            "path": path,
            "blob_sha": _git("rev-parse", f"{cand_sha}:{path}"),
        }
        for path in required_paths
    ]
    return {
        "schema_version": 2,
        "kind": "repository-maintainer-skill-reference",
        "repository": EXPECTED_REPOSITORY,
        "revision": cand_sha,
        "path": CANONICAL_SKILL_PATH,
        "blob_sha": skill_blob,
        "closure": closure_entries,
    }


def _get_adopted_policy_base() -> str:
    for ref in ("origin/policy", "policy"):
        try:
            return _git("merge-base", ref, "HEAD")
        except Exception:
            pass
    return "b3bc6e96a729ed3524f03a1a491a9d53e67fa71a"


def test_prospective_adoption_preview_e2e_succeeds(
    tmp_path: Path,
) -> None:
    cand_sha = _git("rev-parse", "HEAD")
    adopted_base = _get_adopted_policy_base()
    manifest_data = make_prospective_manifest(ROOT, cand_sha)
    manifest_file = tmp_path / "prospective-manifest.json"
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")
    output_dir = tmp_path / "preview_artifacts"

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_maintainer_workflow.py"),
            "--trusted-base-sha",
            adopted_base,
            "--source-manifest",
            str(manifest_file),
            "--pr",
            "1008",
            "--head-sha",
            cand_sha,
            "--base-sha",
            adopted_base,
            "--output-dir",
            str(output_dir),
            "--repository-root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Preview workflow failed: {proc.stderr}"
    pub_file = output_dir / "publication-result.json"
    assert pub_file.is_file()
    pub = json.loads(pub_file.read_text(encoding="utf-8"))
    assert pub["status"] == "preview"
    packet_file = output_dir / "review-packet.json"
    assert packet_file.is_file()
    packet = json.loads(packet_file.read_text(encoding="utf-8"))
    assert packet["candidate"]["pull_request"]["number"] == 1008

    # Ensure all review artifacts are generated and non-empty
    for artifact_name in (
        "manifest.json",
        "review-packet.json",
        "review-request.md",
        "pr-generated-region.md",
        "work-ledger-checkpoint.md",
    ):
        file_path = output_dir / artifact_name
        assert file_path.is_file(), f"Missing artifact {artifact_name}"
        assert file_path.stat().st_size > 0, f"Empty artifact {artifact_name}"


def test_prospective_adoption_unauthorized_apply_fails_at_mutation_guard(
    tmp_path: Path,
) -> None:
    cand_sha = _git("rev-parse", "HEAD")
    adopted_base = _get_adopted_policy_base()
    manifest_data = make_prospective_manifest(ROOT, cand_sha)
    manifest_file = tmp_path / "prospective-manifest.json"
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")
    output_dir = tmp_path / "unauthorized_apply_artifacts"

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_maintainer_workflow.py"),
            "--trusted-base-sha",
            adopted_base,
            "--source-manifest",
            str(manifest_file),
            "--pr",
            "1008",
            "--head-sha",
            cand_sha,
            "--base-sha",
            adopted_base,
            "--output-dir",
            str(output_dir),
            "--repository-root",
            str(ROOT),
            "--apply",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, f"Expected returncode 2, got {proc.returncode}"
    assert (
        "remote apply requires explicit --authorize and --serialized-writer"
        in proc.stderr
    )


def test_prospective_manifest_tampering_fails_before_execution(
    tmp_path: Path,
) -> None:
    cand_sha = _git("rev-parse", "HEAD")
    adopted_base = _get_adopted_policy_base()
    manifest_data = make_prospective_manifest(ROOT, cand_sha)
    assert len(manifest_data["closure"]) > 0
    # Tamper with first closure entry blob SHA
    tampered_closure = list(manifest_data["closure"])
    tampered_closure[0] = {
        "path": tampered_closure[0]["path"],
        "blob_sha": "0" * 40,
    }
    manifest_data["closure"] = tampered_closure

    manifest_file = tmp_path / "tampered-manifest.json"
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")
    output_dir = tmp_path / "tampered_artifacts"

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_maintainer_workflow.py"),
            "--trusted-base-sha",
            adopted_base,
            "--source-manifest",
            str(manifest_file),
            "--pr",
            "1008",
            "--head-sha",
            cand_sha,
            "--base-sha",
            adopted_base,
            "--output-dir",
            str(output_dir),
            "--repository-root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, f"Expected returncode 2, got {proc.returncode}"
    assert "ERROR BOOTSTRAP: source reference verification failed" in proc.stderr
    assert not (output_dir / "publication-result.json").exists()


def test_current_adopted_manifest_does_not_silently_use_candidate_code(
    tmp_path: Path,
) -> None:
    cand_sha = _git("rev-parse", "HEAD")
    adopted_base = _get_adopted_policy_base()
    output_dir = tmp_path / "adopted_artifacts"

    # Running against current adopted base without explicit prospective manifest
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_maintainer_workflow.py"),
            "--trusted-base-sha",
            adopted_base,
            "--pr",
            "1008",
            "--head-sha",
            cand_sha,
            "--base-sha",
            adopted_base,
            "--output-dir",
            str(output_dir),
            "--repository-root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, f"Expected returncode 2, got {proc.returncode}"
    assert "is not declared in verified closure" in proc.stderr
    assert not (output_dir / "publication-result.json").exists()


def test_poisoned_worktree_through_real_bootstrap(
    tmp_path: Path,
) -> None:
    from scripts.verify_maintainer_source_reference import (
        CANONICAL_MAINTAINER_ENTRYPOINT_PATH,
    )

    entrypoint_file = ROOT / CANONICAL_MAINTAINER_ENTRYPOINT_PATH
    orig_bytes = entrypoint_file.read_bytes()

    cand_sha = _git("rev-parse", "HEAD")
    adopted_base = _get_adopted_policy_base()
    manifest_data = make_prospective_manifest(ROOT, cand_sha)
    manifest_file = tmp_path / "prospective-manifest.json"
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")
    output_dir = tmp_path / "poison_artifacts"

    try:
        # Deliberately poison the worktree entrypoint with a syntax/runtime error
        entrypoint_file.write_text(
            "raise RuntimeError('WORKTREE_ENTRYPOINT_IS_POISONED')\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_maintainer_workflow.py"),
                "--trusted-base-sha",
                adopted_base,
                "--source-manifest",
                str(manifest_file),
                "--pr",
                "1008",
                "--head-sha",
                cand_sha,
                "--base-sha",
                adopted_base,
                "--output-dir",
                str(output_dir),
                "--repository-root",
                str(ROOT),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"Bootstrap failed on poisoned worktree: {proc.stderr}"
        res_file = output_dir / "publication-result.json"
        assert res_file.is_file()
        res = json.loads(res_file.read_text(encoding="utf-8"))
        assert res["status"] == "preview"
    finally:
        entrypoint_file.write_bytes(orig_bytes)



