---
description: Describes the policy toolchain, integrated bootstrap skill, and directory responsibilities on the templates policy branch.
---

# Repository structure

The `policy` branch of `TakashiSasaki/templates` is an orphan history with no common ancestor with the repository's other long-lived `main`, `site`, and `webapp` branches. The `policy` branch contains both the policy toolchain and the first-adoption trust seed.

The bootstrap skill is under `skills/bootstrap-agent-policy/`. Its manifest pins a reviewed full commit SHA, so it never executes the mutable `policy` branch tip.

## The `policy` branch

The placeholder below displays the complete Git-tracked tree of the `policy` branch. During documentation publication, the preview manifest is generated from the same commit.

<!-- BEGIN VERIFIED TREE: policy -->
<div class="repository-tree" data-repository-branch="policy">
<p class="repository-tree__loading" role="status">Loading tree…</p>
</div>
<!-- END VERIFIED TREE: policy -->

## Main directory responsibilities

| Path | Responsibility |
|---|---|
| `policy/` | Canonical shared policy. Each rule is maintained as Markdown with YAML front matter. |
| `profiles/` | Declares named selections of shared policy modules for an agent operation or risk context. Profiles determine which shared rules are included; rule metadata determines final rule ordering. |
| `schemas/` | JSON Schemas for product-repository `.agent-policy.yml` and adoption state. The toolchain repository is `TakashiSasaki/templates`. |
| `src/agent_policy/` | Python CLI implementing unified `adopt inspect/prepare/preview/finalize`, `validate`, `render`, and `check`; the hidden `init` command remains an internal fresh-adoption primitive. |
| `templates/` | Generation templates for `AGENTS.md`, product-specific policy, consumer workflows, and related outputs. |
| `skills/` | Canonical normal-operation skills and the first-adoption trust seed integrated at `skills/bootstrap-agent-policy/`. |
| `tests/` | Validation for configuration, adoption transactions, rendering, lock state, path safety, repository identity, and bootstrap trust boundaries. |
| `docs/` | Adoption guidance, architecture, ADRs, PWA assets, and repository-preview UI. |
| `scripts/` | Branch-maintenance and publication helpers such as repository-preview generation and validation. |
| `.github/workflows/` | CI and build-only documentation validation for `policy`. This branch has no Pages deployment authority. |

For a selection guide and the complete current profile catalog, see [Policy profiles](shared-policy/profiles.md).

## Integrated bootstrap skill

```text
skills/bootstrap-agent-policy/
  SKILL.md
  README.md
  bootstrap-manifest.yml
  scripts/
    bootstrap.py
    install.py
    uninstall.py
```

| Path | Responsibility |
|---|---|
| `SKILL.md` | Defines trigger conditions, inspection, state-derived fresh/migration adoption strategy, safety constraints, and separation of migration finalization. |
| `bootstrap-manifest.yml` | Pins the full SHA of `TakashiSasaki/templates` and the allowed internal route set. It does not include a finalize route. |
| `scripts/bootstrap.py` | Acquires the pinned CLI in a temporary environment, inspects repository state, applies the corresponding adoption strategy when authorized, and runs post-apply verification. |
| `scripts/install.py` | Safely copies the skill from a reviewed checkout into a skill directory. |
| `scripts/uninstall.py` | Removes an installed skill after checking its identity marker. |
| `tests/test_bootstrap_skill.py` | Verifies the manifest, pin, strategy routes, safety constraints, state parsing, and post-apply commands. |

## Transfer of control before and after adoption

```text
before adoption
  bootstrap-agent-policy skill in the user environment
      ↓ repository + full SHA from bootstrap-manifest.yml
  pinned agent-policy CLI from templates
      ↓ adopt inspect
  ├─ unmanaged-empty
  │    └─ fresh adoption via adopt prepare --apply
  │         └─ internal init primitive → managed
  │
  └─ unmanaged-existing
       └─ migration adoption via adopt prepare --apply
            ↓ preview and semantic review
          adopt finalize --apply by a separate explicit instruction

after adoption
  product-repository .agent-policy.yml
  .agent-policy.lock
  generated agent instructions and normal-operation skills
  repository-local CI
```

Before adoption, the bootstrap package is the trust seed. After fresh adoption or migration finalization, control transfers to the configuration, lock state, and generated outputs recorded in the product repository.
