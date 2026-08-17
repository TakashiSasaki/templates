# Getting started

## Prerequisites

The target must be a Git repository. Python 3.11 or later and Git are required. When `uvx` is available, the CLI can run in a temporary environment. Otherwise, the bootstrap script creates a temporary Python virtual environment.

## Recommended: adopt through the integrated bootstrap skill

The bootstrap skill is maintained at `skills/bootstrap-agent-policy/` in the `policy` branch of `TakashiSasaki/templates`. Check out a reviewed full commit SHA and install the skill into the agent's skill directory.

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

The skill's own `bootstrap-manifest.yml` pins the `TakashiSasaki/templates` toolchain revision that it will execute by full SHA. Do not replace that revision with a mutable reference such as `policy`, a tag, or an abbreviated SHA.

## 1. Inspect the repository and review the adoption plan

Bootstrap is a dry run by default. From the installed skill directory, run:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository
```

The bootstrap script executes `agent-policy adopt inspect` through the pinned toolchain and classifies the target as one of:

- `unmanaged-empty`: no existing instructions; use fresh adoption;
- `unmanaged-existing`: existing instructions or policy are present; use migration adoption;
- `managed`: `.agent-policy.yml` already exists; bootstrap is unnecessary; or
- `inconsistent`: partial adoption, orphaned generated artifacts, unsafe paths, or another inconsistent state must be repaired first.

The adoption strategy is derived from inspection. Users do not select an `init` or `adopt` route.

## 2A. Apply fresh adoption

For `unmanaged-empty`, review the dry-run plan and then apply the inspected transition:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --apply
```

The bootstrap currently uses pinned `agent-policy init` internally as the fresh-adoption primitive, then requires `validate` and `check` to succeed through the same pinned toolchain. Initialization is not a separate user-facing onboarding operation.

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

The existing primary instruction is not replaced. The operation primarily creates the following prepared artifacts and runs `adopt preview`:

```text
.agent-policy.yml
.agent-policy.lock
.agent-policy/adoption.json
.agent-policy/preview/AGENTS.md
policy/project.md
.agents/skills/validate-agent-policy/SKILL.md
```

Represent the semantics of the handwritten instructions in project policy and review the semantic difference against the preview. The CLI does not automatically convert free-form instructions into policy.

Cutover is a separate phase. After review, run `agent-policy adopt finalize` as a dry run using the CLI from the same repository and full SHA pinned by the manifest, and then explicitly use `--apply` to replace the primary instruction with the generated output. Generic bootstrap `--apply` does not perform migration finalization.

## 3. Author product-specific policy

In `policy/project.md`, record invariants, compatibility requirements, and verification methods that apply only to that product. Do not copy the canonical shared policy into the product repository and edit it there.

For normal managed operation, run:

```bash
agent-policy --repository . validate
agent-policy --repository . render
agent-policy --repository . check
```

During migration adoption preparation, update the shadow preview after editing project policy:

```bash
agent-policy --repository . adopt preview
```

## 4. Review and commit the changes

Fresh adoption, migration preparation, preview, finalization, and regeneration do not automatically create Git commits or push changes. Review the generated diff and commit it through the same normal review flow used for product code.

!!! note
    The bootstrap skill is the first-adoption trust seed. After fresh adoption or migration finalization, normal operation is pinned by the product repository's `.agent-policy.yml` and `.agent-policy.lock`.
