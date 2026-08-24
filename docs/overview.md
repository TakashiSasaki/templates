# agent-policy

`agent-policy` is a policy toolchain for managing operating rules shared across multiple product repositories and multiple coding or general-purpose agents in a verifiable and reproducible form. The canonical development source is the `policy` branch of `TakashiSasaki/templates`.

## Start here

If your goal is to apply Policy to a product repository, you do not need to understand the Provider/toolchain internals first. The normal consumer path is:

1. **Install the single `agent-policy` skill** using the reviewed full-SHA installer documented in [Getting started](getting-started.md).
2. **Inspect an unmanaged repository** with `python scripts/bootstrap.py --repository /path/to/product-repository`. The dry run classifies it as `unmanaged-empty`, `unmanaged-existing`, `managed`, or `inconsistent` and selects the supported adoption path.
3. **Apply fresh adoption or prepare migration** only after reviewing that plan. Fresh adoption can use `--apply`; migration adoption preserves existing primary instructions and requires a separate explicit finalization step after preview.
4. **Operate the managed repository** through the same installed skill: `python scripts/run.py --repository . validate`, then `render`, then `check`.

Start with [Getting started](getting-started.md) for installation and adoption. Once `.agent-policy.lock` exists, use [Managed operation](managed-operation.md) for the normal validation/render/check loop. Use [Policy profiles](shared-policy/profiles.md) when you need to decide which shared rule sets a context should select.

Policy controls coding-agent operating rules. It **does not define the architecture or product requirements** of your Web application, CLI, service, library, or other artifact. Composition owns those artifact and capability semantics separately.

The sections below explain the Policy model and Provider internals when you need deeper architecture, provenance, or maintenance context.

## Purpose

- manage shared policy once at a central source;
- keep product-specific policy in each product repository;
- use `.agent-policy.yml` as the single semantic configuration entry point;
- compose shared and product-specific policy deterministically;
- generate and commit `AGENTS.md` and normal-operation skills;
- record input and output hashes and the complete toolchain commit SHA in `.agent-policy.lock`;
- detect inconsistencies among configuration, lock state, and generated outputs in CI;
- prepare adoption, preview the generated state, and perform explicit cutover without destructively replacing existing instructions; and
- use one installed `agent-policy` skill with a validated persistent full-SHA runtime before and after adoption.

## Three layers that must remain distinct

The word `policy` can refer to the repository branch, the canonical shared rules stored in that branch, or the policy that is actually effective in a consumer repository. These are separate layers.

1. **Provider / toolchain layer** — the entire `policy` branch of `TakashiSasaki/templates`. In addition to shared policy, it contains the `agent-policy` CLI, schemas, renderer templates, the single repository-facing skill, tests, release machinery, and maintainer documentation. The branch itself does not become effective in a consumer repository by being merged into it.
2. **Shared policy corpus layer** — the canonical shared rules under `policy/` and the selection sets under `profiles/`. This is the semantic source of truth for policy shared by multiple repositories. A rule does not become effective merely because it exists in the branch; the consumer configuration must select it.
3. **Consumer effective-policy layer** — the state in which a consumer repository's `.agent-policy.yml` selects shared profiles and repository-local policy and the toolchain composes and renders them into `AGENTS.md`, context outputs, normal-operation skills, and related artifacts. `.agent-policy.lock` pins the selected inputs, toolchain revision, and generated results. Repository work is governed by this consumer-side selected, composed, and generated state.

Adoption therefore does not inject or Git-merge the entire `policy` branch into a consumer. It **selects → composes → renders** shared rules and keeps the generated projections and lock state in the consumer repository. The unrelated histories of the branches remain separate.

Index-guided navigation preserves the same boundary by presenting [Provider and toolchain](provider/index.md), [Shared policy corpus](shared-policy/index.md), and [Applying policy to a consumer repository](consumer/index.md) as separate entry points.

## Structure of the `policy` branch

The `policy` history is unrelated to the `skill`, `site`, and `webapp` histories in the `templates` repository. It maintains the following components.

| Path | Responsibility |
|---|---|
| `policy/`, `profiles/` | Application-type-independent shared policy and selection sets |
| `src/agent_policy/` | Python CLI and adoption transaction implementation |
| `schemas/`, `templates/` | Schemas for consumer configuration and state, and generation templates |
| `skills/agent-policy/` | Single repository-facing skill for unmanaged adoption, managed command dispatch, immutable pin selection, and persistent runtime-cache management |
| `tests/` | Validation of the compiler, path safety, lock state, adoption, release identity, runtime distribution, and single-skill/cache boundary |
| `docs/` | Adoption, architecture, ADR, and publication material |

For an unmanaged repository, `skills/agent-policy/runtime-manifest.json` supplies the reviewed stable full-SHA trust seed and runtime-lock digest. After adoption, the same skill prefers the full SHA recorded by the consumer's `.agent-policy.lock`. A valid runtime cache entry can be reused without network access.

## Commands

```text
agent-policy adopt inspect
agent-policy adopt prepare
agent-policy adopt preview
agent-policy adopt finalize
agent-policy validate
agent-policy render
agent-policy check
```

- `adopt inspect`: classify repository state without mutation;
- `adopt prepare`: execute the state-derived fresh or migration preparation, using hidden initialization internally for fresh adoption when needed;
- `adopt preview`: regenerate and check staged migration output;
- `adopt finalize`: perform the separately authorized migration cutover;
- `validate`: validate configuration, references, rule IDs, path safety, and related constraints;
- `render`: compose shared and product-specific policy and update generated outputs and lock state; and
- `check`: verify read-only that configuration, inputs, lock state, and generated outputs agree.

The installed skill's generic bootstrap operation never exposes migration finalization. Finalization is a separate explicit managed command.

## Read next

- [Provider and toolchain](provider/index.md) — follow the design, maintenance, and release boundary of the `policy` branch and toolchain.
- [Shared policy corpus](shared-policy/index.md) — follow the canonical shared policy and profiles selected by consumers.
- [Applying policy to a consumer repository](consumer/index.md) — follow adoption, configuration, effective policy, and managed operation.
- [CLI reference](cli.md) — inspect the `agent-policy` command and subcommand contracts.
- [Architecture decisions](adr/) — browse the currently applicable ADRs with short descriptions.
- [Threat model](threat-model.md) — review the threats and trust boundaries defended by the toolchain.
