# Policy concepts for first-time readers

This page explains a small set of Policy terms whose ordinary software meanings are broader than their meanings in this repository. The canonical term definitions remain in `docs/glossary.yml`; the architecture, CLI, adoption, and release documents remain authoritative for exact behavior.

You do not need to memorize these terms before the first dry run. Use this page when two nearby operations or states look interchangeable but are not.

## Adoption is the user-facing onboarding operation

**Policy adoption** is the first-time transition by which an unmanaged repository enters Policy management. The supported user-facing path starts with read-only inspection and derives the safe strategy from repository state.

| Repository inspection state | Adoption strategy | Meaning |
| --- | --- | --- |
| `unmanaged-empty` | **fresh adoption** | No handwritten agent instructions need migration. Policy may use the hidden `init` primitive internally and can create normal managed state directly when mutation is explicitly applied. |
| `unmanaged-existing` | **migration adoption** | Existing instructions remain authoritative during preparation. Policy creates staged state and a preview first; final cutover is a separate explicit `adopt finalize --apply` operation after semantic review. |
| `managed` | no first-time adoption | Use normal managed operations instead. |
| `inconsistent` | no automatic adoption | Repair the inconsistent Policy state before mutation. |

Installing the `agent-policy` skill is not adoption. Installation provides the repository-facing tool entry point; adoption changes the target repository.

`init` is also not a competing onboarding mode. It is an internal fresh-adoption primitive retained for the pinned bootstrap path and implementation tests. New callers use adoption.

## Fresh adoption and migration adoption are not interchangeable

Fresh adoption is safe only for `unmanaged-empty`. It does not need to preserve a handwritten primary instruction through a staged migration transaction.

Migration adoption is the safety path for `unmanaged-existing`. Preparation and preview deliberately do **not** replace the existing primary instruction. Finalization occurs only after the generated Policy projection has been reviewed against the intended handwritten semantics.

The distinction is about existing authority, not about repository age, project size, or whether the repository has application code.

## Managed does not mean validated

A **managed repository** is an inspection classification based on the canonical `.agent-policy.yml` path and Policy management state. It does not assert that the configuration, referenced policy, lock, or generated outputs currently pass validation/checking.

Treat these as different questions:

- **managed?** — Has this repository entered the Policy management model?
- **valid?** — Is the semantic Policy configuration and referenced input structure acceptable?
- **in sync?** — Do the lock and generated outputs agree with the current accepted inputs?

## Render, validate, and check have different contracts

The normal managed loop uses three distinct operations:

| Operation | Mutation | Question answered |
| --- | --- | --- |
| **Policy render** | yes | What generated outputs and `.agent-policy.lock` should result from the current accepted Policy inputs? |
| **Policy validate** | no | Is `.agent-policy.yml` plus its referenced Policy input structurally and semantically valid, including schema, profiles, rule IDs, overrides, and path safety? |
| **Policy check** | no | Do the current configuration, inputs, lock state, and generated outputs agree, or has regeneration/manual modification made them stale? |

A successful `validate` is therefore not a substitute for `check`, and `check` is not a rendering command. Change human-owned Policy input, run `render`, then use `validate` and `check` according to the workflow being verified.

During migration preparation, `adopt preview` has its own staged-state contract and is not replaced by an ordinary `render` merely because both produce generated content.

## Prepared and finalized are migration-adoption states

`prepared` means a migration adoption has staged configuration/state and a reviewable generated preview while the existing primary instructions remain authoritative.

`finalized` means the explicit migration cutover transaction completed and the normal Policy-generated instruction path is now active. The word does not mean that every unrelated project task, CI job, or product release is complete.

Fresh adoption does not pass through this staged `prepared -> finalized` migration state machine.

## Stable release is not the policy branch tip

The mutable `policy` branch is the development source. The **Stable release** is the separately selected executable Policy toolchain revision recorded by the stable release descriptor. It may intentionally lag the branch.

Likewise, installer-script revision, installed skill-source revision, and stable runtime revision are distinct immutable identities. Avoid collapsing them into an unqualified phrase such as “the current version” when exact identity matters.

## Words that should usually be qualified

Repository-wide prose is easier to read when broad words name their scope explicitly:

- prefer **Policy managed repository** when Composition-managed state could also be discussed;
- prefer **Policy stable release** or **stable Policy toolchain revision** rather than an unqualified “release” or “runtime revision”;
- prefer **Policy validation** and **Policy check** when another provider's validators are also in scope;
- distinguish the **Policy lock** (`.agent-policy.lock`) from the Composition lock and from an operating-system/process lock.

The goal is not to ban ordinary words. Qualify them where a reader could reasonably select the wrong authority, operation, or completion state.

## Where to go next

- [Getting started](getting-started.md) — first dry run and the state-derived adoption path.
- [Repository adoption](adoption.md) — detailed migration preparation, preview, and finalization safety.
- [CLI reference](cli.md) — exact command behavior for `adopt`, `render`, `validate`, and `check`.
- [Managed repository operation](managed-operation.md) — normal operation after adoption.
- [Configuration](configuration.md) — Policy context, renderer, profile, repository-local policy, and override semantics.
- [Release lifecycle](release-lifecycle.md) — immutable stable-toolchain and installer identities.
