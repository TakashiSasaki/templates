# agent-policy

`agent-policy` is a policy toolchain for managing operating rules shared across multiple product repositories and multiple coding or general-purpose agents in a verifiable and reproducible form. The canonical development source is the `policy` branch of `TakashiSasaki/templates`.

## Purpose

- manage shared policy once at a central source;
- keep product-specific policy in each product repository;
- use `.agent-policy.yml` as the single semantic configuration entry point;
- compose shared and product-specific policy deterministically;
- generate and commit `AGENTS.md` and normal-operation skills;
- record input and output hashes and the complete toolchain commit SHA in `.agent-policy.lock`;
- detect inconsistencies among configuration, lock state, and generated outputs in CI; and
- prepare adoption, preview the generated state, and perform explicit cutover without destructively replacing existing instructions.

## Three layers that must remain distinct

The word `policy` can refer to the repository branch, the canonical shared rules stored in that branch, or the policy that is actually effective in a consumer repository. These are separate layers.

1. **Provider / toolchain layer** — the entire `policy` branch of `TakashiSasaki/templates`. In addition to shared policy, it contains the `agent-policy` CLI, schemas, renderer templates, bootstrap support, tests, release machinery, and maintainer documentation. The branch itself does not become effective in a consumer repository by being merged into it.
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
| `skills/` | Normal-operation skills and the integrated `bootstrap-agent-policy` trust seed |
| `tests/` | Validation of the compiler, path safety, lock state, adoption, and bootstrap boundary |
| `docs/` | Adoption, architecture, ADR, and publication material |

The bootstrap skill is under `skills/bootstrap-agent-policy/`. Its manifest pins a full commit SHA of `TakashiSasaki/templates` before invoking the CLI, so it never executes the mutable `policy` branch tip directly. After initialization or adoption finalization, control transfers to the product repository's `.agent-policy.yml`, `.agent-policy.lock`, generated instructions and skills, and CI.

## Commands

```text
agent-policy init
agent-policy adopt inspect
agent-policy adopt prepare
agent-policy adopt preview
agent-policy adopt finalize
agent-policy validate
agent-policy render
agent-policy check
```

- `init`: initialize an unmanaged repository that has no conflicting existing instructions;
- `adopt`: inspect, prepare, preview, and explicitly cut over while preserving existing instructions;
- `validate`: validate configuration, references, rule IDs, path safety, and related constraints;
- `render`: compose shared and product-specific policy and update generated outputs and lock state; and
- `check`: verify read-only that configuration, inputs, lock state, and generated outputs agree.

## Read next

- [Provider and toolchain](provider/index.md) — follow the design, maintenance, and release boundary of the `policy` branch and toolchain.
- [Shared policy corpus](shared-policy/index.md) — follow the canonical shared policy and profiles selected by consumers.
- [Applying policy to a consumer repository](consumer/index.md) — follow adoption, configuration, effective policy, and managed operation.
- [CLI reference](cli.md) — inspect the `agent-policy` command and subcommand contracts.
- [Architecture decisions](adr/) — browse the currently applicable ADRs with short descriptions.
- [Threat model](threat-model.md) — review the threats and trust boundaries defended by the toolchain.
