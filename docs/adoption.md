# Repository adoption

## Purpose

Adoption is the single user-facing onboarding operation for bringing an unmanaged repository under `agent-policy` management. Read-only inspection determines which internal strategy is safe:

- **fresh adoption** for `unmanaged-empty`, where no existing instruction assets need to be preserved;
- **migration adoption** for `unmanaged-existing`, where handwritten instructions, repository-local policies, or existing agent skills must remain authoritative until their policy meaning has been reviewed.

The user does not choose between separate `init` and `adopt` onboarding routes. The implementation may reuse initialization machinery internally for fresh adoption, but that is an internal primitive rather than a separate onboarding concept.

This document describes the canonical toolchain CLI directly. The normal consumer workflow after installing the `agent-policy` skill uses the installed `scripts/bootstrap.py` wrapper for unmanaged repositories and `scripts/run.py` for managed operations. Installing the skill does not by itself place an `agent-policy` executable globally on `PATH`.

## Command model

```text
agent-policy --repository /path/to/product adopt inspect
agent-policy --repository /path/to/product adopt prepare
agent-policy --repository /path/to/product adopt preview
agent-policy --repository /path/to/product adopt finalize
```

`inspect` is always read-only. `prepare` defaults to dry-run and requires `--apply` for mutation. For fresh adoption, applying `prepare` completes onboarding directly and normal `validate`/`check` operations become available. For migration adoption, `prepare` creates a staged state; `preview` regenerates that prepared state and `finalize` performs the later explicit cutover.

## Phase 1: inspect

```bash
agent-policy --repository . adopt inspect
agent-policy --repository . --format json adopt inspect
```

| State | Meaning | Selected strategy / next operation |
|---|---|---|
| `unmanaged-empty` | No manifest and no existing instruction assets | Fresh adoption via `adopt prepare` |
| `unmanaged-existing` | No manifest, but existing instructions, policies, or skills exist | Migration adoption via `adopt prepare` |
| `managed` | `.agent-policy.yml` exists | `validate`, `render`, `check` |
| `inconsistent` | Partial, conflicting, generated-only, or unsafe state | Repair before onboarding |

Inventory diagnostics record lexical paths, SHA-256 hashes, and generation-marker state. Repository-internal symbolic links are accepted only when they resolve safely to regular files. Directory targets, dangling targets, repository-external targets, absolute symlink components, and unsafe source shapes classify the repository as inconsistent.

## Phase 2: prepare

The same command prepares the state-derived strategy. The first invocation is a dry run.

```bash
agent-policy --repository . adopt prepare \
  --profile core \
  --profile security-baseline
```

Apply only after reviewing paths and conflicts:

```bash
agent-policy --repository . adopt prepare \
  --profile core \
  --profile security-baseline \
  --apply
```

### Fresh adoption

For `unmanaged-empty`, `adopt prepare` delegates to the internal initialization primitive. `--primary-instructions` is invalid because there is no existing instruction file to preserve. Applied fresh adoption creates the normal managed state directly, typically including:

```text
.agent-policy.yml
.agent-policy.lock
AGENTS.md
policy/project.md
.agents/skills/validate-agent-policy/SKILL.md
```

Fresh adoption does not create `.agent-policy/adoption.json` or a shadow preview. After application, run `validate` and `check`; no migration finalization step exists.

The internal initialization primitive validates all planned destinations and refuses conflicts rather than overwriting existing paths or partially initializing the repository.

### Migration adoption

For `unmanaged-existing`, preparation preserves the selected primary instruction file and creates a staged migration state. A single discovered supported instruction file is selected automatically. If multiple supported instruction files are discovered, an explicit valid `--primary-instructions` is required before mutation. If zero supported instruction files are discovered, create a supported instruction file first; policy or skill assets alone cannot be selected as primary instructions.

```bash
agent-policy --repository . adopt prepare \
  --primary-instructions AGENTS.md \
  --profile core \
  --profile security-baseline \
  --verification-command "npm run verify:pr"
```

Applied migration preparation typically creates:

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

The remaining phases apply only to migration adoption. After preparation, review the handwritten instructions and express their durable meaning in shared profiles or repository-local project policy.

Shared profiles contain reusable agent-operation rules. Product-specific invariants, branch topology, verification tiers, compatibility constraints, and justified exceptions remain in project policy. The CLI does not decide whether prose is permanent policy, temporary priority, historical context, or obsolete guidance. The primary instruction and inventoried immutable sources remain protected until finalization.

## Phase 3: preview

```bash
agent-policy --repository . adopt preview
agent-policy --repository . adopt preview --state .agent-policy/adoption.json
```

Preview checks that immutable sources have not changed, regenerates the configured shadow instruction, generated skills, and lock, then runs the normal consistency check. Project-policy files are editable manifest inputs. A changed or deleted inventoried handwritten source produces `ADOPTION_SOURCE_CHANGED` and stops preview.

Review handwritten instructions and the generated preview for semantic coverage, including invariants, prohibitions, exceptions, branch and deployment rules, verification requirements, temporary priorities, and obsolete or contradictory guidance.

## Phase 4: finalize

Finalization performs the explicit migration cutover from handwritten instructions to generated instructions. First run a dry run:

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

Finalization is never performed by automatic classification or generic bootstrap `--apply`.

## Single skill behavior

The repository-facing skill is maintained at `skills/agent-policy/` in `TakashiSasaki/templates:policy`. For an unmanaged repository, its `runtime-manifest.json` selects one reviewed stable full SHA and the bootstrap operation uses CLI inspection to choose the safe strategy:

```text
unmanaged-empty     -> fresh adoption
unmanaged-existing  -> migration adoption
managed             -> stop bootstrap and use scripts/run.py
inconsistent        -> stop mutation and explain required repair
```

Applying a change requires explicit `--apply`, not a route-selection flag. Fresh adoption may complete directly. Migration bootstrap stops at preparation and runs preview. The runtime manifest exposes no finalization route; migration finalization requires a separate explicit managed command through `scripts/run.py`.

After `.agent-policy.lock` exists, the same installed skill prefers the repository's full-SHA toolchain pin. A malformed or mutable managed pin fails closed instead of silently falling back to the skill's stable default.

The skill reuses a validated persistent runtime keyed by full revision, runtime-lock SHA-256, Python major/minor, and platform. A valid cache hit requires no network access; a cache miss is staged and verified before atomic activation.

## Trust-anchor updates

Changing the stable repository/full SHA, runtime-lock digest, cache identity, internal route declarations, skill instructions, orchestration scripts, installer, or safety constraints is a trust-anchor change. The skill must never replace the full SHA with `policy`, `main`, another branch, a tag, a short SHA, or another mutable reference.

The current trust-model decision is ADR-0007. ADR-0004 remains historical and is superseded.

## Non-goals

Adoption does not automatically:

- transform free-form prose into policy modules;
- register generated skills in arbitrary product-specific manifests;
- alter Git history or repository settings;
- commit, push, merge, or deploy;
- overwrite handwritten primary instructions during migration preparation;
- finalize migration merely because validation passes.
