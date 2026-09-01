# ADR-0008: Separate review authority from GitHub runtime integration

- Status: Accepted
- Date: 2026-09-02

## Context

ADR-0005 established one canonical policy authority and requires generated instructions to remain projections rather than competing handwritten authorities. Shared review semantics already live in `policy/review/*.md`, selected through `profiles/review.yml` and configured review contexts.

The current GitHub-facing generated review document combines semantic review rules with GitHub-specific transport requirements. Recent design work also produced revised Review Guidelines and a revised automated pull-request review prompt outside the repository. Those external documents are not immutable repository authorities, so this migration freezes the complete accepted statement-level input baseline in `docs/review-guidance-inputs.md` and classifies that baseline into existing policy, genuinely missing semantic policy, review procedure, adapter concerns, or explanation.

The migration must also prevent proposed-head content from selecting the policy or procedure used to review itself.

## Decision

Automated pull-request review has five responsibility layers:

1. **Semantic review policy** — reviewer-independent obligations and admissibility rules.
2. **Trusted procedure bootstrap** — establishes immutable review-procedure provenance before review execution begins.
3. **Review procedure** — gathers evidence and applies the selected semantic review context.
4. **Platform adapter** — serializes an established semantic result for one provider or protocol.
5. **Platform runtime integration** — files whose location or execution semantics are imposed by the hosting platform.

Each normative requirement has one authority. A lower layer may consume a higher-layer result but may not redefine it.

### Semantic review policy

Canonical review semantics remain atomic modules under `policy/review/*.md`, composed with reusable `policy/core/*` and `policy/security/*` modules through a configured review context.

The frozen inputs in `docs/review-guidance-inputs.md` are migration evidence, not policy. Existing canonical rules are reused whenever they already own a requirement. New semantic modules are created only for genuinely missing, engine- and provider-neutral obligations. GitHub event names, line-side vocabulary, JSON fields, model names, confidence serialization, and similar transport details do not belong in semantic policy.

### Trusted procedure bootstrap

An unverified `pr-review` Skill must never select or authenticate its own executable authority, and an unauthenticated installed `agent-policy` Skill must not be assumed trustworthy merely because it is outside the pull-request head.

For the current architecture there is **exactly one repository-facing bootstrap path**: an installed `agent-policy` Skill runtime/loader whose installation identity has already been authenticated by the deployment. No repository-policy-root override, procedure/toolchain override, alternate loader, or other out-of-band review-authority path is part of this repository contract.

The bootstrap Skill has two distinct immutable identities that must not be collapsed:

- **Skill-source identity** covers the installed `skills/agent-policy` tree containing the bootstrap algorithm itself.
- **Runtime identity** covers the toolchain revision and dependency lock selected by `runtime-manifest.json` / the managed repository lock.

Before any bootstrap instruction or executable from the installed Skill is trusted, the hosting/deployment dispatcher must verify the installed Skill tree against a **deployment-managed installation attestation stored outside the installed Skill tree and outside the repository under review**. That attestation must record at least the immutable installer repository/full-SHA revision, immutable Skill-source repository/full-SHA revision, and cryptographic digests for every installed bootstrap-authority file. The attested installer and Skill-source identities must match an independently trusted deployment pin established before the review invocation; neither the pull-request base nor head may select or rewrite that deployment pin. The published `release/skill-installer.json` contract distinguishes installer and Skill-source revisions and may be used when provisioning that deployment pin, but a repository copy encountered during review is not itself sufficient bootstrap authentication evidence.

`runtime-manifest.json` is then used for its separate runtime-selection responsibility. It does **not** authenticate the Skill-source bytes that contain the bootstrap algorithm. Bootstrap is unavailable unless both the external installation-attestation verification and the applicable runtime identity checks succeed.

The absence of an authority override path is intentional. The current configuration schema contains no canonical machine-readable contract for authorizing one. Any future alternate bootstrap authority or out-of-band policy/procedure selection requires a separate architecture decision and a validated machine contract before it can be used. Until then, attempts to substitute another authority fail closed.

Before `pr-review` executes, trusted bootstrap must:

1. require successful deployment-side authentication of the installed `agent-policy` Skill-source identity and bytes against the external installation attestation;
2. obtain and record the stable repository identity and pull-request identity from the hosting/repository system;
3. obtain the exact current target/base revision and a repository snapshot proven to represent that repository identity at that exact revision;
4. use that exact base snapshot as the active trusted repository-policy root;
5. run the authenticated installed `agent-policy` runtime against that trusted snapshot and require its managed configuration/lock checks to succeed;
6. treat `.agent-policy.lock` as the authoritative managed toolchain pin and require its repository/full-SHA identity to agree with `.agent-policy.yml`;
7. require the trusted base configuration to enable `pr-review` through `skills.enabled`;
8. require `.agents/skills/pr-review/SKILL.md` and every declared `pr-review` reference to resolve lexically inside the trusted repository root, remain inside the generated `pr-review` tree, contain no parent traversal or reserved namespace, have **no symlink component at any path level**, and end in regular non-symlink files reproduced by the lock-pinned immutable toolchain;
9. record the lock-selected procedure revision and cryptographic digests/provenance of the verified generated Skill files; and
10. hand that immutable bootstrap evidence to the verified `pr-review` Skill.

A mutable branch/tag, an unauthenticated installed Skill, a repository-local Skill, or any `agent-policy`/`pr-review` bytes from the proposed head must never participate in bootstrap for that same review. If installed bootstrap provenance cannot be authenticated independently, or if the trusted base does not validly enable and reproduce `pr-review`, automated review under this architecture is unavailable and fails closed.

Trusted bootstrap is not a second review procedure. It may establish bootstrap installation identity, repository and pull-request identity, exact base identity, configuration/lock validity, procedure identity, generated Skill provenance, and handoff evidence only. It must not inspect the proposed change for findings, classify CI or review evidence, choose provider events, decide review completeness, or authorize merge.

### Review procedure

After trusted bootstrap hands control to verified immutable `pr-review` bytes, that Skill is the **sole procedural authority for review execution**. It consumes bootstrap evidence but does not retroactively select or authenticate itself.

At review start the procedure records and verifies:

- stable repository identity matching bootstrap evidence;
- pull-request identity matching bootstrap evidence;
- exact current target/base revision matching the trusted repository-policy root;
- exact proposed head revision; and
- the complete set of best common ancestors between base and head.

The best-common-ancestor set must contain exactly one revision. That unique merge base defines the PR-introduced changed surface as **merge-base → proposed head**. Unrelated histories and multiple-best-base/criss-cross histories fail closed; the procedure does not select an arbitrary base or synthesize an unspecified virtual base.

The procedure inspects the complete changed surface plus enough callers, callees, schemas, configuration, tests, CI definitions, migrations, generated artifacts, and normative repository context to establish real behavior when required by semantic policy. Finding causality and changed-location requirements remain semantic-policy concerns.

The Skill references semantic policy rather than copying severity, compatibility, security-impact, confidence, or finding-admissibility definitions.

The retained canonical automated-review prompt is only a thin non-normative invocation surface. It supplies repository/PR identity and output-binding inputs and directs the already authenticated trusted bootstrap to the verified Skill. It is neither bootstrap authority nor review procedure. If it conflicts with bootstrap or the verified Skill, bootstrap governs executable provenance and the Skill governs review execution.

### Trusted review authority root

The exact current base snapshot established by trusted bootstrap is the **only active repository-policy root** for the review. Proposed-head changes to `.agent-policy.yml`, `.agent-policy.lock`, policy modules, generated review instructions, adapters, Skills, or other authority material are review data, never active authority for that same review.

The trusted base must contain valid `.agent-policy.yml` and `.agent-policy.lock`. The lock is authoritative for the managed runtime pin; missing or malformed lock state, configuration/lock disagreement, invalid full-SHA identity, input/output digest failure, stale generated outputs, or inability to reproduce required outputs fails closed.

Immediately before final serialization, the procedure re-resolves pull-request identity, stable repository identity, base, head, and the complete best-common-ancestor set from the hosting/repository system.

- If pull-request identity differs from bootstrap evidence, fail closed. PR-specific evidence or output destinations must never be reused for another pull request merely because base/head commits happen to match.
- If repository identity differs from bootstrap evidence, fail closed. Authority established for one repository must never be carried into another repository or fork merely because commits match.
- If the base revision changes, stop the current review and return to the authenticated installed bootstrap. The replacement exact base becomes the new trusted repository-policy root. Configuration, lock, `skills.enabled`, generated Skill provenance, output bindings, and generated projections must all be re-established from that base before review continues. If procedure revision or Skill bytes change, restart under the newly verified Skill.
- If only head or unique merge base changes while pull-request identity, repository identity, and base remain stable, recompute the changed surface and refresh all affected evidence and semantic analysis.
- If the histories become unrelated or have multiple best merge bases, fail closed.

Serialization is allowed only when an immediately pre-serialization observation reproduces the fully analyzed pull-request identity, repository identity, base, head, unique merge base, authenticated bootstrap identity, and verified procedure identity.

### Review output binding

Schema version 2 keeps Skill enablement independent from output selection, so `pr-review` must not infer a context from a literal name or choose arbitrarily among multiple outputs.

The invocation supplies two explicit repository-relative output paths from the trusted base snapshot:

- the provider-neutral semantic review projection; and
- the provider/platform adapter projection for the requested output surface.

Before use, the verified Skill requires both configured outputs to be enabled, their paths to match the supplied paths exactly, both to reference the same context, the semantic output renderer to be exactly `policy-context-md`, and the adapter renderer to be a supported adapter-only renderer such as `github-review-json-adapter-v1`.

Configuration, lock, generated Skill/reference, and projection paths must be repository-relative, root-confined, outside `.git` and reserved namespaces, and free of symlink components. Missing, unsafe, duplicate, disabled, role-swapped, unsupported, or otherwise ambiguous bindings fail closed.

Checked-in generated projections are not trusted from metadata alone. Their lock input/output digests must match and deterministic check/regeneration with the **toolchain revision pinned by the trusted base lock** must reproduce the semantic and adapter projections byte for byte. Stale, manually altered, unverifiable, or non-reproducible projection bytes fail closed.

This explicit invocation binding is sufficient for the current design. A future machine-declared Skill-to-output binding would change the configuration trust contract and requires a separate architecture decision.

### Platform adapter

GitHub-specific event names, response schema, confidence serialization, changed-file path/line anchors, `LEFT`/`RIGHT` side selection, and similar provider details remain adapter concerns.

The adapter is bound to the same semantic context as the provider-neutral projection but does not copy the semantic rule corpus. Finding selection and admissibility remain semantic-policy concerns. The adapter serializes every semantic blocking finding without adding its own confidence threshold or suppressing unanchored findings; findings that cannot truthfully use a GitHub inline anchor require a lossless non-inline representation.

### Pull-request review versus merge authorization

Automated review and merge authorization are separate contexts.

The review procedure determines a semantic review result. Existing `policy/pull-request/*` and `skills/pr-merge-gate/*` own merge readiness and merge authorization, including exact-head CI evidence, independent review completion, unresolved threads, target freshness, mergeability, immutable-head guards, and post-merge verification.

A provider-recorded review object is not automatically evidence that required independent review analysis completed. Merge-gate evidence must establish completion under the applicable review contract. A partial, failed, incomplete, or materially limited review cannot silently become merge authorization merely because the provider stored a review event.

### `.github/` runtime boundary

The `policy` branch does not use `.github/` as a general namespace for GitHub-related material.

Files belong under `.github/` only when GitHub assigns path-based discovery or runtime semantics to that location, such as GitHub Actions workflows and other GitHub-defined repository metadata.

Generated semantic review projections, adapter projections, prompts, renderer sources, and Skill sources live outside `.github/` unless GitHub requires the exact path. The transitional generated `.github/REVIEW_GUIDELINES.md` is removed only after replacement projections exist and the canonical lock-bound generated-output lifecycle can remove it safely.

### Generated consumer projections

Generated review artifacts are projections rather than authorities. Their output paths are configuration data. Obsolete generated outputs are removed only through the existing lock-bound fail-closed lifecycle; modified or non-generated files are never deleted merely because configuration changed.

## Migration sequence

Implement the decision in separate reviewed changes:

1. record this architecture decision and freeze the accepted input inventory;
2. classify every frozen input and add only genuinely missing atomic semantic review rules;
3. extend the stable Skill-installer/distribution contract to produce an independently verifiable installation attestation outside the installed Skill tree, extend the authenticated installed `agent-policy` Skill with the single trusted `pr-review` bootstrap handoff, add `pr-review` as the sole review-execution procedure, retain only a thin non-normative invocation prompt, and introduce a transport-only GitHub adapter without changing the meaning of the transitional combined renderer;
4. harden merge-gate evidence so incomplete review analysis cannot satisfy independent-review requirements;
5. harden stable-promotion verification for the new bootstrap/review/adapter capability and promote the reviewed toolchain revision; and
6. update Policy self-hosting to the promoted full SHA, enable `pr-review`, generate bound and lock-verified review projections/Skill bytes, and remove obsolete `.github/REVIEW_GUIDELINES.md` through the canonical generator.

Reader-facing Site publication remains a separate cross-authority operation.

## Consequences

- Review semantics remain engine- and provider-neutral.
- The frozen revised-guidance inputs are reproducible migration evidence without becoming a competing authority.
- Trust establishment is non-circular: deployment authentication establishes the installed `agent-policy` Skill-source identity before that Skill bootstraps and verifies `pr-review`.
- Bootstrap Skill-source identity and runtime identity remain distinct; `runtime-manifest.json` cannot substitute for installation provenance.
- There is one current bootstrap path, one trusted repository-policy root, and one lock-selected repository procedure path; undefined override or alternate-loader mechanisms are rejected rather than inferred.
- Pull-request identity and stable repository identity are both part of start/final review evidence, preventing cross-PR and cross-repository authority/evidence reuse based only on commit identity.
- Base movement always returns control to authenticated bootstrap and re-establishes all trusted authority from the replacement base.
- The verified `pr-review` Skill is the only review-execution procedural authority; the invocation prompt remains non-normative.
- Managed lock/configuration disagreement, unsafe or symlinked generated paths, stale generated bytes, ambiguous merge bases, or unavailable procedure authority fail closed.
- Semantic and adapter projections are explicitly bound, role-checked, and byte-reproduced from the trusted lock-pinned toolchain.
- GitHub transport requirements remain adapter-only; merge authorization remains pull-request-policy/procedure-only.
- `.github/` remains a thin platform runtime/discovery boundary rather than a policy namespace.
