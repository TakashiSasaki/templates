# Getting started

## Prerequisites

The target must be a Git repository. Python 3.11 or later and Git are required. Install the single `agent-policy` skill once; its validated runtime cache is then reused instead of creating a new environment on every invocation.

## Recommended: install the single agent-policy skill

The skill is maintained at `skills/agent-policy/` in the `policy` branch of `TakashiSasaki/templates`. From a reviewed checkout, install it into the agent's skill directory:

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

`runtime-manifest.json` pins the reviewed stable toolchain revision by full SHA and binds that revision's `requirements-runtime.lock` by SHA-256. Do not replace the full SHA with `policy`, a tag, or an abbreviated SHA.

## 1. Inspect the repository and review the adoption plan

For an unmanaged repository, bootstrap is a dry run by default. From the installed skill directory, run:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository
```

The bootstrap operation executes `agent-policy adopt inspect` through the pinned cached runtime and classifies the target as one of:

- `unmanaged-empty`: no existing instructions; use fresh adoption;
- `unmanaged-existing`: existing instructions or policy are present; use migration adoption;
- `managed`: `.agent-policy.yml` and managed state already exist; use `scripts/run.py`; or
- `inconsistent`: partial adoption, orphaned generated artifacts, unsafe paths, or another inconsistent state must be repaired first.

The adoption strategy is derived from inspection. Users do not select an `init` or `adopt` route.

## 2A. Apply fresh adoption

For `unmanaged-empty`, review the dry-run plan and then apply the inspected transition:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --apply
```

The pinned toolchain may use `agent-policy init` internally as the fresh-adoption primitive, then requires `validate` and `check` to succeed through the same runtime. Initialization is not a separate user-facing onboarding operation.

The main files created are:

```text
.agent-policy.yml
.agent-policy.lock
policy/project.md
AGENTS.md
.agents/skills/validate-agent-policy/SKILL.md
```

`.agent-policy.yml` is the human-edited configuration entry point. `.agent-policy.lock`, `AGENTS.md`, and generated skills are managed by the CLI.

## 2B. Prepare migration adoption while preserving existing instructions

For `unmanaged-existing`, choose the primary instruction from an `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `.github/copilot-instructions.md` discovered during inspection when more than one candidate exists.

Review the dry run first:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md
```

After reviewing the plan, apply the prepared state:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md \
  --apply
```

The existing primary instruction is not replaced. The operation creates the prepared adoption state and runs `adopt preview`.

Represent the semantics of the handwritten instructions in project policy and review the semantic difference against the preview. The CLI does not automatically convert free-form instructions into policy.

Cutover is separate. After review, use the same installed skill and the repository-pinned toolchain:

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt finalize
```

Review that dry run, then add `--apply` explicitly. Generic bootstrap `--apply` cannot perform migration finalization.

## 3. Operate a managed repository

Once `.agent-policy.lock` exists, use `scripts/run.py`. The runner prefers the full SHA recorded by the repository rather than the skill's default stable pin:

```bash
python scripts/run.py --repository . validate
python scripts/run.py --repository . render
python scripts/run.py --repository . check
```

During migration preparation, update the shadow preview with:

```bash
python scripts/run.py --repository . adopt preview
```

A malformed or mutable `.agent-policy.lock` toolchain pin fails closed. The skill does not silently substitute the stable default.

## 4. Runtime-cache behavior

Runtime cache identity includes the full toolchain SHA, runtime-lock SHA-256, Python major/minor, and platform. A valid cache entry is reused without network access.

For the stable default, `runtime-manifest.json` already records the lock digest, so the cache identity can be checked before network access. For another full SHA selected by a managed repository, an existing validated cache for the same revision/Python/platform can also be reused offline. Otherwise the skill fetches that revision's runtime lock once, computes its digest, and builds a new staged runtime.

## 5. Author policy, review, and commit

In `policy/project.md`, record invariants, compatibility requirements, and verification methods that apply only to that product. Do not copy the canonical shared policy into the product repository and edit it there.

Fresh adoption, migration preparation, preview, finalization, and regeneration do not automatically create Git commits or push changes. Review the generated diff and commit it through the normal review flow used for product code.

!!! note
    The same `agent-policy` skill is used before and after adoption. Before adoption its reviewed runtime manifest is the default trust seed; after adoption `.agent-policy.lock` becomes authoritative for the managed repository's toolchain revision.
