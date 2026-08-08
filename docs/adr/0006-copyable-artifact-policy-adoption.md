# ADR-0006: Keep shared policy adoption opt-in for copyable artifacts

- Status: Accepted
- Date: 2026-08-08

## Context

ADR-0005 separated repository-maintainer policy from artifact contracts and deliberately left policy adoption inside copyable consumer artifacts as a separate distribution-contract decision.

The `skill` and `webapp` branches each publish a byte-preserving `template/` distribution that is copied into a new repository or artifact root. Those distributions must remain independently usable after copying and must not inherit source-maintainer concerns merely because their source branch consumes the shared policy toolchain.

The two distributions also have different artifact-level instruction needs. A Skill distribution already contains consumer-facing `AGENTS.md` instructions that describe the Skill artifact contract. A Web application distribution does not require an agent-instruction entry point merely to satisfy the Web application contract.

Pre-enrolling either distribution in the shared policy toolchain would add policy configuration, release identity, generated outputs, and maintenance workflow semantics to every copied artifact before its owner has chosen that operating model. It would also risk making repository operating policy appear to be part of the artifact contract itself.

## Decision

Copyable template distributions are **not pre-enrolled** in the shared policy toolchain.

A copyable distribution must not include `.agent-policy.yml`, `.agent-policy.lock`, generated shared-policy maintenance workflows, or repository-local shared-policy inputs solely because its source branch uses them.

After a template is copied, the owner of the resulting concrete repository may explicitly adopt the shared policy toolchain as a separate repository-maintenance decision. That adoption must use the normal reviewed full-SHA bootstrap or adoption path and must preserve the concrete artifact's existing semantic requirements.

Artifact-level instructions remain owned by the artifact contract unless and until an explicit repository-policy adoption converts their operating-policy portions into generated projections. In particular:

- a Skill template may retain consumer-facing `AGENTS.md` when its contents define how to develop and validate the Skill artifact;
- a Web application template is not required to add `AGENTS.md` merely to participate in the Web application contract; and
- source-maintainer `.agent-policy.yml`, lock files, generated instructions, review adapters, and policy workflows do not flow into `template/` by inheritance.

A future template may choose pre-enrollment only through a new reviewed distribution-contract decision that demonstrates why the additional toolchain identity and maintenance surface belong in that artifact's default distribution.

## Rationale

This keeps three ownership layers distinct:

1. **shared policy** defines application-neutral operating semantics;
2. **source repository policy** governs maintenance of the template product itself; and
3. **artifact contracts** define what a copied Skill or Web application repository must contain and how that artifact behaves.

Opt-in adoption avoids imposing repository-management infrastructure on consumers that only need the artifact template. It also keeps copied artifacts self-contained at the semantic level: committed artifact instructions and contracts remain usable even when the shared policy toolchain is not fetched or executed.

The decision does not prohibit a concrete repository from using shared policy. It only makes that adoption an explicit post-copy operation rather than an implicit property of the template distribution.

## Consequences

- `skill/template/` must keep source-maintainer policy configuration and generated shared-policy maintenance surfaces out of its closed distribution inventory.
- `webapp/template/` must keep the same separation and must not gain coding-agent policy merely because the `webapp` source branch consumes shared policy.
- Distribution validators should reject accidental leakage of source-maintainer policy surfaces into copyable artifacts.
- Consumer documentation may explain how to opt in after copying, but the copy operation itself remains byte-preserving and performs no automatic policy adoption.
- Full-SHA policy adoption remains available to any concrete repository after artifact creation.

## Verification

The decision is satisfied when each copyable distribution remains independently valid without `.agent-policy.yml` or `.agent-policy.lock`, source-maintainer policy surfaces are explicitly excluded from the distribution boundary, and post-copy policy adoption remains a separate explicit operation rather than an automatic transformation.
