# ADR-0008: Separate review authority from GitHub runtime integration

- Status: Accepted
- Date: 2026-09-02

## Context

ADR-0005 established one canonical policy authority and requires generated instructions to remain projections rather than competing handwritten authorities. The current review implementation already follows part of that model: shared review semantics live in `policy/review/*.md`, `profiles/review.yml` selects the review-specific modules, and `.agent-policy.yml` composes review contexts from shared profiles and repository-local policy.

The current GitHub-facing projection, however, combines two different responsibilities. `.github/REVIEW_GUIDELINES.md` is a generated file, but its location makes it appear repository-authoritative even though its semantic content is derived from policy modules. Its renderer also combines semantic rules with a GitHub-specific JSON transport contract. At the same time `.github/workflows/*` contains actual GitHub Actions entry points whose placement under `.github/workflows/` is part of GitHub's discovery contract.

Recent automated-review design work also produced revised Review Guidelines and a revised Canonical automated PR review prompt. The original conversational documents are not immutable repository inputs, so this migration freezes the complete accepted statement-level baseline in `docs/review-guidance-inputs.md`. Follow-up implementation may classify only that frozen baseline unless a reviewed change explicitly amends it.

## Decision

Separate automated pull-request review into five responsibility layers:

1. **Semantic review policy** defines reviewer-independent obligations and admissibility requirements for findings.
2. **Trusted procedure bootstrap** establishes which immutable review Skill is authorized to execute without consulting proposed-head bytes.
3. **Review procedure** defines the operational sequence used by that verified Skill to gather evidence and apply the selected review context.
4. **Platform adapter** defines provider-specific transport, serialization, event names, and inline-location rules.
5. **Platform runtime integration** contains files whose path or discovery semantics are imposed by the hosting platform.

No lower layer may redefine the semantics owned by a higher layer, and each layer has exactly one source authority for a given requirement. Trusted procedure bootstrap is deliberately narrower than review procedure: it may establish repository identity, prior trust anchor, immutable runtime/procedure identity, and fail-closed handoff, but it must not perform review analysis or redefine review semantics.

### Semantic review policy

Canonical review semantics remain atomic modules under `policy/review/*.md`, composed with reusable `policy/core/*` and `policy/security/*` modules through a configured review context.

The frozen Review Guidelines inputs in `docs/review-guidance-inputs.md` are classified statement by statement. Existing canonical rules are reused when they already own a requirement. New modules are created only for genuinely missing, independently applicable semantics. The review corpus remains provider-neutral and must not encode GitHub event names, GitHub line-side vocabulary, model names, or transport serialization.

The frozen guidance inventory is therefore migration evidence, not a second normative policy document.

### Trusted procedure bootstrap

An unverified `pr-review` Skill must never participate in selecting or verifying its own authority. Before any review procedure executes, a trusted loader/dispatcher establishes the procedure identity and hands control to verified immutable Skill bytes.

The canonical repository-facing bootstrap authority is the existing immutable `agent-policy` Skill runtime/loader contract. Its executable bootstrap implementation is distributed outside the reviewed pull-request head, pins its own toolchain/runtime identity through an immutable runtime manifest or an explicitly authorized immutable bootstrap revision, treats a managed repository lock as authoritative for the repository-selected toolchain, and fails closed rather than executing a mutable branch or a repository-local Skill discovered from the proposed head. A deployment may use an independently administered equivalent loader only when the repository contract explicitly authorizes that bootstrap authority; the proposed head and the candidate policy/procedure override may not authorize it.

The bootstrap performs only these trust-establishment responsibilities before handing control to `pr-review`:

1. establish and record the stable repository identity supplied by the hosting/repository system, together with the exact current target/base tip, before selecting any policy or procedure override;
2. use that exact base snapshot as the prior repository trust anchor for authorization of any requested out-of-band repository-policy or procedure/toolchain override;
3. select the active trusted repository-policy root only after that prior-anchor authorization succeeds;
4. validate the active root's managed configuration/lock trust state sufficiently to determine its authoritative full-SHA toolchain pin and repository Skill enablement;
5. when no separately authorized immutable procedure override exists, require the active trusted configuration to enable `pr-review` and resolve its procedure revision from the validated authoritative lock pin;
6. when a separately authorized immutable procedure override exists, use only that immutable revision for `pr-review` procedure bytes while retaining the active repository lock as the toolchain authority for repository-policy projection validation;
7. obtain `pr-review` only from the selected immutable procedure revision and verify its provenance before execution; and
8. hand the recorded repository identity, prior authorization anchor, active policy root, validated lock/config identities, selected procedure revision, and any authorized overrides to the verified Skill as bootstrap evidence.

The loader must never execute or delegate authority selection to a `pr-review` copy from the proposed head, a mutable branch/tag, or an unverified local generated Skill. If bootstrap cannot establish an authorized immutable procedure identity and provenance, automated review is unavailable and fails closed before review analysis begins.

This bootstrap contract does not make the loader a second review procedure. It cannot decide changed-surface semantics, finding admissibility, severity, CI interpretation, review completeness, adapter events, or merge authorization. Those responsibilities remain with the verified review Skill, semantic policy, adapter, and merge-gate authorities respectively.

### Review procedure

After trusted bootstrap hands control to verified immutable `pr-review` bytes, that Skill is the **sole procedural authority for review execution**. It owns the ordered review operations: exact target and comparison identity, complete changed-surface inspection, relevant-context discovery, evidence handling, target revalidation, semantic-policy application, adapter handoff, and the boundary that stops review before merge authorization. It consumes bootstrap evidence but does not retroactively select or authenticate itself.

At review start the procedure records and verifies against bootstrap evidence:

- the stable repository identity for the repository being reviewed;
- the exact current target/base tip, which is the default trusted repository-policy root unless an authorized override was selected;
- the exact proposed head; and
- the complete set of best common ancestors between that base tip and proposed head.

The procedure requires that best-common-ancestor set to contain **exactly one** revision. That unique revision is the merge-base/comparison base for the PR-introduced changed surface. If the histories are unrelated or have multiple best merge bases, including a criss-cross history, the procedure fails closed rather than selecting an arbitrary merge base or synthesizing an unspecified virtual base.

The complete PR changed surface is defined as the repository change from that unique recorded merge-base to the recorded proposed head. A tip-to-tip base→head comparison is not substituted for that surface. Surrounding repository context may be inspected beyond the changed surface when the semantic review requires it, but findings still follow the semantic policy's causality and changed-location requirements.

The Skill must reference semantic policy instead of copying definitions such as severity, compatibility, security impact, or admissibility thresholds.

The previously revised Canonical automated PR review prompt is not a second procedure authority. Its reusable retained form is a thin, explicitly non-normative invocation surface that supplies task and trust-binding parameters and directs the trusted bootstrap to load a verified `pr-review` Skill. Procedural knowledge extracted from the revised prompt is incorporated into the Skill itself. If the prompt and verified Skill ever appear to disagree, the verified Skill governs and the prompt must be regenerated or corrected.

### Trusted review authority root

Reviewed content must not be allowed to choose or weaken either the semantic policy, bootstrap authority, or procedural code used to judge itself.

The exact current **base tip captured before selecting any override** is the default prior repository trust anchor for the review. By default it is also the active trusted repository-policy root. A caller may request an immutable out-of-band repository-policy root or procedure/toolchain revision only when that override mechanism and requested identity are explicitly authorized by this prior trust anchor. The candidate override revision must never authorize itself, and proposed-head content must never authorize an override. If the prior base does not authorize the requested override mechanism or identity, bootstrap fails closed rather than consulting the candidate override for permission. A future independently administered trust-anchor mechanism would require its own explicit repository contract; it is not inferred here.

When an authorized repository-policy override is selected, that immutable revision becomes the active trusted repository-policy root. The reviewer reads `.agent-policy.yml`, `.agent-policy.lock`, repository-local policy inputs, generated review projections, and their recorded provenance only from that active trusted snapshot. Changes on the proposed head to policy configuration, lock state, policy modules, generated review instructions, adapter configuration, generated Skills, or related authority material are review data, not active instructions for that same review.

For a repository-bound review, the active trusted root must contain a valid `.agent-policy.yml` and `.agent-policy.lock`. The lock is the authoritative managed-runtime pin: its `toolchain.repository` and full-SHA `toolchain.revision` must be valid and must agree exactly with the corresponding configuration values. A missing or malformed lock, a configuration/lock disagreement, an input-digest mismatch, or other lock-integrity failure causes bootstrap/review to fail closed rather than selecting the configuration pin independently.

The procedural Skill is resolved independently of the proposed head. Unless the prior trust anchor authorizes a separately supplied immutable trusted procedure/toolchain revision, bootstrap derives the procedure revision from the **active trusted repository-policy root's validated lock pin**, not from `.agent-policy.yml` alone. The active trusted configuration must also list `pr-review` in `skills.enabled`; a toolchain merely containing that Skill does not authorize its execution. Bootstrap resolves `pr-review` only from the validated full-SHA procedure revision and verifies Skill provenance against that immutable revision before executing it. A repository-local or generated `pr-review` copy from the proposed head is never executed merely because it is newer or locally discoverable.

An explicitly authorized out-of-band trusted procedure/toolchain revision is a separate procedure-selection authority supplied by the caller after authorization has been established from the prior base trust anchor. Such an override may be used even when the active repository configuration does not enable `pr-review`. The override revision must be immutable, recorded in bootstrap/review evidence, and selected independently of reviewed head content. An authorized repository-policy-root override without a separate procedure override does **not** bypass repository procedure selection: default procedure availability and pinning are evaluated against that selected active repository-policy root.

If the active trusted repository-policy root does not validly select and enable a toolchain revision containing `pr-review`, and no authorized out-of-band trusted procedure revision is supplied, automated review is unavailable and must fail closed rather than falling back to a head-side Skill.

Immediately before final serialization, the procedure re-resolves the stable repository identity, base tip, proposed head, and complete set of best common ancestors. Repository identity must still refer to the same repository contract used by bootstrap; commit identity alone is insufficient across forks or repositories. The ancestor set must still contain exactly one merge-base.

If the base tip changes, every active out-of-band repository-policy or procedure override must be **reauthorized against the replacement exact base snapshot before review continues**, even when the override revision itself would otherwise remain fixed. If the new base does not authorize the same override mechanism and immutable identity, the current review fails closed or restarts using authority newly selected under the replacement base; the old authorization cannot be carried forward. When this rebootstrap selects a procedure revision different from the Skill currently executing, the current run stops and the review restarts under the newly verified Skill before any further analysis or serialization. The old Skill cannot emulate requirements owned by the new procedure revision.

After any repository identity, base, head, unique merge-base, merge-base cardinality, policy-root authorization, or procedure identity change, the review is stale. It replaces the recorded identities, recomputes the unique merge-base→head changed surface, refreshes affected evidence and semantic analysis, and repeats the final observation. An explicit out-of-band repository-policy root may remain the selected root only while each replacement base reauthorizes it. Serialization is reached only when an immediately pre-serialization observation reproduces the fully analyzed repository identity, base, head, unique merge-base, active policy-root authorization, and verified procedure identity.

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

The review procedure determines whether changed code contains material, evidence-backed findings under the trusted review policy. Merge-gate policy and procedure determine whether the exact current head is authorized to merge based on CI, independently completed review analysis, unresolved threads, base freshness, mergeability, and other lifecycle evidence.

The review procedure collects and revision-binds CI or remote evidence when material, but the selected semantic review policy determines how that evidence affects a finding or limitation. Procedure and adapter layers do not independently classify pending, missing, successful, failed, stale, or inaccessible CI as either a defect or a clean result.

Existing `policy/pull-request/*` and `skills/pr-merge-gate/*` continue to own merge-readiness and merge-authorization semantics and procedure. In particular, a provider-recorded review object is not automatically proof that required independent review analysis completed; merge-gate evidence must establish completion under the applicable review contract.

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
3. extend the immutable agent-policy Skill runtime/loader with the minimal trusted `pr-review` bootstrap handoff, add the dedicated automated PR-review Skill as the sole review-execution procedure authority, retain only a thin non-normative invocation prompt, and introduce a transport-only GitHub adapter without silently changing the meaning of an existing combined renderer;
4. harden merge-gate evidence so incomplete review analysis cannot satisfy the independent-review requirement;
5. harden stable-promotion verification for the newly declared review/bootstrap capability and promote the resulting reviewed toolchain revision through the existing stable-release process; and
6. update policy self-hosting configuration to the promoted full SHA, enable `pr-review`, generate explicitly bound and lock-verified review projections and Skill bytes from that trusted toolchain, and remove the obsolete `.github/REVIEW_GUIDELINES.md` through the canonical generated-output lifecycle.

Reader-facing Site publication changes, if any, remain a separate cross-authority publication operation and must not be coupled implicitly to the Policy implementation change.

## Consequences

- Review semantics remain engine- and provider-neutral.
- The accepted insights from the two revised review documents are reproducibly frozen without making the documents competing authorities.
- The immutable agent-policy runtime/loader establishes trusted procedure provenance before `pr-review` executes; an unverified review Skill never verifies itself.
- The verified `pr-review` Skill is the only review-execution procedural authority; the canonical invocation prompt is thin and non-normative.
- Reviewed head content cannot silently change bootstrap authority, semantic policy, or the procedural Skill used to evaluate itself.
- Repository identity is part of review evidence together with exact revision identities, preventing cross-repository/fork ambiguity from commit identity alone.
- Override authorization is anchored in the exact prior base snapshot rather than the candidate override or reviewed head, and every active override is reauthorized after base movement.
- The base tip is the default trusted policy root, while one verified unique merge-base independently defines the PR-introduced changed surface; ambiguous merge-base histories fail closed.
- The default procedure revision is derived from the active trusted root's authoritative lock and requires repository enablement; an authorized caller may instead supply an explicit immutable out-of-band procedure revision.
- A base-driven procedure change causes a full restart under the newly verified Skill rather than allowing stale procedural authority to continue.
- Managed lock/configuration disagreement, invalid generated projections, and unavailable procedure authority fail closed instead of silently choosing another source.
- Review output paths are explicit invocation inputs and are verified to bind to one trusted context with the expected renderer roles and reproducible bytes rather than inferred from names.
- Projection generation/verification always uses the active trusted lock's toolchain revision even when a separate procedure override is in force.
- GitHub JSON/event/location details remain adapter concerns; finding selection remains semantic policy.
- Automated review cannot silently absorb merge-gate responsibilities, and an incomplete submitted review cannot silently satisfy merge authorization.
- `.github/` becomes a thin GitHub runtime/discovery boundary instead of a generic container for GitHub-related policy documents.
- Generated review artifacts remain inspectable while retaining explicit provenance and non-authoritative status.
- The current migration can proceed without a configuration-schema version change because the missing Skill/output association is supplied and validated as explicit invocation data rather than inferred configuration.
