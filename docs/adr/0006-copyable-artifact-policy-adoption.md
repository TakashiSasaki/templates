# ADR-0006: Keep shared policy adoption opt-in for Composition-materialized artifacts

- Status: Accepted
- Date: 2026-08-08

## Context

ADR-0005 separated repository-maintainer policy from artifact contracts and deliberately left Policy adoption for consumer artifacts as a separate repository-maintenance decision.

The current `composition` authority materializes Agent Skill and Web application artifacts from recipes and reusable components. Those artifacts must remain independently usable without acquiring Policy configuration, runtime identity, or maintenance workflows merely because `policy` is maintained in the same `TakashiSasaki/templates` repository.

The artifact families also have different instruction needs. The Skill artifact may materialize consumer-facing `AGENTS.md` as a Composition `seed`, while a Web application artifact does not require an agent-instruction entry point merely to satisfy its artifact contract.

Automatically enrolling Composition output in the shared Policy toolchain would add Policy configuration, release identity, generated outputs, and maintenance workflow semantics before the consumer repository owner has chosen that operating model. It would also blur artifact semantics with coding-agent operating policy and create an implicit dependency between two independent authorities.

## Decision

Composition-materialized artifacts are **not pre-enrolled** in the shared Policy toolchain.

A Composition recipe or component must not add `.agent-policy.yml`, `.agent-policy.lock`, Policy-generated maintenance workflows, or other Policy management state solely because Policy exists in the source repository. Composer must not invoke `agent-policy` as part of materialization, update, upgrade, or recovery.

After Composition materialization, the owner of the resulting concrete repository may explicitly adopt the shared Policy toolchain as a separate repository-maintenance decision. That adoption uses the normal reviewed full-SHA Policy bootstrap/adoption path and must preserve the concrete artifact's semantic requirements.

Artifact-level instructions remain governed by the artifact ownership contract until an explicit ownership handoff occurs. In particular:

- a Skill artifact may materialize consumer-facing `AGENTS.md` as a Composition `seed`;
- after initial materialization that seed is consumer-owned according to the Composition seed contract;
- a later explicit Policy adoption may inspect and migrate that consumer-owned `AGENTS.md` into the Policy-generated steady-state instruction projection;
- a Web application artifact is not required to add `AGENTS.md` merely to participate in the Web application contract; and
- `.agent-policy.yml`, `.agent-policy.lock`, `.agent-policy/**`, generated Policy instructions, review adapters, and Policy workflows are not inherited from Composition by default.

The canonical cross-authority ownership handoff and collision rules are defined by the Site-owned [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/). This ADR does not create a separate Policy-side copy of that contract.

## Rationale

This keeps three ownership layers distinct:

1. **shared Policy** defines application-neutral coding-agent operating semantics;
2. **concrete repository Policy state** governs maintenance of a repository that explicitly adopts Policy; and
3. **Composition artifact contracts** define what a materialized Skill or Web application repository contains and how Composition-owned lifecycle state is managed.

Opt-in adoption avoids imposing Policy management infrastructure on consumers that only need a Composition artifact. It also preserves source-time composition and consumer self-containment: committed artifact instructions and contracts remain usable even when the Policy toolchain is not fetched or executed.

The decision does not prohibit a Composition-produced repository from using Policy. It only makes that adoption an explicit post-materialization operation rather than an implicit property of a recipe or component graph.

## Consequences

- Composition recipes and components must remain semantically independent of Policy adoption.
- Policy must not be represented as `capability.agent-policy` or an equivalent Composition component merely to automate repository enrollment.
- Policy does not interpret `.template-composition/**` as Policy state and does not rewrite Composition lock, transaction, staging, or ownership metadata.
- Consumer documentation may explain how to opt in after Composition materialization, but Composer performs no automatic Policy adoption.
- Full-SHA Policy adoption remains available to any concrete repository after artifact creation.
- Reverse ownership transfer from an already Policy-generated destination to newly selected Composition material remains fail-closed unless an explicit migration contract is introduced.

## Verification

The decision is satisfied when Composition-produced repositories remain independently valid without `.agent-policy.yml` or `.agent-policy.lock`, Policy operations leave `.template-composition/**` unchanged, Composition artifact selection does not become a Policy profile concern, and post-materialization Policy adoption remains a separate explicit operation.
