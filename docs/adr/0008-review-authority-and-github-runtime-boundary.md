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

At review start the procedure records:

- the exact current target/base tip, which is the default trusted repository-policy root;
- the exact proposed head; and
- the complete set of best common ancestors between that base tip and proposed head.

The procedure requires that best-common-ancestor set to contain **exactly one** revision. That unique revision is the merge-base/comparison base for the PR-introduced changed surface. If the histories are unrelated or have multiple best merge bases, including a criss-cross history, the procedure fails closed rather than selecting an arbitrary merge base or synthesizing an unspecified virtual base.

The complete PR changed surface is defined as the repository change from that unique recorded merge-base to the recorded proposed head. A tip-to-tip base→head comparison is not substituted for that surface. Surrounding repository context may be inspected beyond the changed surface when the semantic review requires it, but findings still follow the semantic policy's causality and changed-location requirements.

The Skill must reference semantic policy instead of copying definitions such as severity, compatibility, security impact, or admissibility thresholds.

The previously revised Canonical automated PR review prompt is not a second procedure authority. Its reusable retained form is a thin, explicitly non-normative invocation surface that supplies task and trust-binding parameters and directs the agent to execute a verified `pr-review` Skill. Procedural knowledge extracted from the revised prompt is incorporated into the Skill itself. If the prompt and Skill ever appear to disagree, the verified Skill governs and the prompt must be regenerated or corrected.

### Trusted review authority root

Reviewed content must not be allowed to choose or weaken either the semantic policy or the procedural code used to judge itself.

The exact current **base tip captured before selecting any override** is the default prior trust anchor for the review. By default it is also the active trusted repository-policy root. A caller may request an immutable out-of-band repository-policy root or procedure/toolchain revision only when that override mechanism is explicitly authorized by this prior trust anchor. The candidate override revision must never authorize itself, and proposed-head content must never authorize an override. If the prior base does not authorize the requested override mechanism, the review fails closed rather than consulting the candidate override for permission. A future independently administered trust-anchor mechanism would require its own explicit repository contract; it is not inferred here.

When an authorized repository-policy override is selected, that immutable revision becomes the active trusted repository-policy root. The reviewer reads `.agent-policy.yml`, `.agent-policy.lock`, repository-local policy inputs, generated review projections, and their recorded provenance only from that active trusted snapshot. Changes on the proposed head to policy configuration, lock state, policy modules, generated review instructions, adapter configuration, generated Skills, or related authority material are review data, not active instructions for that same review.

For a repository-bound review, the active trusted root must contain a valid `.agent-policy.yml` and `.agent-policy.lock`. The lock is the authoritative managed-runtime pin: its `toolchain.repository` and full-SHA `toolchain.revision` must be valid and must agree exactly with the corresponding configuration values. A missing or malformed lock, a configuration/lock disagreement, an input-digest mismatch, or other lock-integrity failure causes the review procedure to fail closed rather than selecting the configuration pin independently.

The procedural Skill is resolved independently of the proposed head. Unless the caller supplies a separately authorized immutable trusted procedure/toolchain revision, the reviewer derives the procedure revision from the **active trusted repository-policy root's validated lock pin**, not from the original base snapshot and not from `.agent-policy.yml` alone. The active trusted configuration must also list `pr-review` in `skills.enabled`; a toolchain merely containing that Skill does not authorize its execution. The loader resolves `pr-review` only from the validated full-SHA toolchain revision and verifies the Skill source/generated provenance against that immutable revision before executing it. A repository-local or generated `pr-review` copy from the proposed head is never executed merely because it is newer or locally discoverable.

An explicitly authorized out-of-band trusted procedure/toolchain revision is a separate procedure-selection authority supplied by the caller after authorization has been established from the prior base trust anchor. Such an override may be used even when the active repository configuration does not enable `pr-review`. The override revision must be immutable, recorded in the review evidence, and selected independently of reviewed head content. An authorized repository-policy-root override without a separate procedure override does **not** bypass repository procedure selection: default procedure availability and pinning are evaluated against that selected active repository-policy root.

If the active trusted repository-policy root does not validly select and enable a toolchain revision containing `pr-review`, and no authorized out-of-band trusted procedure revision is supplied, the automated review procedure is unavailable and must fail closed rather than falling back to a head-side Skill.

Immediately before final serialization, the procedure re-resolves the base tip, proposed head, and complete set of best common ancestors. The set must still contain exactly one merge-base. If the base, head, unique merge-base, or merge-base cardinality differs from the identities used by the current analysis, the review is stale: it replaces the recorded target/comparison identities, recomputes the merge-base→head changed surface, refreshes affected evidence and semantic analysis, and repeats the final observation. When the repository-policy root is the default base tip, a changed base requires re-establishing the trust bootstrap from the new base, including configuration/lock integrity, Skill enablement, procedure pin, output bindings, and generated projections. If that bootstrap resolves a procedure revision different from the Skill currently executing, the current run must stop and the review must restart under the newly verified Skill before any further analysis or serialization. The old Skill cannot hand-wave or emulate requirements owned by the new procedure revision. An explicit out-of-band repository-policy root remains fixed unless the caller explicitly replaces it, but target/comparison identities and affected evidence must still be refreshed. Serialization is reached only when an immediately pre-serialization observation reproduces the fully analyzed base, head, and unique merge-base identities.

### Review output binding

Schema version 2 keeps Skill enablement independent from output selection, so a Skill must not guess a context by the literal name `review` or choose arbitrarily among multiple outputs.

The review invocation therefore identifies two explicit repository-relative output paths from the **active trusted repository-policy root**:

- the provider-neutral semantic review projection; and
- the provider/platform adapter projection required for the requested output surface.

Before reviewing, the verified Skill checks from the active trusted `.agent-policy.yml` that both outputs are enabled, that each configured path matches the supplied path, and that both outputs reference the same context. It also validates each output's renderer role rather than accepting any two same-context outputs. If the binding is absent, ambiguous, inconsistent, unsupported, or cannot be validated, the reviewer fails closed or reports the resulting limitation according to trusted adapter behavior that remains available; it does not infer a context or renderer role from naming conventions.

Checked-in generated projection bytes are never trusted merely because their paths and renderer metadata match. Before either projection is consumed, the procedure verifies the active trusted snapshot with the validated lock. Configured input and output digests must match the lock, and deterministic check/regeneration must execute the **toolchain revision pinned by that active trusted lock** and establish byte-for-byte equivalence between the canonical configuration/policy inputs and the semantic/adapter projections. A separately authorized procedure override governs only the `pr-review` Skill bytes; it does not replace the lock-pinned toolchain for projection generation or validation. A stale, manually altered, unverifiable, or non-reproducible projection fails closed. The lock digest alone is not treated as proof that arbitrary generated bytes implement the canonical inputs.

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
5. update policy self-hosting configuration to the promoted full SHA, enable the trusted `pr-review` Skill, generate explicitly bound and lock-verified review projections and Skill bytes from that trusted toolchain, and remove the obsolete `.github/REVIEW_GUIDELINES.md` through the canonical generated-output lifecycle.

Reader-facing Site publication changes, if any, remain a separate cross-authority publication operation and must not be coupled implicitly to the Policy implementation change.

## Consequences

- Review semantics remain engine- and provider-neutral.
- The accepted insights from the two revised review documents are reproducibly frozen without making the documents competing authorities.
- The verified `pr-review` Skill is the only procedural authority; the canonical invocation prompt is thin and non-normative.
- Reviewed head content cannot silently change either the semantic policy or the procedural Skill used to evaluate itself.
- Override authorization is anchored in the exact prior base snapshot rather than the candidate override or reviewed head.
- The base tip is the default trusted policy root, while one verified unique merge-base independently defines the PR-introduced changed surface; ambiguous merge-base histories fail closed.
- The default procedure revision is derived from the active trusted root's authoritative lock and requires repository enablement; an authorized caller may instead supply an explicit immutable out-of-band procedure revision.
- A base-driven procedure change causes a full restart under the newly verified Skill rather than allowing stale procedural authority to continue.
- Managed lock/configuration disagreement, invalid generated projections, and unavailable procedure authority fail closed instead of silently choosing another source.
- Review output paths are explicit invocation inputs and are verified to bind to one trusted context with the expected renderer roles and reproducible bytes rather than inferred from names.
- Projection generation/verification always uses the active trusted lock's toolchain revision even when a separate procedure override is in force.
- GitHub JSON/event/location details remain adapter concerns; finding selection remains semantic policy.
- Automated review cannot silently absorb merge-gate responsibilities.
- `.github/` becomes a thin GitHub runtime/discovery boundary instead of a generic container for GitHub-related policy documents.
- Generated review artifacts remain inspectable while retaining explicit provenance and non-authoritative status.
- The current migration can proceed without a configuration-schema version change because the missing Skill/output association is supplied and validated as explicit invocation data rather than inferred configuration.
