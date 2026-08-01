# Existing repository adoption

## Purpose

Adoption brings an existing repository under `agent-policy` management without replacing handwritten instructions before their policy meaning has been reviewed.

Initialization is used when no conflicting instruction output exists. Adoption is used when files such as `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, repository-local policies, or existing agent skills are already present.

## Command model

```text
agent-policy --repository /path/to/product adopt inspect
agent-policy --repository /path/to/product adopt prepare
agent-policy --repository /path/to/product adopt preview
agent-policy --repository /path/to/product adopt finalize
```

`inspect` is read-only. `prepare` and `finalize` default to dry-run and require `--apply` for mutation. `preview` regenerates the prepared generated outputs and lock; it never performs final cutover.

## Phase 1: inspect

```bash
agent-policy --repository . adopt inspect
agent-policy --repository . --format json adopt inspect
```

| State | Meaning | Next operation |
|---|---|---|
| `unmanaged-empty` | No manifest and no existing instruction assets | `init` |
| `unmanaged-existing` | No manifest, but existing instructions or policies exist | `adopt prepare` |
| `managed` | `.agent-policy.yml` exists | `validate`, `render`, `check` |
| `inconsistent` | Partial, conflicting, generated-only, or unsafe state | Repair before onboarding |

Inventory diagnostics record lexical paths, SHA-256 hashes, and generation-marker state. Repository-internal symbolic links are accepted only when they resolve safely to regular files. Directory targets, dangling targets, repository-external targets, absolute symlink components, and unsafe source shapes classify the repository as inconsistent.

## Phase 2: prepare

Preparation creates an adoption scaffold while preserving the existing primary instruction file. The first invocation is a dry-run.

```bash
agent-policy --repository . adopt prepare \
  --primary-instructions AGENTS.md \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr"
```

Apply only after reviewing paths and conflicts:

```bash
agent-policy --repository . adopt prepare \
  --primary-instructions AGENTS.md \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr" \
  --apply
```

Preparation creates or generates the following default state:

```text
.agent-policy.yml
.agent-policy.lock
.agent-policy/adoption.json
.agent-policy/preview/AGENTS.md
policy/project.md
.agents/skills/validate-agent-policy/SKILL.md
```

The manifest initially renders instructions to the preview path rather than the handwritten primary path. Preparation constructs and validates the complete result in a temporary repository before applying anything, creates only new files, and rolls back files created by the invocation if application fails.

Preparation stops rather than overwrite an existing manifest, conflicting adoption state, non-generated preview or skill target, unsafe path, or source that overlaps management output.

The selected primary instructions must be one of the discovered supported instruction files: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `.github/copilot-instructions.md`. Assets under `.agents/policies` and `.agents/skills` are inventoried and protected but cannot be primary instructions.

## Policy migration

After preparation, review the handwritten instructions and express their durable meaning in shared profiles or repository-local project policy.

Shared profiles contain reusable agent-operation rules. Product-specific invariants, branch topology, verification tiers, compatibility constraints, and justified exceptions remain in project policy. The CLI does not decide whether prose is permanent policy, temporary priority, historical context, or obsolete guidance. The primary instruction and inventoried immutable sources remain protected until finalization.

## Phase 3: preview

```bash
agent-policy --repository . adopt preview
agent-policy --repository . adopt preview --state .agent-policy/adoption.json
```

Preview checks that immutable sources have not changed, regenerates the configured shadow instruction, generated skills, and lock, then runs the normal consistency check. Project-policy files are editable manifest inputs. A changed or deleted inventoried handwritten source produces `ADOPTION_SOURCE_CHANGED` and stops preview.

Review handwritten instructions and the generated preview for semantic coverage, including invariants, prohibitions, exceptions, branch and deployment rules, verification requirements, temporary priorities, and obsolete or contradictory guidance.

## Phase 4: finalize

Finalization performs the explicit cutover from handwritten instructions to generated instructions. First run a dry-run:

```bash
agent-policy --repository . adopt finalize \
  --backup-path .agent-policy/adoption/original/AGENTS.md
```

Apply only after review:

```bash
agent-policy --repository . adopt finalize \
  --backup-path .agent-policy/adoption/original/AGENTS.md \
  --apply
```

Finalization requires unchanged immutable source hashes, matching configuration and adoption state, a current preview and lock, valid project-policy inputs, and a safe unused backup path. The transaction preserves the original primary instructions byte-for-byte, switches output from preview to the retained primary path, renders generated instructions, updates the lock, marks adoption finalized, and removes the shadow preview. Failure during the transaction restores files owned by the operation.

Finalization is never performed by automatic classification, bootstrap automatic routing, or generic bootstrap `--apply`.

## Integrated bootstrap skill behavior

The onboarding skill is maintained at `skills/bootstrap-agent-policy/` in `TakashiSasaki/templates:policy`. Its manifest invokes one pinned full SHA from `TakashiSasaki/templates` and uses CLI inspection to select the safe workflow:

```text
unmanaged-empty     -> recommend init
unmanaged-existing  -> recommend adoption preparation
managed             -> stop bootstrap and use normal validation
inconsistent        -> stop mutation and explain required repair
```

Automatic selection is read-only advice. Applying a change requires explicit `--route init` or `--route adopt`. Adoption application stops at preparation and runs preview. The bootstrap manifest exposes no finalization route; finalization requires a separate explicit instruction using the same pinned repository and full SHA.

## Trust-anchor updates

Changing the bootstrap repository, pinned SHA, route declarations, invocation script, installer, or safety constraints is a trust-anchor change. The skill must never replace the full SHA with `policy`, `main`, another branch, a tag, a short SHA, or another mutable reference.

## Non-goals

Adoption does not automatically:

- transform free-form prose into policy modules;
- register generated skills in arbitrary product-specific manifests;
- alter Git history or repository settings;
- commit, push, merge, or deploy;
- overwrite the primary instruction file during preparation;
- finalize merely because validation passes.
