# ADR-0008: Separate review authority from GitHub runtime integration

- Status: Accepted
- Date: 2026-09-02

## Context

ADR-0005 established one canonical policy authority and requires generated instructions to remain projections rather than competing handwritten authorities. The current review implementation already follows part of that model: shared review semantics live in `policy/review/*.md`, `profiles/review.yml` selects the review-specific modules, and `.agent-policy.yml` composes review contexts from shared profiles and repository-local policy.

The current GitHub-facing projection, however, combines two different responsibilities. `.github/REVIEW_GUIDELINES.md` is a generated file, but its location makes it appear repository-authoritative even though its semantic content is derived from policy modules. Its renderer also combines semantic rules with a GitHub-specific JSON transport contract. At the same time `.github/workflows/*` contains actual GitHub Actions entry points whose placement under `.github/workflows/` is part of GitHub's discovery contract.

Recent automated-review design work also produced revised Review Guidelines and a revised Canonical automated PR review prompt. The original conversational documents are not immutable repository inputs, so this migration freezes the complete accepted statement-level baseline in `docs/review-guidance-inputs.md`. Follow-up implementation may classify only that frozen baseline unless a reviewed change explicitly amends it.

## Decision

Separate automated pull-request review into four responsibility layers:

1. **Semantic review policy** defines reviewer-independent obligations and admissibility requirements for findings.
2. **Review procedure** defines the operational sequence used to gather evidence and apply the selected review context.
3. **Platform adapter** defines provider-specific transport, serialization, event names, and inline-location rules.
4. **Platform runtime integration** contains files whose path or discovery semantics are imposed by the hosting platform.

No lower layer may redefine the semantics owned by a higher layer, and each layer has exactly one source authority for a given requirement.

### Semantic review policy

Canonical review semantics remain atomic modules under `policy/review/*.md`, composed with reusable `policy/core/*` and `policy/security/*` modules through a configured review context.

The frozen Review Guidelines inputs in `docs/review-guidance-inputs.md` are classified statement by statement. Existing canonical rules are reused when they already own a requirement. New modules are created only for genuinely missing, independently applicable semantics. The review corpus remains provider-neutral and must not encode GitHub event names, GitHub line-side vocabulary, model names, or transport serialization.

The frozen guidance inventory is therefore migration evidence, not a second normative policy document.

### Review procedure

The dedicated automated pull-request review Skill is the **sole procedural authority** for review execution. It owns the ordered operations required to establish a review: exact target identity, trusted policy selection, complete changed-surface inspection, relevant-context discovery, evidence handling, head revalidation, semantic-policy application, adapter handoff, and the boundary that stops review before merge authorization.

The Skill must reference semantic policy instead of copying definitions such as severity, compatibility, security impact, or admissibility thresholds.

The previously revised Canonical automated PR review prompt is not a second procedure authority. Its reusable retained form is a thin, explicitly non-normative invocation surface that supplies task parameters and directs the agent to execute the installed `pr-review` Skill. Procedural knowledge extracted from the revised prompt is incorporated into the Skill itself. If the prompt and Skill ever appear to disagree, the Skill governs and the prompt must be regenerated or corrected.

### Trusted policy root

Reviewed content must not be allowed to choose or weaken the policy used to judge itself.

By default, a pull-request review uses the exact current **base revision captured at review start** as its trusted repository-policy root. The reviewer reads `.agent-policy.yml`, repository-local policy inputs, generated review projections, and their recorded provenance from that trusted base snapshot. Changes on the proposed head to policy configuration, policy modules, generated review instructions, adapter configuration, or related authority material are review data, not active instructions for that same review.

An invocation may instead supply an explicit out-of-band trusted policy revision when the repository's review contract authorizes such a root. That revision must be immutable, recorded in the review evidence, and selected by the caller rather than by reviewed head content. There is no implicit head-side rebaseline.

If the pull-request base revision changes while the review is in progress, evidence collected under the prior trusted base is stale until the reviewer re-resolves the authority root and re-evaluates affected analysis.

### Review output binding

Schema version 2 keeps Skill enablement independent from output selection, so a Skill must not guess a context by the literal name `review` or choose arbitrarily among multiple outputs.

The review invocation therefore identifies two explicit repository-relative output paths from the **trusted policy root**:

- the provider-neutral semantic review projection; and
- the provider/platform adapter projection required for the requested output surface.

Before reviewing, the Skill verifies from the trusted `.agent-policy.yml` that both outputs are enabled, that each configured path matches the supplied path, and that both outputs reference the same context. If the binding is absent, ambiguous, inconsistent, or cannot be validated, the reviewer fails closed or reports the resulting limitation according to the available trusted adapter; it does not infer a context from naming conventions.

This invocation-level binding is sufficient for the current design and does not require a configuration-schema transition. A future machine-declared Skill-to-output binding would be a separate trust-contract change and would require its own architecture decision.

### Platform adapter

GitHub-specific output requirements remain adapter concerns. These include GitHub review events, JSON response schema, confidence serialization, changed-file path/line anchors, `LEFT`/`RIGHT` side selection, and consistency constraints between analysis status and review event.

A GitHub adapter is bound to the same semantic context as the provider-neutral review projection, but it must not reproduce the semantic rule corpus as an independent copy. Renderer tests must enforce this separation.

### Pull-request review versus merge authorization

Automated review and merge gating are separate operational contexts.

The review procedure determines whether changed code contains material, evidence-backed findings under the trusted review policy. Merge-gate policy and procedure determine whether the exact current head is authorized to merge based on CI, independent review, unresolved threads, base freshness, mergeability, and other lifecycle evidence.

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

1. record this authority and runtime-boundary decision and freeze the accepted design-input inventory;
2. perform a statement-level disposition of `docs/review-guidance-inputs.md` and add only genuinely missing atomic review semantics;
3. add the dedicated automated PR-review Skill as the sole procedural authority, retain only a thin non-normative invocation prompt, and separate the GitHub transport renderer from semantic rule rendering;
4. promote the resulting reviewed toolchain revision through the existing stable-release process; and
5. update policy self-hosting configuration to the promoted full SHA, generate explicitly bound review projections, and remove the obsolete `.github/REVIEW_GUIDELINES.md` through the canonical generated-output lifecycle.

Reader-facing Site publication changes, if any, remain a separate cross-authority publication operation and must not be coupled implicitly to the Policy implementation change.

## Consequences

- Review semantics remain engine- and provider-neutral.
- The accepted insights from the two revised review documents are reproducibly frozen without making the documents competing authorities.
- The `pr-review` Skill is the only procedural authority; the canonical invocation prompt is thin and non-normative.
- Reviewed head content cannot silently change the policy used to evaluate itself.
- Review output paths are explicit invocation inputs and are verified to bind to one trusted context rather than inferred from names.
- GitHub JSON/event/location details remain adapter concerns.
- Automated review cannot silently absorb merge-gate responsibilities.
- `.github/` becomes a thin GitHub runtime/discovery boundary instead of a generic container for GitHub-related policy documents.
- Generated review artifacts remain inspectable while retaining explicit provenance and non-authoritative status.
- The current migration can proceed without a configuration-schema version change because the missing Skill/output association is supplied and validated as explicit invocation data rather than inferred configuration.
