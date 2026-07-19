# Existing repository adoption

## Purpose

Adoption brings an existing repository under `agent-policy` management without replacing handwritten instructions before their policy meaning has been reviewed.

The onboarding split uses initialization when the repository has no conflicting instruction output. It uses adoption when files such as `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, repository-local policies, or existing agent skills are already present.

## Command model

The implemented CLI workflow is:

```text
agent-policy --repository /path/to/product adopt inspect
agent-policy --repository /path/to/product adopt prepare
agent-policy --repository /path/to/product adopt preview
agent-policy --repository /path/to/product adopt finalize
```

`inspect` is read-only. `prepare` and `finalize` default to dry-run and require `--apply` for mutation. `preview` is an explicit regeneration command for the prepared generated outputs and lock; it has no `--apply` option and never performs final cutover.

## Phase 1: inspect

Inspection classifies the repository and inventories adoption-relevant assets without writing files.

```bash
agent-policy --repository . adopt inspect
agent-policy --repository . --format json adopt inspect
```

The report distinguishes:

| State | Meaning | Next operation |
|---|---|---|
| `unmanaged-empty` | No manifest and no existing instruction assets | `init` |
| `unmanaged-existing` | No manifest, but existing instructions or policies exist | `adopt prepare` |
| `managed` | `.agent-policy.yml` exists | `validate`, `render`, `check` |
| `inconsistent` | Partial, conflicting, generated-only, or unsafe state | Repair before onboarding |

Inventory diagnostics record lexical paths, SHA-256 hashes, and generation-marker state. They do not copy complete instruction contents into the machine report.

Repository-internal symbolic links are accepted as discovered sources only when they resolve safely to regular files. Directory targets, dangling targets, repository-external targets, absolute symlinks in a source path, and other unsafe source shapes classify the repository as inconsistent.

## Phase 2: prepare

Preparation creates an adoption scaffold while preserving the existing primary instruction file. The first invocation is a dry-run.

```bash
agent-policy --repository . adopt prepare \
  --primary-instructions AGENTS.md \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr"
```

Mutation requires explicit application after reviewing paths and conflicts:

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

The manifest initially renders agent instructions to the preview path rather than to the handwritten primary path.

`prepare` constructs and validates the complete result in a temporary repository before applying anything. It then creates only new files using exclusive creation. If an applied preparation fails, it removes only files created successfully by that invocation.

Preparation stops rather than overwrite:

- an existing `.agent-policy.yml`;
- a conflicting adoption-state file;
- a non-generated preview output;
- a non-generated generated-skill target;
- an unsafe path or symbolic-link boundary;
- an existing source that overlaps a management or generated output.

The selected primary instructions must be one of the discovered supported instruction files: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `.github/copilot-instructions.md`. Files under `.agents/policies` and `.agents/skills` are inventoried and protected but cannot be selected as the primary instructions.

Multiple project-policy inputs may be retained. Preparation can scaffold at most one missing project-policy file; existing policy files remain byte-for-byte unchanged.

## Policy migration

After preparation, review the handwritten instructions and express their durable meaning in shared profiles or repository-local project policy.

Shared profiles should contain reusable rules. Product-specific invariants, branch topology, verification tiers, compatibility constraints, and justified exceptions remain in project policy.

The CLI does not decide whether a paragraph is permanent policy, temporary priority, historical context, or obsolete guidance. That classification is performed by a human or an agent operating under the bootstrap skill. The primary instruction and every inventoried immutable source remain protected until finalization.

## Phase 3: preview

Preview checks that recorded immutable sources have not changed, regenerates the configured shadow instruction, generated skills, and lock, and then runs the normal consistency check.

```bash
agent-policy --repository . adopt preview
agent-policy --repository . adopt preview --state .agent-policy/adoption.json
```

Project-policy files are editable manifest inputs. Changes to them are expected and are incorporated into the regenerated preview. By contrast, a changed or deleted inventoried handwritten source produces `ADOPTION_SOURCE_CHANGED` and stops preview.

The handwritten instructions and generated preview should be reviewed for semantic coverage, including:

- preserved invariants and prohibitions;
- project-specific exceptions;
- branch and deployment rules;
- required verification commands or tiers;
- temporary priorities that should not become permanent policy;
- obsolete or contradictory guidance that should not be revived.

`agent-policy check` validates the configured preview path rather than assuming that generated instructions are always named `AGENTS.md`.

## Phase 4: finalize

Finalization performs the explicit cutover from handwritten instructions to generated instructions. The first invocation validates the complete transaction without changing the live repository.

```bash
agent-policy --repository . adopt finalize \
  --backup-path .agent-policy/adoption/original/AGENTS.md
```

Apply the cutover only after reviewing the dry-run:

```bash
agent-policy --repository . adopt finalize \
  --backup-path .agent-policy/adoption/original/AGENTS.md \
  --apply
```

The primary instruction path is recorded during preparation and read from adoption state during finalization; it is not supplied again as a finalize option.

Finalization requires unchanged immutable source hashes, matching configuration and adoption state, a current preview and lock, valid project-policy inputs, and a safe unused backup path. Strict finalization paths must be lexical regular files without symlink components. A repository-internal primary symlink accepted during inspection and preparation must be materialized as the same intended regular file before finalization.

The transaction:

- preserves the original primary instructions byte-for-byte at the backup path;
- changes the manifest output from the shadow preview to the retained primary path;
- renders generated instructions at the primary path;
- updates `.agent-policy.lock`;
- marks adoption state as finalized;
- removes the shadow preview.

The implementation stages the complete final state in a temporary repository, rechecks live input bytes immediately before the first write, and rolls back files changed by the transaction if rendering, locking, checking, or state update fails.

Finalization is never performed by automatic repository classification, bootstrap automatic routing, generic bootstrap `--apply`, or an unattended update.

## Bootstrap skill behavior

The `bootstrap-agent-policy` orphan branch is the single directly cloneable onboarding skill. It invokes one pinned full SHA from `main` and uses CLI inspection to select the safe workflow:

```text
unmanaged-empty     -> recommend init
unmanaged-existing  -> recommend adoption preparation
managed             -> stop bootstrap and use normal validation
inconsistent        -> stop mutation and explain required repair
```

Automatic selection is read-only advice. Applying a change requires explicit `--route init` or `--route adopt`. Adoption application stops at preparation and runs preview; finalization requires a separate explicit instruction after semantic review. The bootstrap manifest exposes no finalization route.

## Trust-anchor updates

The bootstrap manifest pins the exact reviewed CLI implementation commit. Changing the pinned SHA, route declarations, invocation script, or bootstrap safety constraints is a separate trust-anchor change.

The bootstrap skill must never replace the full SHA with `main`, another branch, a tag, a short SHA, or any mutable reference.

## Non-goals

Adoption does not automatically:

- transform free-form prose into policy modules;
- register generated skills in arbitrary product-specific manifests;
- alter Git history or repository settings;
- commit, push, merge, or deploy;
- overwrite the primary instruction file during preparation;
- finalize merely because validation passes.
