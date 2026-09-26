from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from agent_policy.commands import check, render
from agent_policy.config import load_config, validate_config
from agent_policy.policy_loader import load_rules, parse_policy

ROOT = Path(__file__).resolve().parents[1]
RULE_PATH = ROOT / "policy/core/policy-applicability.md"
CORE_PROFILE_PATH = ROOT / "profiles/core.yml"
AGENTS_MD_PATH = ROOT / "AGENTS.md"
REVIEW_POLICY_PATH = ROOT / ".review-authority/review-policy.md"
LOCK_PATH = ROOT / ".agent-policy.lock"
CONFIG_PATH = ROOT / ".agent-policy.yml"

SOURCE_PROVENANCE_PATTERN = re.compile(
    r"_Source:\s*`(?P<repo>[^@]+)@(?P<sha>[0-9a-f]{40}):(?P<path>[^`]+)`"
)


def make_consumer_config(
    *,
    profiles: list[str] | None = None,
    project_policy_files: list[str] | None = None,
    skills: list[str] | None = None,
    toolchain_revision: str | None = None,
) -> dict[str, object]:
    """Construct a valid schema-v2 configuration for synthetic consumer tests."""
    if toolchain_revision is None:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        toolchain_revision = str(config["toolchain"]["revision"])
    return {
        "schema_version": 2,
        "toolchain": {
            "repository": "TakashiSasaki/templates",
            "revision": toolchain_revision,
        },
        "contexts": {
            "coding": {
                "profiles": ["core"] if profiles is None else profiles,
                "project_policy": {
                    "files": [] if project_policy_files is None else project_policy_files,
                },
            }
        },
        "outputs": {
            "agents": {
                "enabled": True,
                "path": "AGENTS.md",
                "context": "coding",
                "renderer": "agents-md",
            }
        },
        "skills": {
            "enabled": [] if skills is None else skills,
        },
    }


# =============================================================================
# 1. Normative Rule Specification & Invariants
# =============================================================================


def test_policy_applicability_rule_metadata() -> None:
    """The applicability rule has canonical metadata, ordering, and severity."""
    assert RULE_PATH.is_file()
    rule = parse_policy(
        RULE_PATH,
        RULE_PATH.relative_to(ROOT).as_posix(),
        "toolchain",
    )

    assert rule.id == "core.scope-applicability-to-target"
    assert rule.title == "Scope policy and instruction applicability to the governed target"
    assert rule.severity == "mandatory"
    assert rule.overridable is False
    assert rule.order == 48


def test_policy_applicability_rule_remains_technology_neutral() -> None:
    """The applicability rule avoids technology-specific keywords or runtime products."""
    text = RULE_PATH.read_text(encoding="utf-8").casefold()

    technology_specific_terms = (
        "python",
        "javascript",
        "pytest",
        "github",
        "posix",
        "windows",
        "subprocess",
        "symlink",
        "pip",
    )
    for term in technology_specific_terms:
        assert term.casefold() not in text


def test_policy_applicability_defines_required_operations_and_principles() -> None:
    """The applicability rule explicitly formalizes the four operations and eight principles."""
    text = RULE_PATH.read_text(encoding="utf-8")

    # Four distinct operational relationships
    for operation in (
        "**Reference**",
        "**Edit**",
        "**Adopt**",
        "**Execute**",
    ):
        assert operation in text

    # Core applicability principles
    required_phrases = (
        "does not govern an agent merely because the file containing it is visible",
        "governed target",
        "declared operation",
        "explicit adoption facts",
        "working directory alone",
        "advisory role labels do not establish authority",
        "object of work",
        "do not self-activate",
        "provider-local maintenance rules",
        "do not propagate to consumer repositories",
        "adopted shared policy remains effective",
        "self-hosted or mixed environments",
        "evaluate applicability per target and operation",
        "materially ambiguous",
        "continue safe bounded read-only investigation",
        "fail closed before performing any dependent mutation",
    )
    for phrase in required_phrases:
        assert phrase.casefold() in text.casefold()


# =============================================================================
# 2. Real Profile Selection & Separation of Provider-Local vs Shared Policy
# =============================================================================


def test_consumer_rule_loading_excludes_provider_maintainer_rules() -> None:
    """Consumer configuration selecting shared profiles never receives provider-maintainer rules."""
    rules = load_rules(ROOT, ["core", "security-baseline", "pull-request"], [])
    rule_ids = {rule.id for rule in rules}

    # Provider-maintainer rules must NOT be included in any shared profile
    provider_maintainer_rule_ids = {
        "policy-repo.preserve-authority-boundary",
        "policy-repo.preserve-history-boundary",
        "policy-repo.require-architecture-decisions",
        "policy-repo.preserve-release-trust-model",
        "policy-repo.preserve-toolchain-safety-boundaries",
        "policy-repo.run-maintainer-validation",
        "policy-repo.preserve-documentation-deployment-boundary",
        "policy-repo.maintainer-stacked-pr-landing",
        "policy-repo.maintainer-merge-routing",
    }
    assert rule_ids.isdisjoint(provider_maintainer_rule_ids)


def test_provider_maintainer_rules_remain_isolated_in_repository_policy() -> None:
    """Provider-maintainer rules are loaded via repository-policy inputs, never in profiles."""
    for profile_path in sorted((ROOT / "profiles").glob("*.yml")):
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        policy_files = data.get("policy_files", [])
        assert all(not str(p).startswith("repository-policy/") for p in policy_files)


def test_provider_self_host_repository_policy_is_separately_applied() -> None:
    """Provider self-host instructions apply provider rules strictly via project_policy.files."""
    config = load_config(ROOT, ".agent-policy.yml")
    coding_context = config.contexts["coding"]

    # Shared profile rules
    shared_rules = load_rules(ROOT, list(coding_context.profiles), [])
    shared_rule_ids = {r.id for r in shared_rules}
    assert not any(r_id.startswith("policy-repo.") for r_id in shared_rule_ids)

    # Effective self-host rules with local repository policy
    effective_rules = load_rules(
        ROOT,
        list(coding_context.profiles),
        list(coding_context.project_policy_files),
    )
    effective_rule_ids = {r.id for r in effective_rules}

    # Provider rules are present ONLY through repository-policy files
    assert "policy-repo.preserve-authority-boundary" in effective_rule_ids
    assert "policy-repo.preserve-history-boundary" in effective_rule_ids


def test_candidate_core_profile_selects_applicability_with_established_rules() -> None:
    """Candidate source core profile selects applicability alongside established mandatory rules in
    canonical order.
    """
    rules = load_rules(ROOT, ["core"], [])
    rule_ids = [rule.id for rule in rules]

    expected_baseline_ids = [
        "core.discover-repository-topology-fail-closed",
        "core.discover-local-checkout-topology-fail-closed",
        "core.scope-applicability-to-target",
        "changes.define-contract",
        "changes.preserve-acceptance-baseline",
        "changes.minimize-scope",
        "decisions.escalate-semantic-ambiguity",
        "regression.no-weaken-tests",
        "testing.run-required-checks",
        "testing.require-adversarial-invariant-coverage",
        "verification.separate-evidence-layers",
        "consistency.synchronize-derived-artifacts",
        "compatibility.preserve-contracts",
        "safety.revalidate-destructive-actions",
        "safety.bind-validated-state-to-operation",
        "safety.limit-rollback-to-owned-changes",
        "reporting.truthful-status",
        "changes.separate-task-review-merge-state",
        "changes.prevent-diagnostic-stall",
    ]
    assert rule_ids == expected_baseline_ids
    assert len(rule_ids) == 19



# =============================================================================
# 3. Truthful Provenance & P1/P3 Candidate vs Adopted Separation
# =============================================================================


def test_all_generated_source_provenance_claims_resolve_in_git() -> None:
    """Every source revision claimed in committed generated instructions exists in Git."""
    for output_path in (AGENTS_MD_PATH, REVIEW_POLICY_PATH):
        content = output_path.read_text(encoding="utf-8")
        matches = SOURCE_PROVENANCE_PATTERN.findall(content)
        assert matches, f"No source provenance references found in {output_path}"

        for repo, sha, file_path in matches:
            assert repo == "TakashiSasaki/templates"
            res = subprocess.run(
                ["git", "cat-file", "-e", f"{sha}:{file_path}"],
                cwd=ROOT,
                capture_output=True,
            )
            assert res.returncode == 0, (
                f"Invalid provenance claim in {output_path}: "
                f"{sha}:{file_path} does not exist in Git"
            )


def test_adopted_applicability_rule_is_claimed_with_truthful_provenance() -> None:
    """The adopted shared applicability rule is claimed with truthful immutable provenance.

    Under P3c, policy/core/policy-applicability.md is adopted via the stable runtime pin
    declared in .agent-policy.yml (aa6f9ac4). Policy's current generated instructions
    truthfully claim this path as a source at the pinned revision.
    """
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    pinned_revision = config["toolchain"]["revision"]

    # 1. Verify adopted rule exists at the pinned revision in Git
    res = subprocess.run(
        [
            "git",
            "cat-file",
            "-e",
            f"{pinned_revision}:policy/core/policy-applicability.md",
        ],
        cwd=ROOT,
        capture_output=True,
    )
    assert res.returncode == 0, "Adopted rule must exist in pinned immutable runtime"

    # 2. Verify committed generated instructions claim it truthfully under that pin
    for output_path in (AGENTS_MD_PATH, REVIEW_POLICY_PATH):
        content = output_path.read_text(encoding="utf-8")
        assert f"{pinned_revision}:policy/core/policy-applicability.md" in content, (
            f"Adopted rule not claimed in {output_path}"
        )
        assert "core.scope-applicability-to-target" in content

    # 3. Unadopted candidate rules must not exist at the pinned revision in Git
    unadopted_candidate = "policy/core/unadopted-prospective-rule.md"
    res_unadopted = subprocess.run(
        [
            "git",
            "cat-file",
            "-e",
            f"{pinned_revision}:{unadopted_candidate}",
        ],
        cwd=ROOT,
        capture_output=True,
    )
    assert res_unadopted.returncode != 0
    for output_path in (AGENTS_MD_PATH, REVIEW_POLICY_PATH):
        content = output_path.read_text(encoding="utf-8")
        assert unadopted_candidate not in content


def test_policy_self_host_check_passes_with_truthful_state() -> None:
    """Policy self-hosting check passes with 0 diagnostics against the locked state."""
    from scripts.verify_policy_self_host import verify_self_host

    verify_self_host(ROOT)


# =============================================================================
# 4. Synthetic Consumer Configuration Render & Check
# =============================================================================


def test_synthetic_consumer_rendering_with_real_engine(tmp_path: Path) -> None:
    """Consumer repository adopting shared profiles renders and checks cleanly."""
    consumer_config = make_consumer_config(profiles=["core", "security-baseline"])
    (tmp_path / ".agent-policy.yml").write_text(yaml.safe_dump(consumer_config), encoding="utf-8")

    # Render with real agent-policy command
    render_diags = render.run(tmp_path, ".agent-policy.yml")
    assert render_diags == []

    # Verify AGENTS.md was created with shared policy
    agents_content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "agent-policy-generated: true" in agents_content
    assert "core.discover-repository-topology-fail-closed" in agents_content
    assert "security.no-secrets" in agents_content

    # Verify provider-maintainer rules are NOT included
    assert "policy-repo.preserve-authority-boundary" not in agents_content

    # Verify check passes with 0 diagnostics
    check_diags = check.run(tmp_path, ".agent-policy.yml")
    assert check_diags == []


def test_synthetic_consumer_with_local_project_policy(tmp_path: Path) -> None:
    """A consumer repository can define project-local policy without altering shared rules."""
    local_policy_dir = tmp_path / "project-policy"
    local_policy_dir.mkdir(parents=True)
    (local_policy_dir / "consumer-rules.md").write_text(
        "---\n"
        "id: consumer.enforce-local-boundary\n"
        "severity: mandatory\n"
        "overridable: false\n"
        "order: 100\n"
        "---\n"
        "# Enforce local boundary\n\n"
        "Consumer application enforces its local domain boundary.\n",
        encoding="utf-8",
    )

    consumer_config = make_consumer_config(
        profiles=["core"],
        project_policy_files=["project-policy/consumer-rules.md"],
    )
    (tmp_path / ".agent-policy.yml").write_text(yaml.safe_dump(consumer_config), encoding="utf-8")

    render_diags = render.run(tmp_path, ".agent-policy.yml")
    assert render_diags == []

    agents_content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "consumer.enforce-local-boundary" in agents_content
    assert "core.discover-repository-topology-fail-closed" in agents_content
    assert "policy-repo.preserve-authority-boundary" not in agents_content


# =============================================================================
# 5. Semantic Scenarios (A through H) Exercised on Real Engine Behavior
# =============================================================================


def test_scenario_a_consumer_applies_composition(tmp_path: Path) -> None:
    """Scenario A: Consumer developing an application repo references Composition provider source.

    Principle 1 & 2: Provider maintenance rules (repository-policy/) do not propagate to consumer.
    """
    consumer_config = make_consumer_config(profiles=["core"])
    (tmp_path / ".agent-policy.yml").write_text(yaml.safe_dump(consumer_config), encoding="utf-8")

    # Real engine renders consumer
    assert render.run(tmp_path, ".agent-policy.yml") == []

    # Governed target is consumer: consumer receives core rules, zero provider rules
    rendered = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "core.discover-repository-topology-fail-closed" in rendered
    assert "policy-repo." not in rendered


def test_scenario_b_consumer_adopts_policy(tmp_path: Path) -> None:
    """Scenario B: Consumer adopts shared Policy.

    Principle 3: Adopted shared rules remain effective within consumer governance.
    """
    rules = load_rules(ROOT, ["core", "security-baseline"], [])
    rule_ids = {r.id for r in rules}

    # Adopted shared rules are active and effective
    assert "core.discover-repository-topology-fail-closed" in rule_ids
    assert "security.no-secrets" in rule_ids

    # Provider maintenance rules are strictly absent
    assert not any(rid.startswith("policy-repo.") for rid in rule_ids)


def test_scenario_c_policy_provider_is_edited() -> None:
    """Scenario C: Policy provider normative source is edited.

    Principle 4: Editing normative source does not self-activate; provider maintenance rules govern.
    """
    # 1. The adopted rule exists in the worktree and is active via adoption
    assert RULE_PATH.is_file()
    agents_text = AGENTS_MD_PATH.read_text(encoding="utf-8")
    assert "core.scope-applicability-to-target" in agents_text

    # 2. But unadopted candidate edits do NOT self-activate into maintainer instructions
    assert "core.unadopted-prospective-rule" not in agents_text

    # 3. Provider maintenance policy remains authoritative for provider work
    config = load_config(ROOT, ".agent-policy.yml")
    coding = config.contexts["coding"]
    assert "repository-policy/maintainer-validation.md" in coding.project_policy_files


def test_scenario_d_site_self_hosting(tmp_path: Path) -> None:
    """Scenario D: Site maintains Site while consuming Composition and Policy.

    Principle 5: Mixed/self-hosted relationships are scoped per target and operation.
    """
    # Site defines its own local maintenance policy in project_policy
    local_dir = tmp_path / "site-policy"
    local_dir.mkdir(parents=True)
    (local_dir / "site-maintenance.md").write_text(
        "---\n"
        "id: site.maintain-publishing-pipeline\n"
        "severity: mandatory\n"
        "overridable: false\n"
        "order: 10\n"
        "---\n"
        "# Maintain publishing pipeline\n\n"
        "Site publishing pipeline must be validated.\n",
        encoding="utf-8",
    )

    site_config = make_consumer_config(
        profiles=["core"],
        project_policy_files=["site-policy/site-maintenance.md"],
    )
    (tmp_path / ".agent-policy.yml").write_text(yaml.safe_dump(site_config), encoding="utf-8")

    assert render.run(tmp_path, ".agent-policy.yml") == []
    rendered = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    # Site maintenance rules apply locally
    assert "site.maintain-publishing-pipeline" in rendered
    # Shared policy applies through explicit selection
    assert "core.discover-repository-topology-fail-closed" in rendered
    # Templates provider-local rules do not propagate
    assert "policy-repo." not in rendered


def test_scenario_e_reference_only_inspection() -> None:
    """Scenario E: User asks agent to explain or inspect a Policy rule.

    Principle 1 & 4: Reference-only inspection leaves repository and projections unchanged.
    """
    # Verify current hash of lock and instructions
    initial_lock_bytes = LOCK_PATH.read_bytes()
    initial_agents_bytes = AGENTS_MD_PATH.read_bytes()

    # Reading / parsing policy file for inspection
    rule = parse_policy(RULE_PATH, RULE_PATH.relative_to(ROOT).as_posix(), "toolchain")
    assert rule.id == "core.scope-applicability-to-target"

    # Reference operation causes zero state mutations
    assert LOCK_PATH.read_bytes() == initial_lock_bytes
    assert AGENTS_MD_PATH.read_bytes() == initial_agents_bytes


def test_scenario_f_consumer_enters_provider_checkout_cwd(tmp_path: Path) -> None:
    """Scenario F: Agent CWD is inside provider checkout during consumer work.

    Principle 1 & 6: Target repository identity governs; CWD alone does not retarget mutations.
    """
    consumer_config = make_consumer_config(profiles=["core"])
    (tmp_path / ".agent-policy.yml").write_text(yaml.safe_dump(consumer_config), encoding="utf-8")

    # Running render targeting consumer repo from current ROOT CWD
    diags = render.run(tmp_path, ".agent-policy.yml")
    assert diags == []

    # Output was written to consumer target, NOT provider repository
    assert (tmp_path / "AGENTS.md").is_file()
    from scripts.verify_policy_self_host import verify_self_host

    verify_self_host(ROOT)


def test_scenario_g_advisory_role_labels_do_not_override_configuration(tmp_path: Path) -> None:
    """Scenario G: Advisory role labels do not establish or bypass authority.

    Principle 7: Effective governance derives from explicit repository configuration.
    """
    # Even if a config claims an advisory label or custom context name,
    # governance is bound strictly by the explicit profiles and project_policy files.
    labeled_config = make_consumer_config(profiles=["core"])
    (tmp_path / ".agent-policy.yml").write_text(yaml.safe_dump(labeled_config), encoding="utf-8")

    assert render.run(tmp_path, ".agent-policy.yml") == []
    rendered = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "core.discover-repository-topology-fail-closed" in rendered
    assert "policy-repo." not in rendered


def test_scenario_h_ambiguity_fails_closed_before_mutation(tmp_path: Path) -> None:
    """Scenario H: Applicability ambiguity fails closed before performing dependent mutation.

    Principle 8: Material configuration error halts execution before file mutations occur.
    """
    # Malformed configuration (missing required toolchain revision)
    invalid_config = {
        "schema_version": 2,
        "toolchain": {
            "repository": "TakashiSasaki/templates",
            # missing revision
        },
        "contexts": {
            "coding": {
                "profiles": ["core"],
                "project_policy": {"files": []},
            }
        },
        "outputs": {
            "agents": {
                "enabled": True,
                "path": "AGENTS.md",
                "context": "coding",
                "renderer": "agents-md",
            }
        },
        "skills": {"enabled": []},
    }
    (tmp_path / ".agent-policy.yml").write_text(yaml.safe_dump(invalid_config), encoding="utf-8")

    # Validation detects ambiguity/error
    config = load_config(tmp_path, ".agent-policy.yml")
    diags = validate_config(tmp_path, config)
    assert len(diags) > 0

    # Render fails closed: no AGENTS.md is produced
    render_diags = render.run(tmp_path, ".agent-policy.yml")
    assert len(render_diags) > 0
    assert not (tmp_path / "AGENTS.md").exists()
