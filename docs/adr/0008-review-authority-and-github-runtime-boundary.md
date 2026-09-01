# ADR-0008: Separate review authority from GitHub runtime integration

- Status: Accepted
- Date: 2026-09-02

## Context

ADR-0005 established one canonical policy authority and requires generated instructions to remain projections rather than competing handwritten authorities. The current review implementation already follows part of that model: shared review semantics live in `policy/review/*.md`, `profiles/review.yml` selects the review-specific modules, and `.agent-policy.yml` composes the `review` context from shared core, security, review, and repository-local policy.

The current GitHub-facing projection, however, combines two different responsibilities. `.github/REVIEW_GUIDELINES.md` is a generated file, but its location makes it appear repository-authoritative even though its semantic content is derived from policy modules. Its renderer also combines semantic rules with a GitHub-specific JSON transport contract. At the same time `.github/workflows/*` contains actual GitHub Actions entry points whose placement under `.github/workflows/` is part of GitHub's discovery contract.

Recent automated-review design work also produced two useful review artifacts: a revised Review Guidelines document and a revised Canonical automated PR review prompt. They contain requirements that should improve the policy toolchain, but treating either document as a new handwritten authority would violate the single-authority model. Their statements must instead be classified by ownership and incorporated into the existing authority graph.

## Decision

Separate automated pull-request review into four responsibility layers:

1. **Semantic review policy** defines reviewer-independent obligations and admissibility requirements for findings.
2. **Review procedure** defines the operational sequence used to gather evidence and apply the selected review context.
3. **Platform adapter** defines provider-specific transport, serialization, event names, and inline-location rules.
4. **Platform runtime integration** contains files whose path or discovery semantics are imposed by the hosting platform.

No lower layer may redefine the semantics owned by a higher layer.

### Semantic review policy

Canonical review semantics remain atomic modules under `policy/review/*.md`, composed with reusable `policy/core/*` and `policy/security/*` modules through `profiles/review.yml` and the named `review` context.

Insights from the revised Review Guidelines are incorporated statement by statement. Existing canonical rules are reused when they already own the requirement. New modules are created only for genuinely missing, independently applicable semantics. The review corpus remains provider-neutral and must not encode GitHub event names, GitHub line-side vocabulary, model names, or transport serialization.

The revised Review Guidelines are therefore design input, not a second normative document.

### Review procedure

The operational procedure for an automated pull-request reviewer belongs in a dedicated review Skill source. It may prescribe operations such as resolving exact base/head identity, loading the repository-selected review context, inspecting the complete changed surface and relevant repository context, evaluating PR claims as evidence rather than authority, checking current evidence when material, revalidating the reviewed head before emission, and reporting limitations.

The procedure must reference semantic policy instead of copying definitions such as severity, compatibility, security impact, or admissibility thresholds.

The revised Canonical automated PR review prompt is classified as orchestration input for this layer. It may be retained as a canonical invocation/reference artifact of the review Skill, but it is not semantic policy.

### Platform adapter

GitHub-specific output requirements remain adapter concerns. These include GitHub review events, JSON response schema, confidence serialization, changed-file path/line anchors, `LEFT`/`RIGHT` side selection, and consistency constraints between analysis status and review event.

A GitHub adapter may consume the same review context as a provider-neutral review projection, but it must not reproduce the semantic rule corpus as an independent copy. Renderer tests must enforce this separation.

### Pull-request review versus merge authorization

Automated review and merge gating are separate operational contexts.

The review procedure determines whether changed code contains material, evidence-backed findings under the review policy. Merge-gate policy and procedure determine whether the exact current head is authorized to merge based on CI, independent review, unresolved threads, base freshness, mergeability, and other lifecycle evidence.

A pending or unavailable CI result is therefore not automatically a code-review defect. A change that weakens, disables, or invalidates required CI can still be a review finding when the changed code itself causes that regression.

Existing `policy/pull-request/*` and `skills/pr-merge-gate/*` continue to own merge-readiness and merge-authorization semantics and procedure.

### `.github/` runtime boundary

The `policy` branch does not use `.github/` as a general namespace for files merely because their consumer operates on GitHub.

Files belong under `.github/` only when GitHub itself assigns path-based discovery or runtime semantics to that location, for example GitHub Actions workflows and other GitHub-defined repository metadata.

Generated review instructions, semantic review projections, review prompts, renderer sources, and Skill sources must live outside `.github/` unless GitHub requires that exact path for discovery.

The existing `.github/REVIEW_GUIDELINES.md` is a transitional generated projection and will be removed from `.github/` during the reviewed self-hosting cutover after replacement projections and adapter separation exist. `.github/workflows/*` remains because those files are GitHub runtime entry points.

### Generated consumer projections

Generated review-facing artifacts are projections rather than authorities. The target layout may place provider-neutral review guidance and provider-specific adapter material under an agent-facing generated namespace such as `.agents/review/`, while generated Skills continue under `.agents/skills/`.

The exact output paths are configuration data and may evolve independently of semantic policy. Obsolete generated outputs must be removed only through the existing lock-bound, fail-closed generated-output lifecycle; modified or non-generated files are never deleted merely because configuration changed.

## Migration sequence

Implement the decision in separate reviewed changes:

1. record this authority and runtime-boundary decision;
2. perform a statement-level gap analysis of the revised Review Guidelines and add only missing atomic review semantics;
3. add a dedicated automated PR-review Skill and separate the GitHub transport renderer from semantic rule rendering;
4. promote the resulting reviewed toolchain revision through the existing stable-release process; and
5. update policy self-hosting configuration to the promoted full SHA, generate the new review projections, and remove the obsolete `.github/REVIEW_GUIDELINES.md` through the canonical generated-output lifecycle.

Reader-facing Site publication changes, if any, remain a separate cross-authority publication operation and must not be coupled implicitly to the Policy implementation change.

## Consequences

- Review semantics remain engine- and provider-neutral.
- The revised Review Guidelines contribute semantic coverage without becoming a competing authority.
- The revised Canonical automated PR review prompt becomes procedure/orchestration material rather than policy.
- GitHub JSON/event/location details remain adapter concerns.
- Automated review cannot silently absorb merge-gate responsibilities.
- `.github/` becomes a thin GitHub runtime/discovery boundary instead of a generic container for GitHub-related policy documents.
- Generated review artifacts remain inspectable while retaining explicit provenance and non-authoritative status.
- The migration can proceed without a configuration-schema version change because schema version 2 already separates contexts from output renderers and supports multiple named outputs.
