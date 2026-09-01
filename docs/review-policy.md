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

Operational requirements such as resolving the exact pull-request base and head, refreshing the head before emitting a review, retrieving current CI evidence, and serializing a GitHub review belong to review procedure or adapter layers rather than new semantic modules. ADR-0008 records that boundary.

## Statement-level disposition of the revised guidance

`docs/review-guidance-disposition.json` is the machine-readable, non-authoritative disposition record for the frozen migration inputs `RG-01` through `RG-09` and `AP-01` through `AP-08`. It records whether each statement is already owned by canonical policy, contributes to the single new semantic rule in this change, belongs to the planned review procedure, or belongs to the planned adapter.

The disposition record is deliberately not another review policy source. Tests require every frozen input ID to appear exactly once, every semantic authority reference to resolve to a composed canonical rule, and the set of newly introduced semantic authorities to be exactly `{review.assess-applicable-risk-domains}`. Multiple frozen statements may therefore map to the same canonical rule without creating duplicate authority.

Procedure and adapter entries identify the downstream owner planned by ADR-0008; they do not make the disposition file procedural or transport authority. Those requirements become executable only in the dedicated reviewed follow-up that supplies `pr-review` and the adapter.

## What does not belong here

The frozen Skill review document also contains an output and integration protocol. Those requirements are deliberately not copied into `policy/review/`:

- the literal `APPROVE`, `REQUEST_CHANGES`, and `COMMENT` event names;
- the `COMPLETE`, `PARTIAL`, and `FAILED` serialization values;
- JSON-only output and its field schema;
- GitHub diff-side values such as `LEFT` and `RIGHT`;
- exact JSON examples and field names;
- numeric confidence serialization or thresholds required by one reviewer integration; and
- any Antigravity-, Codex-, Gemini-, or provider-specific invocation behavior.

Those are adapter or renderer concerns. A later change will separate provider-neutral review rendering from the GitHub transport renderer so one shared semantic review profile can support integration-specific review instructions without making the integration format part of the policy authority.

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
| Review completion | `review.report-review-limitations` plus adapter serialization |
| Comment location | `review.anchor-findings-at-cause` plus GitHub adapter line-side serialization |
| Confidence | semantic high-confidence requirement in `review.focus-on-blocking-findings`; numeric serialization remains adapter-owned |
| JSON output and examples | adapter-owned only |

The `skill` copy remains unchanged in this phase. It is removed or regenerated only after the shared review policy can be selected and rendered through a pinned stable toolchain revision.
