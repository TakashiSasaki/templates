# Getting started

This page is the first-use path for adding coding-agent operating rules to an existing Git repository. You do not need to understand the Policy trust model, the three SHA identities, or runtime-cache internals before the first dry run.

The first decision is simple:

```text
No existing AGENTS.md / CLAUDE.md / GEMINI.md / Copilot instructions
        ↓
fresh adoption

Existing agent instructions
        ↓
migration adoption
```

Do not guess the route yourself. The bootstrap dry run inspects the repository and tells you which state it found.

## 0. What this workflow changes

Policy is an independent authority for coding-agent operating rules. It is not a Composition capability. You may adopt Policy in any suitable Git repository, including a repository that also uses Composition.

After successful adoption, the important ownership boundary is:

- **you edit** `.agent-policy.yml` and product-specific policy such as `policy/project.md`;
- **the Policy toolchain manages** `.agent-policy.lock`, rendered `AGENTS.md`, and generated validation skills;
- existing primary agent instructions are preserved during migration preparation until you explicitly finalize cutover.

The shortest first-use path is:

```text
check prerequisites
  ↓
install agent-policy skill
  ↓
bootstrap dry run / inspect
  ↓
  ├─ unmanaged-empty    → fresh adoption
  └─ unmanaged-existing → migration adoption
  ↓
edit human-owned Policy input
  ↓
render → validate → check
```

## 1. Check prerequisites

The target must already be a Git repository. Python 3.11 or later and Git are required.

**Run**

```bash
git --version
python --version
```

**Expected**

Both commands succeed and the target repository is available at a path such as `/path/to/product-repository`.

**Repository change**

None.

**Next**

Install the single `agent-policy` skill outside the product repository.

## 2. Install the `agent-policy` skill

Use the published immutable installer:

**Run**

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/f4457c90854db34c3ce8e1c381f67a4d7d5ea523/scripts/install_agent_policy_skill.py', timeout=30).read())" /path/to/agent-skills/agent-policy
```

Append `--replace` only when intentionally replacing an existing `agent-policy` skill installation.

**Expected**

The installed skill contains `scripts/bootstrap.py` and `scripts/run.py`.

**Repository change**

None in the product repository. Installing the skill does not by itself install an `agent-policy` executable globally on `PATH`.

**What this means**

You now have the normal consumer entry point. The full-SHA installer is intentional; the detailed immutable-source and runtime-cache trust model is explained later in [Trust and runtime details](#trust-and-runtime-details).

**Next**

Run the bootstrap inspection. It is a dry run by default.

## 3. Inspect the repository with a dry run

From the installed skill directory:

**Run**

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository
```

**Expected**

The bootstrap operation runs `agent-policy adopt inspect` through the pinned runtime and classifies the target as one of:

- `unmanaged-empty` — no existing instructions; use **fresh adoption**;
- `unmanaged-existing` — existing instructions or policy are present; use **migration adoption**;
- `managed` — `.agent-policy.yml` and managed state already exist; skip first-time adoption and use `scripts/run.py`;
- `inconsistent` — partial adoption, orphaned generated artifacts, unsafe paths, or another inconsistent state must be repaired before continuing.

**Repository change**

None. Bootstrap without `--apply` is a dry run.

**What this means**

You do not select an `init` or `adopt` route manually. Inspection derives the supported next transition from repository state.

**Next**

- `unmanaged-empty` → continue with [4A. Fresh adoption](#4a-fresh-adoption).
- `unmanaged-existing` → continue with [4B. Migration adoption](#4b-migration-adoption).
- `managed` → continue with [6. Render, validate, and check a managed repository](#6-render-validate-and-check-a-managed-repository).
- `inconsistent` → stop first-use adoption and follow the diagnostic/recovery guidance reported by the toolchain.

## 4A. Fresh adoption

Use this branch when inspection reported `unmanaged-empty`.

### Review before mutation

The dry run from Section 3 is the adoption plan. Review the target and proposed changes first.

### Apply the fresh adoption

**Run**

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --apply
```

**Expected**

The pinned toolchain may use `agent-policy init` internally as the fresh-adoption primitive, then requires validation/check to succeed through the same runtime. Initialization is not a separate user-facing onboarding step.

The main created files are:

```text
.agent-policy.yml
.agent-policy.lock
policy/project.md
AGENTS.md
.agents/skills/validate-agent-policy/SKILL.md
```

**Repository change**

Yes. This is the first mutating Policy step.

**What this means**

- `.agent-policy.yml` is human-owned configuration.
- `policy/project.md` is human-owned product-specific policy input.
- `.agent-policy.lock`, rendered `AGENTS.md`, and generated validation skills are tool-managed outputs/state.

**Next**

Review the baseline profiles, edit human-owned Policy input if necessary, then continue to [5. Choose the baseline profile and edit human-owned Policy input](#5-choose-the-baseline-profile-and-edit-human-owned-policy-input).

## 4B. Migration adoption

Use this branch when inspection reported `unmanaged-existing`.

Migration is intentionally two-stage: **prepare and preview first; finalize cutover only after semantic review**.

### Select the authoritative existing instruction when necessary

A single supported instruction discovered as `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `.github/copilot-instructions.md` is selected automatically.

If multiple supported instruction files are discovered, choose the authoritative primary explicitly:

**Run**

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md
```

If inspection found exactly one supported instruction file, omit `--primary-instructions`.

If no supported instruction files are discovered, create one supported instruction file first; policy or skill assets alone cannot be selected as primary instructions.

**Repository change**

None. This remains a dry run until `--apply` is present.

### Apply migration preparation

After reviewing the plan:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository \
  --primary-instructions AGENTS.md \
  --apply
```

Omit `--primary-instructions` when the primary was selected automatically.

**Expected**

The existing primary instruction is **not replaced**. Bootstrap creates prepared Policy state and runs `adopt preview`.

**What this means**

Policy does not automatically convert free-form existing instructions into policy. You must represent their intended semantics in human-owned `policy/project.md` and any other Policy input that needs to change.

### Refresh and review the preview after every Policy edit

After changing human-owned Policy input during migration preparation:

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt preview
```

Review the regenerated preview against the handwritten primary instruction. `adopt finalize` rejects a stale preview if Policy inputs changed after the last preview; do not bypass or hand-edit generated state when you see `STALE_OUTPUT`.

### Finalize only after semantic review

First run the finalization dry run:

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt finalize
```

Review it. Then mutate explicitly:

```bash
python scripts/run.py \
  --repository /path/to/product-repository \
  adopt finalize --apply
```

Generic bootstrap `--apply` cannot perform migration finalization.

**Next**

Continue to the normal managed workflow.

## 5. Choose the baseline profile and edit human-owned Policy input

Policy profiles select which shared policy modules participate in a context. For a normal coding or maintenance repository, the baseline is:

```text
core
security-baseline
```

The baseline profiles are `core` and `security-baseline`. The normal bootstrap path uses exactly that pair for fresh adoption and migration preparation.

Add operation-specific profiles only when the context actually performs those operations:

- `pull-request` for contexts that own pull-request lifecycle work;
- `review` for contexts that review changes for blocking defects;
- `external-artifact-intake` for contexts that receive or stage externally produced artifacts.

Fresh adoption creates `.agent-policy.yml` with the baseline profiles. Edit that human-owned file when the repository needs additional contexts/profiles. Put product-specific invariants, compatibility requirements, and verification methods in `policy/project.md` rather than copying canonical shared policy into the product repository.

See [Policy profiles](shared-policy/profiles.md) for the complete profile catalog and composition semantics.

## 6. Render, validate, and check a managed repository

Once `.agent-policy.lock` exists, use the installed `scripts/run.py` entry point.

**Run**

```bash
python scripts/run.py --repository /path/to/product-repository render
python scripts/run.py --repository /path/to/product-repository validate
python scripts/run.py --repository /path/to/product-repository check
```

**Expected**

- `render` updates tool-managed rendered instruction output from human-owned Policy input;
- `validate` verifies Policy structure/managed state; and
- `check` verifies the repository against the rendered/locked Policy expectations.

**Repository change**

`render` may update generated Policy output. `validate` and `check` are verification operations rather than authoring steps.

**What this means**

The first-use loop is complete. Continue to edit human-owned Policy input, render, validate, and check. During migration preparation, regenerate `adopt preview` after Policy edits instead of using the normal rendered instruction as a substitute for the migration preview.

The runner prefers the full SHA recorded by the repository's `.agent-policy.lock` rather than the skill's default stable pin. A malformed or mutable toolchain pin fails closed; the skill does not silently substitute the stable default.

## Trust and runtime details

The details below are important for reproducibility and supply-chain trust, but they are reference material rather than prerequisites for deciding the first dry-run command.

### Three immutable identities

Three full-SHA identities intentionally remain separate:

- **installer script revision** `f4457c90854db34c3ce8e1c381f67a4d7d5ea523` identifies the remotely executed installer;
- **skill source revision** `344aaf0b140e3c066363297012bb866efbc106e4` identifies the installed `skills/agent-policy/` subtree; and
- the **stable runtime revision** in the installed `runtime-manifest.json` identifies the canonical CLI runtime used by the skill.

`release/skill-installer.json` records the first two identities. The published command does not execute `policy`, a tag, or an abbreviated SHA.

A reviewed checkout remains available for repository-development installation:

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

That path installs the skill tree from the checkout under review. It is not necessarily byte-for-byte identical to the current published distribution unless the checkout matches the skill-source revision in `release/skill-installer.json`. Use the published remote command when reproducing the published distribution is the goal.

`runtime-manifest.json` pins the reviewed stable toolchain revision by full SHA and binds that revision's `requirements-runtime.lock` by SHA-256. Do not replace these identities with `policy`, a tag, or an abbreviated SHA.

Direct `agent-policy ...` examples in CLI/adoption reference documentation describe the canonical toolchain CLI. The normal consumer workflow uses `scripts/bootstrap.py` and `scripts/run.py` from the installed skill.

### Runtime-cache behavior

Runtime cache identity includes the full toolchain SHA, runtime-lock SHA-256, Python major/minor, and platform. A valid cache entry is reused without network access.

For the stable default, `runtime-manifest.json` already records the lock digest, so cache identity can be checked before network access. For another full SHA selected by a managed repository, an existing validated cache for the same revision/Python/platform can also be reused offline. Otherwise the skill fetches that revision's runtime lock once, computes its digest, and builds a new staged runtime.

## Review and commit

Fresh adoption, migration preparation, preview, finalization, rendering, and regeneration do not automatically create Git commits or push changes. Review the generated diff and commit it through the repository's normal review flow.

!!! note
    The same `agent-policy` skill is used before and after adoption. Before adoption its reviewed runtime manifest is the default trust seed; after adoption `.agent-policy.lock` becomes authoritative for the managed repository's toolchain revision.