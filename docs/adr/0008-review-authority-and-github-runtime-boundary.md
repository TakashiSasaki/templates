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

The dedicated automated pull-request review Skill is the **sole procedural authority** for review execution. It owns the ordered operations required to establish a review: exact target and comparison identity, trusted authority selection, complete changed-surface inspection, relevant-context discovery, evidence handling, target revalidation, semantic-policy application, adapter handoff, and the boundary that stops review before merge authorization.

At review start the procedure records three immutable revision identities:

- the exact current target/base tip, which is the default trusted repository-policy root;
- the exact proposed head; and
- the exact merge-base/common-ancestor revision between that base tip and proposed head, which is the comparison base for the PR-introduced changed surface.

The complete PR changed surface is defined as the repository change from the recorded merge-base to the recorded proposed head. A tip-to-tip base→head comparison is not substituted for that surface. Surrounding repository context may be inspected beyond the changed surface when the semantic review requires it, but findings still follow the semantic policy's causality and changed-location requirements.

The Skill must reference semantic policy instead of copying definitions such as severity, compatibility, security impact, or admissibility thresholds.

The previously revised Canonical automated PR review prompt is not a second procedure authority. Its reusable retained form is a thin, explicitly non-normative invocation surface that supplies task and trust-binding parameters and directs the agent to execute a verified `pr-review` Skill. Procedural knowledge extracted from the revised prompt is incorporated into the Skill itself. If the prompt and Skill ever appear to disagree, the verified Skill governs and the prompt must be regenerated or corrected.

### Trusted review authority root

Reviewed content must not be allowed to choose or weaken either the semantic policy or the procedural code used to judge itself.

By default, a pull-request review uses the exact current **base tip captured at review start** as its trusted repository-policy root. The reviewer reads `.agent-policy.yml`, repository-local policy inputs, generated review projections, and their recorded provenance from that trusted base snapshot. Changes on the proposed head to policy configuration, policy modules, generated review instructions, adapter configuration, generated Skills, or related authority material are review data, not active instructions for that same review.

The procedural Skill is resolved independently of the proposed head. Unless the caller supplies a different immutable trusted procedure revision, the reviewer reads the full-SHA `toolchain.revision` from `.agent-policy.yml` at the trusted repository-policy root and resolves `pr-review` only from that exact toolchain revision. The loader must verify the Skill source/generated provenance against that immutable revision before executing it. A repository-local or generated `pr-review` copy from the proposed head is never executed merely because it is newer or locally discoverable.

A caller may instead supply an explicit out-of-band trusted repository-policy revision, trusted procedure/toolchain revision, or both when the repository's review contract authorizes those roots. Each supplied revision must be immutable, recorded in the review evidence, and selected by the caller rather than by reviewed head content. There is no implicit head-side rebaseline.

If the trusted base does not select a toolchain revision containing the required `pr-review` Skill and no authorized out-of-band trusted procedure revision is supplied, the automated review procedure is unavailable and must fail closed rather than falling back to a head-side Skill.

Immediately before final serialization, the procedure re-resolves the base tip, proposed head, and their merge-base. If any of the three differs from the identities used by the current analysis, the review is stale: it replaces the recorded identities, recomputes the merge-base→head changed surface, refreshes affected evidence and semantic analysis, and repeats the final three-revision observation. A changed base tip also requires re-resolving the default trusted repository-policy root and its default toolchain/procedure binding. Serialization is reached only when an immediately pre-serialization observation reproduces all three fully analyzed revision identities.

### Review output binding

Schema version 2 keeps Skill enablement independent from output selection, so a Skill must not guess a context by the literal name `review` or choose arbitrarily among multiple outputs.

The review invocation therefore identifies two explicit repository-relative output paths from the **trusted repository-policy root**:

- the provider-neutral semantic review projection; and
- the provider/platform adapter projection required for the requested output surface.

Before reviewing, the verified Skill checks from the trusted `.agent-policy.yml` that both outputs are enabled, that each configured path matches the supplied path, and that both outputs reference the same context. It also validates each output's renderer role rather than accepting any two same-context outputs. If the binding is absent, ambiguous, inconsistent, unsupported, or cannot be validated, the reviewer fails closed or reports the resulting limitation according to trusted adapter behavior that remains available; it does not infer a context or renderer role from naming conventions.

This invocation-level binding is sufficient for the current design and does not require a configuration-schema transition. A future machine-declared Skill-to-output binding would be a separate trust-contract change and would require its own architecture decision.

### Platform adapter

GitHub-specific output requirements remain adapter concerns. These include GitHub review events, JSON response schema, confidence serialization, changed-file path/line anchors, `LEFT`/`RIGHT` side selection, and consistency constraints between analysis status and review event.

A GitHub adapter is bound to the same semantic context as the provider-neutral review projection, but it must not reproduce the semantic rule corpus as an independent copy. Finding selection and admissibility remain semantic-policy concerns; an adapter serializes the semantic result and must not add a confidence threshold or otherwise filter that result. Renderer tests must enforce this separation.

### Pull-request review versus merge authorization

Automated review and merge gating are separate operational contexts.

The review procedure determines whether changed code contains material, evidence-backed findings under the trusted review policy. Merge-gate policy and procedure determine whether the exact current head is authorized to merge based on CI, independent review, unresolved threads, base freshness, mergeability, and other lifecycle evidence.

The review procedure collects and revision-binds CI or remote evidence when material, but the selected semantic review policy determines how that evidence affects a finding or limitation. Procedure and adapter layers do not independently classify pending, missing, successful, failed, stale, or inaccessible CI as either a defect or a clean result.

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
3. add the dedicated automated PR-review Skill as the sole procedural authority, retain only a thin non-normative invocation prompt, and introduce a transport-only GitHub adapter without silently changing the meaning of an existing combined renderer;
4. promote the resulting reviewed toolchain revision through the existing stable-release process; and
5. update policy self-hosting configuration to the promoted full SHA, generate explicitly bound review projections and Skill bytes from that trusted toolchain, and remove the obsolete `.github/REVIEW_GUIDELINES.md` through the canonical generated-output lifecycle.

Reader-facing Site publication changes, if any, remain a separate cross-authority publication operation and must not be coupled implicitly to the Policy implementation change.

## Consequences

- Review semantics remain engine- and provider-neutral.
- The accepted insights from the two revised review documents are reproducibly frozen without making the documents competing authorities.
- The verified `pr-review` Skill is the only procedural authority; the canonical invocation prompt is thin and non-normative.
- Reviewed head content cannot silently change either the semantic policy or the procedural Skill used to evaluate itself.
- The base tip is the default trusted policy root, while the merge-base independently defines the PR-introduced changed surface.
- The default procedure revision is derived from the trusted base's immutable toolchain pin, while an authorized caller may supply an explicit immutable out-of-band procedure revision when needed.
- Review output paths are explicit invocation inputs and are verified to bind to one trusted context with the expected renderer roles rather than inferred from names.
- GitHub JSON/event/location details remain adapter concerns; finding selection remains semantic policy.
- Automated review cannot silently absorb merge-gate responsibilities.
- `.github/` becomes a thin GitHub runtime/discovery boundary instead of a generic container for GitHub-related policy documents.
- Generated review artifacts remain inspectable while retaining explicit provenance and non-authoritative status.
- The current migration can proceed without a configuration-schema version change because the missing Skill/output association is supplied and validated as explicit invocation data rather than inferred configuration.
