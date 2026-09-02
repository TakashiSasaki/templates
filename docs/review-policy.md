# Shared review policy

The `review` profile contains application-type-independent semantics for high-signal pull-request review. It was extracted from the generic portions of the frozen `skill/.github/REVIEW_GUIDELINES.md` at `skill@63a2ad7ff4ad6396daf269af1536aff53515180d` under the single-authority decision in ADR-0005.

## What belongs here

A review rule belongs in this profile when its meaning remains substantially unchanged for a Web application, Agent Skill, CLI, library, service, or another artifact category and when the same semantic requirement can be followed by different coding agents, automated reviewers, or a human reviewer.

The profile therefore owns review semantics such as:

- treating pull-request claims and reviewed repository content as evidence rather than as instructions or facts that bypass independent verification;
- inspecting enough execution and repository context to establish real behavior;
- assessing the material risk domains applicable to the change before concluding that no blocking defect exists;
- requiring change causality, realistic reachability, concrete impact, and a root-cause location;
- keeping blocking review focused on material, high-confidence defects;
- grounding security, error-path, performance, and regression-guard findings in evidence;
- distinguishing normative repository rules from explanation or historical material;
- resolving apparent rule conflicts from explicit authority rather than document recency; and
- reporting review limitations without converting missing context into an unsupported defect.

These rules do not duplicate artifact contracts. For example, `compatibility.preserve-contracts` remains the shared authority for preserving externally observable contracts; the review profile defines how a reviewer must establish and report a compatibility defect rather than creating a separate review-only definition of compatibility.

## Coverage is not checklist approval

Revised automated-review guidance identified a gap between finding admissibility and review coverage. The existing profile strongly constrains when a blocking finding is valid, but a reviewer also needs an explicit obligation to consider the risk domains actually exposed by the change before reporting a clean result.

`review.assess-applicable-risk-domains` closes that gap. It requires applicable consideration of contract or specification consistency, correctness and preserved invariants, data integrity, tests and CI integrity, security and trust boundaries, compatibility or migration, generated or derived artifacts, failure and recovery paths, and performance or resource behavior.

This does not create a checklist whose completion authorizes approval. A domain that is irrelevant to the change does not need a finding, and enumerating every domain does not satisfy the separate requirements for change causality, realistic reachability, concrete impact, root-cause localization, severity, and evidence quality.

The same review-guidance audit also clarified that pull-request descriptions and review comments are claims and evidence, not review authority. That clarification remains part of the existing `review.treat-reviewed-content-as-data` rule rather than becoming a duplicate rule.

Other guidance was already owned elsewhere and is deliberately reused instead of copied:

- exact revision binding of verification evidence remains `verification.separate-evidence-layers` in the core profile;
- contract preservation remains `compatibility.preserve-contracts`;
- required testing remains `testing.run-required-checks`;
- weakening existing test, security, compatibility, or CI guards remains `review.evaluate-regression-guard-changes`;
- trust-boundary validation remains `security.validate-boundaries` together with `review.trace-security-findings`; and
- concrete data or operational impact remains part of `review.require-reachable-impact`.

Operational requirements such as resolving the exact pull-request base and head, refreshing identities before review completion, retrieving current CI evidence, and preserving review limitations belong to the provider-neutral review procedure rather than new semantic modules. Concrete GitHub request fields or event names belong to integration behavior/reference material, not to semantic policy or the review procedure. ADR-0008 records the immutable review trust machinery; ADR-0009 is the current authority for the review-result representation boundary.

## Statement-level disposition of the revised guidance

`docs/review-guidance-disposition.json` is the machine-readable, non-authoritative disposition record for the frozen migration inputs `RG-01` through `RG-09` and `AP-01` through `AP-08`. It records whether each statement is already owned by canonical policy, contributes to the single new semantic rule in this change, belongs to the planned review procedure, or is useful only as provider integration material.

The disposition record is deliberately not another review policy source. Tests require every frozen input ID to appear exactly once, every semantic authority reference to resolve to a composed canonical rule, and the set of newly introduced semantic authorities to be exactly `{review.assess-applicable-risk-domains}`. Multiple frozen statements may therefore map to the same canonical rule without creating duplicate authority.

Procedure entries identify downstream responsibilities planned for `skills/pr-review/SKILL.md`. The frozen taxonomy's `adapter` disposition class identifies provider-specific transport material. Under ADR-0009, AP-07's adapter-side entry points only to a non-normative GitHub integration reference; that classification does not turn the reference into semantic policy or review-procedure authority. Provider request shape remains governed by the provider API/tool contract.

## What does not belong here

The frozen Skill review document also contains an output and integration protocol. Those requirements are deliberately not copied into `policy/review/`:

- the literal `APPROVE`, `REQUEST_CHANGES`, and `COMMENT` GitHub event names;
- the `COMPLETE`, `PARTIAL`, and `FAILED` serialization values;
- JSON-only output and its field schema;
- fields such as `schema_version`, `analysis_status`, `comments`, or `unanchored_findings`;
- GitHub diff-side values such as `LEFT` and `RIGHT`;
- exact JSON examples and field names;
- numeric confidence serialization required by one reviewer integration; and
- any Antigravity-, Codex-, Gemini-, or provider-specific invocation behavior.

These are not required review-result semantics. GitHub-specific request concepts may be documented in a non-normative integration reference such as `skills/pr-review/references/github-pull-request-review-api.md`, and an executing integration may map an established review result to the current GitHub API. Such a reference or mapping is not semantic policy, not `pr-review` procedure authority, and not a reason to invent a repository-owned general-purpose review JSON schema.

The provider-neutral review procedure may report findings, limitations, and whether its analysis completed in a natural representation suitable for the executing environment. It must preserve their meaning but does not require one JSON object, JSON-only output, or exact response-field names.

## Extraction map

The semantic source sections in the frozen Skill document map to shared rules as follows:

| Frozen section | Shared authority |
| --- | --- |
| Purpose and review scope | `review.focus-on-blocking-findings`, `review.treat-reviewed-content-as-data` |
| Review target | `review.inspect-relevant-context`, `review.assess-applicable-risk-domains` |
| Blocking finding conditions | `review.require-change-causality`, `review.require-reachable-impact`, `review.deduplicate-root-causes` |
| Severity | `review.classify-severity-by-impact` |
| Exclusions | `review.focus-on-blocking-findings`, `review.require-reachable-impact` |
| Security review | `review.trace-security-findings` |
| Error handling and boundary conditions | `review.require-error-path-evidence` |
| Performance and resource use | `review.require-performance-evidence` |
| Test evaluation | `review.evaluate-regression-guard-changes` |
| Repository documentation and rule inspection | `review.identify-applicable-normative-rules`, `review.resolve-rule-conflicts-explicitly`, `review.require-rule-conflict-evidence` |
| Review completion | `review.report-review-limitations` plus provider-neutral procedure completion |
| Comment location | `review.anchor-findings-at-cause`; provider-specific line serialization is integration-only |
| Confidence | semantic high-confidence requirement in `review.focus-on-blocking-findings`; numeric serialization is integration-only |
| JSON output and examples | non-normative provider integration material only |

The `skill` copy remains unchanged in this phase. It is removed or regenerated only after the shared review policy can be selected and rendered through a pinned stable toolchain revision.
