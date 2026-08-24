# Getting started

## Prerequisites

The target must be a Git repository. Python 3.11 or later and Git are required. Install the single `agent-policy` skill once; its validated runtime cache is then reused instead of creating a new environment on every invocation.

## Recommended: install the single agent-policy skill

Use the published installer whose script URL is pinned to a full immutable commit SHA:

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/b330f517ad2a348fafc7cb9f690b4df298ee24f4/scripts/install_agent_policy_skill.py', timeout=30).read())" /path/to/agent-skills/agent-policy
```

Append `--replace` only when replacing an existing `agent-policy` skill installation.

Three full-SHA identities intentionally remain separate:

- **installer script revision** `b330f517ad2a348fafc7cb9f690b4df298ee24f4` identifies the remotely executed installer;
- **skill source revision** `1656a0a18076dcb90d5ccadc0c6271fb557fe2a7` identifies the installed `skills/agent-policy/` subtree; and
- the **stable runtime revision** in the installed `runtime-manifest.json` identifies the canonical CLI runtime used by the skill.

`release/skill-installer.json` records the first two identities. The command does not execute `policy`, a tag, or an abbreviated SHA.

A reviewed checkout is also available as a repository-development installation path:

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

That command installs the skill tree from the checkout being reviewed. It is not necessarily byte-for-byte identical to the currently published remote distribution unless the checkout matches the skill-source revision in `release/skill-installer.json`. Use the published remote command when reproducing the published distribution is the goal.

`runtime-manifest.json` pins the reviewed stable toolchain revision by full SHA and binds that revision's `requirements-runtime.lock` by SHA-256. Do not replace any of these full-SHA identities with `policy`, a tag, or an abbreviated SHA.

The normal consumer workflow uses `scripts/bootstrap.py` and `scripts/run.py` from the installed skill directory. Direct `agent-policy ...` examples in the CLI and adoption reference describe the canonical toolchain CLI. Installing the skill does not by itself install an `agent-policy` executable globally on `PATH`.

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

### Choose the policy profile baseline

Policy profiles select which shared policy modules participate in a context. For a normal coding or maintenance repository, use `core` and `security-baseline` as the baseline. The normal bootstrap path uses exactly that pair for both fresh adoption and migration preparation.

Add operation-specific profiles only to contexts that perform those operations:

- add `pull-request` when the context owns pull-request lifecycle work;
- add `review` when the context reviews changes for blocking defects; and
- add `external-artifact-intake` when the context receives or stages externally produced artifacts.

Fresh adoption creates `.agent-policy.yml` with the baseline profiles. After adoption, edit that human-owned configuration when the repository needs additional contexts or profiles, then run the normal managed validation and rendering commands. See [Policy profiles](shared-policy/profiles.md) for the profile catalog, composition semantics, and detailed selection guidance.

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

For `unmanaged-existing`, a single supported instruction discovered as `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `.github/copilot-instructions.md` is selected automatically. If multiple supported instruction files are discovered, choose the authoritative primary with `--primary-instructions`. If no supported instruction files are discovered, create one supported instruction file first; policy or skill assets alone cannot be selected as primary instructions.

When an explicit primary is required, review the dry run first:

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

Omit `--primary-instructions` when inspection found exactly one supported instruction file and selected it automatically.

The existing primary instruction is not replaced. The operation creates the prepared adoption state and runs `adopt preview`.

Represent the semantics of the handwritten instructions in `policy/project.md` and any other human-owned Policy configuration that needs to change. The CLI does not automatically convert free-form instructions into policy.

After every such Policy edit during migration preparation, regenerate the preview before attempting cutover:

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt preview
```

Review the regenerated preview and its semantic difference from the handwritten primary instruction. `adopt finalize` deliberately rejects a stale preview if Policy inputs changed after the last preview; do not treat `STALE_OUTPUT` as a reason to bypass or hand-edit generated state.

Cutover is separate. Only after the current preview has been reviewed, use the same installed skill and the repository-pinned toolchain:

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
