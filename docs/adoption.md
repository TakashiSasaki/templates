# Existing repository adoption

## Purpose

Adoption brings an existing repository under `agent-policy` management without replacing handwritten instructions before their policy meaning has been reviewed.

Use initialization when the repository has no conflicting instruction output. Use adoption when files such as `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, repository-local policies, or existing agent skills are already present.

## Command model

The planned CLI workflow is:

```bash
agent-policy --repository /path/to/product adopt inspect
agent-policy --repository /path/to/product adopt prepare
agent-policy --repository /path/to/product adopt preview
agent-policy --repository /path/to/product adopt finalize
```

Commands that can write default to dry-run and require `--apply` for mutation.

## Phase 1: inspect

Inspection is read-only. It classifies the repository and inventories adoption-relevant assets.

```bash
agent-policy --repository . --format json adopt inspect
```

The report distinguishes:

| State | Meaning | Next operation |
|---|---|---|
| `unmanaged-empty` | No manifest and no existing instruction assets | `init` |
| `unmanaged-existing` | No manifest, but existing instructions or policies exist | `adopt prepare` |
| `managed` | `.agent-policy.yml` exists | `validate`, `render`, `check` |
| `inconsistent` | Partial, conflicting, or unsafe state | Repair before onboarding |

Inventory records paths, file kinds, generation markers, and byte hashes. It does not copy complete instruction contents into the machine report.

## Phase 2: prepare

Preparation creates an adoption scaffold while preserving the existing primary instruction file.

A typical invocation is:

```bash
agent-policy --repository . adopt prepare \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr"
```

The first invocation is a dry-run. Apply only after reviewing paths and conflicts:

```bash
agent-policy --repository . adopt prepare \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr" \
  --apply
```

Preparation creates or generates the following conceptual state:

```text
.agent-policy.yml
.agent-policy.lock
.agent-policy/adoption.json
.agent-policy/preview/AGENTS.md
policy/project.md
.agents/skills/validate-agent-policy/SKILL.md
```

The manifest initially renders agent instructions to the preview path rather than to the handwritten `AGENTS.md`.

Preparation must stop rather than overwrite:

- an existing `.agent-policy.yml`;
- a conflicting adoption-state file;
- a non-generated preview output;
- a non-generated `validate-agent-policy` skill;
- an unsafe path or symbolic-link escape.

## Policy migration

After preparation, review the handwritten instructions and create repository-local policy modules.

Shared profiles should contain reusable rules. Product-specific invariants, branch topology, verification tiers, compatibility constraints, and justified exceptions remain in project policy.

The CLI does not decide whether a paragraph is permanent policy, temporary priority, historical context, or obsolete guidance. That classification is performed by a human or an agent operating under the bootstrap skill.

## Phase 3: preview

Preview regenerates the configured non-final output and verifies that it matches the current profile and project-policy inputs.

```bash
agent-policy --repository . adopt preview
```

The operation reports whether inventoried handwritten sources changed after preparation. A changed source does not get silently accepted into the cutover baseline; preparation must be reviewed or refreshed.

Review the handwritten instructions and generated preview for semantic coverage, including:

- preserved invariants and prohibitions;
- project-specific exceptions;
- branch and deployment rules;
- required verification commands or tiers;
- temporary priorities that should not become permanent policy;
- obsolete or contradictory guidance that should not be revived.

`agent-policy check` must validate the configured preview path rather than assuming that generated instructions are always named `AGENTS.md`.

## Phase 4: finalize

Finalization performs the explicit cutover from handwritten instructions to generated instructions.

```bash
agent-policy --repository . adopt finalize \
  --primary-instructions AGENTS.md \
  --backup-path .agent-policy/adoption/original/AGENTS.md
```

Review the dry-run, then apply explicitly:

```bash
agent-policy --repository . adopt finalize \
  --primary-instructions AGENTS.md \
  --backup-path .agent-policy/adoption/original/AGENTS.md \
  --apply
```

Finalization requires unchanged source hashes, a current preview, valid configuration and policy, a safe and unused backup path, and a final output path that can be generated without overwriting unrelated files.

The operation preserves the original file byte-for-byte before changing the manifest output path. Rendering, lock generation, and adoption-state update are transactional. Failure restores the pre-finalization configuration and original instruction file.

Finalization is never performed by automatic repository classification, generic bootstrap `--apply`, or an unattended update.

## Bootstrap skill behavior

The `bootstrap-agent-policy` orphan branch remains the single directly cloneable onboarding skill.

The skill invokes one pinned full SHA from `main` and uses CLI inspection to select the safe workflow:

```text
unmanaged-empty     -> propose init
unmanaged-existing  -> propose adoption preparation
managed             -> stop bootstrap and use normal validation
inconsistent        -> stop mutation and explain required repair
```

Automatic selection is read-only. Applying a change requires an explicit mode. Adoption application stops at preparation; finalization requires a separate, explicit instruction after semantic review.

## Trust-anchor update

CLI adoption support is merged and tested on `main` before the bootstrap manifest is updated. The manifest update pins the exact reviewed commit and is handled as a separate trust-anchor change.

The bootstrap skill must never replace that SHA with `main`, another branch, a tag, or any mutable reference.

## Non-goals

Adoption does not automatically:

- transform free-form prose into policy modules;
- register generated skills in arbitrary product-specific manifests;
- alter Git history or repository settings;
- commit, push, merge, or deploy;
- overwrite the primary instruction file during preparation;
- finalize merely because validation passes.
