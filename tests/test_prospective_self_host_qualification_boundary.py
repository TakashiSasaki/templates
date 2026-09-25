from __future__ import annotations

import inspect
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest
import yaml

import scripts.verify_candidate_qualification as candidate_mod
from scripts.verify_candidate_qualification import (
    ROOT,
    _verify_source_and_resources_bound,
    qualify_candidate,
    resolve_checkout_revision,
)
from scripts.verify_candidate_qualification import (
    main as candidate_main,
)
from scripts.verify_policy_self_host import verify_self_host


def test_candidate_qualification_passes_on_current_head() -> None:
    """Candidate qualification proves current head is a valid reusable toolchain."""
    rev = qualify_candidate()
    assert rev == resolve_checkout_revision(ROOT)


def test_candidate_verifier_rejects_arbitrary_source_root_interface() -> None:
    """Test 1: wrong external source cannot masquerade via arbitrary source-root interface."""
    # 1. qualify_candidate takes no arbitrary source-root positional argument
    sig = inspect.signature(qualify_candidate)
    assert len(sig.parameters) == 0, (
        "qualify_candidate must not accept arbitrary source-root parameters"
    )

    # 2. CLI reject --source-root option
    with pytest.raises(SystemExit):
        candidate_main(["--source-root", "/tmp"])


def test_candidate_qualification_provenance_contains_exact_checkout_sha() -> None:
    """Test 2: candidate rendered output provenance contains exact evaluated checkout SHA."""
    rev = qualify_candidate()
    expected_rev = resolve_checkout_revision(ROOT)
    assert rev == expected_rev
    assert len(rev) == 40

    # If checkout revision cannot be resolved from git, fail closed
    with pytest.raises((RuntimeError, ValueError)):
        resolve_checkout_revision(Path("/tmp"))


def test_candidate_qualification_binds_source_and_resources_strictly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 3: package/resource identity; synthetic differences or external packages fail closed."""
    import agent_policy
    import agent_policy.config

    # Normal state passes
    _verify_source_and_resources_bound(ROOT)

    # If package_root() resolves to an external or mismatched directory, fail closed
    other_root = tmp_path / "other_pkg_root"
    other_root.mkdir()
    monkeypatch.setattr(agent_policy.config, "package_root", lambda: other_root)
    with pytest.raises(RuntimeError, match="package_root\\(\\) resolved to"):
        _verify_source_and_resources_bound(ROOT)

    # If agent_policy.__file__ resolves outside ROOT/src, fail closed
    fake_module_file = str(tmp_path / "external_pkg" / "agent_policy" / "__init__.py")
    monkeypatch.setattr(agent_policy, "__file__", fake_module_file)
    with pytest.raises(RuntimeError, match="agent_policy imported from"):
        _verify_source_and_resources_bound(ROOT)

    # Sibling directory starting with same string prefix (e.g. ROOT/src-evil/...) must fail closed
    sibling_evil_file = str(ROOT / "src-evil" / "agent_policy" / "__init__.py")
    monkeypatch.setattr(agent_policy, "__file__", sibling_evil_file)
    with pytest.raises(RuntimeError, match="agent_policy imported from"):
        _verify_source_and_resources_bound(ROOT)


def test_adopted_self_host_consistency_passes_on_current_head() -> None:
    """Adopted self-host consistency proves committed outputs match pinned runtime."""
    verify_self_host(ROOT)


def test_prospective_profile_change_separated_from_adopted_self_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 4: Prospective profile change is qualified in candidate toolchain

    while adopted self-host consistency continues to evaluate the old pinned toolchain.
    """
    synthetic_root = tmp_path / "synthetic_package_root"
    for d in ("src", "schemas", "templates", "profiles", "policy", "skills"):
        shutil.copytree(ROOT / d, synthetic_root / d)

    synthetic_rule_path = synthetic_root / "policy" / "core" / "synthetic-prospective-rule.md"
    synthetic_rule_path.write_text(
        """---
id: core.synthetic-prospective-rule
severity: mandatory
overridable: false
order: 49
---
# Synthetic Prospective Rule

Must not leak into adopted self-host maintainer instructions.
""",
        encoding="utf-8",
    )

    core_profile_path = synthetic_root / "profiles" / "core.yml"
    profile_data = yaml.safe_load(core_profile_path.read_text(encoding="utf-8"))
    profile_data["policy_files"].append("policy/core/synthetic-prospective-rule.md")
    core_profile_path.write_text(yaml.safe_dump(profile_data), encoding="utf-8")

    subprocess.run(["git", "init"], cwd=synthetic_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=synthetic_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=synthetic_root,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=synthetic_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init prospective candidate"],
        cwd=synthetic_root,
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(candidate_mod, "ROOT", synthetic_root)

    # 1. Candidate qualification sees the prospective change and qualifies cleanly
    candidate_rev = qualify_candidate()
    assert candidate_rev == resolve_checkout_revision(synthetic_root)

    # 2. Adopted self-host consistency continues evaluating the adopted runtime (5ad8b0d...)
    verify_self_host(ROOT)

    # 3. Committed self-host outputs remain untouched and do not contain the prospective rule
    agents_content = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "core.synthetic-prospective-rule" not in agents_content
    review_content = (ROOT / ".review-authority" / "review-policy.md").read_text(encoding="utf-8")
    assert "core.synthetic-prospective-rule" not in review_content

    # 4. No false source provenance is emitted under the pinned toolchain
    assert "TakashiSasaki/templates@5ad8b0d89a7778beb98aa5794ef6aa58dca30ab5" in agents_content


def test_adopted_self_host_fails_when_outputs_are_stale(tmp_path: Path) -> None:
    """Tampered or stale maintainer outputs in an adopted repository fail closed."""
    repo = tmp_path / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"))
    (repo / ".git").mkdir()

    # Modify committed AGENTS.md to simulate stale output
    agents_file = repo / "AGENTS.md"
    agents_file.write_text(agents_file.read_text(encoding="utf-8") + "\n# Stale line\n")

    with pytest.raises(RuntimeError, match="Self-host check failed against adopted toolchain"):
        verify_self_host(repo)


def test_adopted_self_host_fails_closed_when_lock_and_config_disagree(tmp_path: Path) -> None:
    """Mismatched toolchain revisions between config and lock fail closed."""
    repo = tmp_path / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"))
    (repo / ".git").mkdir()

    config_path = repo / ".agent-policy.yml"
    config_text = config_path.read_text(encoding="utf-8")
    tampered_config = config_text.replace(
        "5ad8b0d89a7778beb98aa5794ef6aa58dca30ab5",
        "1111111111111111111111111111111111111111",
    )
    config_path.write_text(tampered_config, encoding="utf-8")

    with pytest.raises(ValueError, match="does not match lock toolchain"):
        verify_self_host(repo)


def test_adopted_self_host_fails_closed_when_pin_is_malformed(tmp_path: Path) -> None:
    """Malformed toolchain revisions fail closed."""
    repo = tmp_path / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"))
    (repo / ".git").mkdir()

    lock_path = repo / ".agent-policy.lock"
    lock_text = lock_path.read_text(encoding="utf-8")
    tampered_lock = lock_text.replace(
        "5ad8b0d89a7778beb98aa5794ef6aa58dca30ab5",
        "not-a-valid-sha",
    )
    lock_path.write_text(tampered_lock, encoding="utf-8")

    with pytest.raises(ValueError, match="must be a full lowercase commit SHA"):
        verify_self_host(repo)


def test_adopted_self_host_fails_closed_when_runtime_identity_unestablished(tmp_path: Path) -> None:
    """Unresolvable runtime revision fails closed."""
    repo = tmp_path / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"))
    (repo / ".git").mkdir()

    nonexistent_sha = "0" * 40
    config_path = repo / ".agent-policy.yml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "5ad8b0d89a7778beb98aa5794ef6aa58dca30ab5", nonexistent_sha
        ),
        encoding="utf-8",
    )
    lock_path = repo / ".agent-policy.lock"
    lock_path.write_text(
        lock_path.read_text(encoding="utf-8").replace(
            "5ad8b0d89a7778beb98aa5794ef6aa58dca30ab5", nonexistent_sha
        ),
        encoding="utf-8",
    )

    with pytest.raises((RuntimeError, OSError, ValueError)):
        verify_self_host(repo)


def test_toolchain_payload_supports_json_and_yaml(tmp_path: Path) -> None:
    """_parse_toolchain_payload transparently supports both YAML and JSON format."""
    from scripts.verify_policy_self_host import runtime
    config_toolchain = runtime.config_toolchain
    lock_toolchain = runtime.lock_toolchain

    rev = "5ad8b0d89a7778beb98aa5794ef6aa58dca30ab5"
    repo = "TakashiSasaki/templates"

    # YAML format
    yaml_file = tmp_path / ".agent-policy.yml"
    yaml_file.write_text(
        f"schema_version: 2\ntoolchain:\n  repository: {repo}\n  revision: {rev}\n",
        encoding="utf-8",
    )
    assert config_toolchain(yaml_file) == (repo, rev)

    # JSON format
    json_file = tmp_path / ".agent-policy.json"
    json_file.write_text(
        f'{{"schema_version": 2, "toolchain": {{"repository": "{repo}", "revision": "{rev}"}}}}',
        encoding="utf-8",
    )
    assert config_toolchain(json_file) == (repo, rev)
    assert lock_toolchain(json_file) == (repo, rev)


def test_runtime_selection_trust_boundary_distinction(tmp_path: Path) -> None:
    """Exact runtime selection trust boundaries:

    1. No lock, no config -> stable manifest default.
    2. No lock, config present -> does NOT silently make config the managed executable authority;
       still returns stable manifest default.
    3. Lock present -> lock authority.
    4. Lock + config present and agree -> lock authority.
    5. Lock + config present but disagree -> fails closed.
    """
    from scripts.verify_policy_self_host import runtime

    manifest = runtime.load_manifest()
    default_pin = runtime.pin_from_manifest(manifest)
    repo = "TakashiSasaki/templates"
    pinned_rev = "5ad8b0d89a7778beb98aa5794ef6aa58dca30ab5"
    custom_rev = "1111111111111111111111111111111111111111"

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # 1. No lock, no config -> stable manifest default
    pin1 = runtime.select_pin(repo_dir, manifest)
    assert pin1.revision == default_pin.revision

    # 2. No lock, config present -> does NOT make config the managed executable authority
    config_file = repo_dir / ".agent-policy.yml"
    config_file.write_text(
        f"schema_version: 2\ntoolchain:\n  repository: {repo}\n  revision: {custom_rev}\n",
        encoding="utf-8",
    )
    pin2 = runtime.select_pin(repo_dir, manifest)
    assert pin2.revision == default_pin.revision
    assert pin2.revision != custom_rev

    # 3. Both lock and config present, but disagree -> fail closed
    lock_file = repo_dir / ".agent-policy.lock"
    lock_file.write_text(
        f"lock_version: 1\ntoolchain:\n  repository: {repo}\n  revision: {pinned_rev}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="does not match .agent-policy.lock"):
        runtime.select_pin(repo_dir, manifest)

    # 4. Lock present without config -> lock authority
    config_file.unlink()
    pin4 = runtime.select_pin(repo_dir, manifest)
    assert pin4.revision == pinned_rev

    # 5. Lock + config present and agree -> lock authority
    config_file.write_text(
        f"schema_version: 2\ntoolchain:\n  repository: {repo}\n  revision: {pinned_rev}\n",
        encoding="utf-8",
    )
    pin5 = runtime.select_pin(repo_dir, manifest)
    assert pin5.revision == pinned_rev


def _create_isolated_candidate_repo(tmp_path: Path, prefix: str = "repo") -> Path:
    repo = tmp_path / prefix
    for d in ("src", "schemas", "templates", "profiles", "policy", "skills"):
        shutil.copytree(ROOT / d, repo / d)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init candidate"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def test_candidate_qualification_ignores_dirty_tracked_resource(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial regression 1: modified tracked resource without committing.

    The candidate verifier must ignore the dirty bytes by evaluating the exact commit snapshot.
    It must never evaluate dirty bytes while reporting HEAD provenance.
    """
    repo = _create_isolated_candidate_repo(tmp_path, "dirty_tracked_repo")
    head_rev = resolve_checkout_revision(repo)

    # Break core.yml in the working tree with invalid YAML syntax
    broken_profile = repo / "profiles" / "core.yml"
    broken_profile.write_text("invalid: yaml: syntax: [broken", encoding="utf-8")

    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
    assert "M profiles/core.yml" in status

    monkeypatch.setattr(candidate_mod, "ROOT", repo)
    # Qualify candidate must succeed by evaluating exact commit snapshot,
    # ignoring dirty working tree
    rev = qualify_candidate()
    assert rev == head_rev


def test_candidate_qualification_ignores_staged_modification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial regression 2: staged modification.

    A modified and staged tracked file must not contaminate candidate qualification.
    """
    repo = _create_isolated_candidate_repo(tmp_path, "staged_repo")
    head_rev = resolve_checkout_revision(repo)

    # Modify and stage a broken profile
    broken_profile = repo / "profiles" / "core.yml"
    broken_profile.write_text("invalid: yaml: syntax: [broken", encoding="utf-8")
    subprocess.run(["git", "add", "profiles/core.yml"], cwd=repo, check=True)

    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
    assert "M  profiles/core.yml" in status

    monkeypatch.setattr(candidate_mod, "ROOT", repo)
    rev = qualify_candidate()
    assert rev == head_rev


def test_candidate_qualification_ignores_untracked_import_influence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial regression 3: untracked import influence.

    Untracked files/modules capable of influencing imports cannot alter exact-commit qualification.
    """
    repo = _create_isolated_candidate_repo(tmp_path, "untracked_import_repo")
    head_rev = resolve_checkout_revision(repo)

    # Create an untracked poisonous module inside src/agent_policy
    poison = repo / "src" / "agent_policy" / "untracked_poison_module.py"
    poison.write_text("raise RuntimeError('Poison module executed!')\n", encoding="utf-8")

    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
    assert "??" in status

    monkeypatch.setattr(candidate_mod, "ROOT", repo)
    rev = qualify_candidate()
    assert rev == head_rev


def test_candidate_qualification_ignores_untracked_resource_influence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial regression 4: untracked resource influence.

    Untracked policy/profile/template/resource files cannot alter exact-commit qualification.
    """
    repo = _create_isolated_candidate_repo(tmp_path, "untracked_resource_repo")
    head_rev = resolve_checkout_revision(repo)

    # Create an untracked profile file that would be invalid if discovered
    untracked_profile = repo / "profiles" / "untracked_poison_profile.yml"
    untracked_profile.write_text("invalid: yaml: [syntax", encoding="utf-8")

    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
    assert "??" in status

    monkeypatch.setattr(candidate_mod, "ROOT", repo)
    rev = qualify_candidate()
    assert rev == head_rev


def test_candidate_qualification_rejects_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adversarial regression 5: symlink escape.

    Exercise an implementation/resource path through a symlink that resolves outside
    the exact candidate source boundary. Must fail closed.
    """
    repo = _create_isolated_candidate_repo(tmp_path, "symlink_escape_repo")

    # Commit a symlink pointing outside the repository tree
    outside_target = tmp_path / "outside_secret.txt"
    outside_target.write_text("secret outside data", encoding="utf-8")

    symlink_file = repo / "policy" / "core" / "escaped_symlink.md"
    symlink_file.symlink_to(outside_target)

    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "commit symlink escape"], cwd=repo, check=True)

    monkeypatch.setattr(candidate_mod, "ROOT", repo)
    # Extraction with filter='data' or path-containment verification must fail closed
    with pytest.raises((RuntimeError, tarfile.FilterError, tarfile.TarError)):
        qualify_candidate()


def test_clean_exact_candidate_qualifies_matching_head() -> None:
    """Adversarial regression 6: clean exact candidate.

    A clean exact committed checkout must qualify successfully and emit provenance
    matching its exact HEAD.
    """
    rev = qualify_candidate()
    expected_rev = resolve_checkout_revision(ROOT)
    assert rev == expected_rev


def test_candidate_qualification_rejects_revision_and_effective_bytes_mismatch(
    tmp_path: Path,
) -> None:
    """Adversarial regression 7: wrong revision / effective bytes mismatch.

    The verifier cannot report revision A while evaluating effective source bytes
    from revision/state B.
    """
    repo = _create_isolated_candidate_repo(tmp_path, "mismatch_repo")
    commit_a = resolve_checkout_revision(repo)

    # Create a second commit B
    (repo / "policy" / "core" / "new_rule.md").write_text("# New rule\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "commit B"], cwd=repo, check=True)
    commit_b = resolve_checkout_revision(repo)
    assert commit_a != commit_b

    from scripts.verify_candidate_qualification import (
        _run_snapshot_qualification,
        materialize_snapshot,
    )

    # 1. Materialize snapshot of B, but attempt to qualify it claiming revision A
    with materialize_snapshot(repo, commit_b) as snapshot_b:
        with pytest.raises(RuntimeError, match="Snapshot revision mismatch"):
            _run_snapshot_qualification(snapshot_b, commit_a)

    # 2. Tampered snapshot marker file fails closed
    with materialize_snapshot(repo, commit_a) as snapshot_a:
        marker = snapshot_a / ".candidate_revision"
        marker.write_text(commit_b, encoding="utf-8")
        with pytest.raises(RuntimeError, match="Snapshot revision mismatch"):
            _run_snapshot_qualification(snapshot_a, commit_a)

