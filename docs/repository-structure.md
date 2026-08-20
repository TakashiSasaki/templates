---
description: Describes the policy toolchain, single agent-policy skill, persistent runtime cache, and directory responsibilities on the templates policy branch.
---

# Repository structure

The `policy` branch of `TakashiSasaki/templates` is an orphan history with no common ancestor with the repository's independent `site` and `composition` authority histories. The branch contains the Policy toolchain and one repository-facing `agent-policy` skill. Agent Skill and Web application artifact semantics are owned by Composition rather than separate provider branches.

The skill is under `skills/agent-policy/`. Its runtime manifest pins a reviewed full commit SHA and the SHA-256 of that revision's runtime dependency lock, so it never executes the mutable `policy` branch tip.

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
| `schemas/` | JSON Schemas for product-repository `.agent-policy.yml`, adoption state, and stable release metadata. |
| `src/agent_policy/` | Canonical Python CLI implementing unified `adopt inspect/prepare/preview/finalize`, `validate`, `render`, and `check`; the hidden `init` command remains an internal fresh-adoption primitive. |
| `templates/` | Generation templates for `AGENTS.md`, product-specific policy, consumer workflows, and related outputs. |
| `skills/agent-policy/` | Single installable repository-facing skill for unmanaged bootstrap, managed command dispatch, immutable pin selection, and persistent runtime-cache management. |
| `tests/` | Validation for configuration, adoption transactions, rendering, lock state, path safety, release identity, runtime distribution, cache behavior, and single-skill trust boundaries. |
| `docs/` | Adoption guidance, architecture, ADRs, PWA assets, and repository-preview UI. |
| `scripts/` | Branch-maintenance, release verification, runtime-distribution verification, and publication helpers. |
| `.github/workflows/` | CI and build-only documentation validation for `policy`. This branch has no Pages deployment authority. |

For a selection guide and the complete current profile catalog, see [Policy profiles](shared-policy/profiles.md).

## Single agent-policy skill

```text
skills/agent-policy/
  SKILL.md
  README.md
  runtime-manifest.json
  scripts/
    bootstrap.py
    install.py
    run.py
    runtime.py
    uninstall.py
```

| Path | Responsibility |
|---|---|
| `SKILL.md` | Defines when to bootstrap an unmanaged repository, when to run managed commands, cache/pin semantics, and migration-finalization safety. |
| `runtime-manifest.json` | Pins the stable full SHA of `TakashiSasaki/templates`, the SHA-256 of its `requirements-runtime.lock`, stable project identity, and the closed bootstrap route set. It contains no finalize route. |
| `scripts/runtime.py` | Resolves the stable or repository-pinned full SHA, constructs or reuses the persistent runtime cache, sanitizes Python/pip inputs, and verifies the exact installed distribution set. |
| `scripts/bootstrap.py` | Inspects unmanaged repository state and applies either the state-derived fresh adoption or migration adoption strategy when authorized. Migration bootstrap stops after preview. |
| `scripts/run.py` | Runs normal managed commands through the cached runtime selected from `.agent-policy.lock`. |
| `scripts/install.py` | Atomically installs or replaces the skill from a reviewed checkout after identity and path-safety checks. |
| `scripts/uninstall.py` | Removes an installed skill after checking its identity marker. |
| `tests/test_agent_policy_skill.py` | Verifies pin precedence, cache identity, offline cache hits, environment isolation, bootstrap safety, managed dispatch, and install/uninstall guards. |

## Runtime and control transfer

```text
before adoption
  installed agent-policy skill
      ↓ stable full SHA + runtime-lock digest from runtime-manifest.json
  validated persistent runtime cache
      ↓ adopt inspect
  ├─ unmanaged-empty
  │    └─ fresh adoption --apply
  │         └─ internal init primitive → managed
  │
  └─ unmanaged-existing
       └─ migration adoption prepare --apply
            ↓ preview and semantic review
          separate explicit adopt finalize --apply

after adoption
  same installed agent-policy skill
      ↓ full SHA from product-repository .agent-policy.lock
  validated persistent runtime cache
      ↓ normal managed commands
  .agent-policy.yml + generated outputs + repository-local CI
```

Before adoption, `runtime-manifest.json` supplies the reviewed stable default toolchain. After `.agent-policy.lock` exists, the same skill prefers the repository's full-SHA pin. A malformed or mutable managed pin fails closed instead of silently falling back.

Runtime cache identity includes repository, full revision, runtime-lock SHA-256, Python major/minor, and platform. A valid cache entry is reusable without network access; a cache miss is built in a staging directory and moved into place only after dependency and installed-set validation succeed.
