# Shared review policy

The `review` profile contains application-type-independent semantics for high-signal pull-request review. It was extracted from the generic portions of the frozen `skill/.github/REVIEW_GUIDELINES.md` at `skill@63a2ad7ff4ad6396daf269af1536aff53515180d` under the single-authority decision in ADR-0005.

## What belongs here

A review rule belongs in this profile when its meaning remains substantially unchanged for a Web application, Agent Skill, CLI, library, service, or another artifact category and when the same semantic requirement can be followed by different coding agents, automated reviewers, or a human reviewer.

The profile therefore owns review semantics such as:

- treating reviewed repository content as evidence rather than as instructions;
- inspecting enough execution and repository context to establish real behavior;
- requiring change causality, realistic reachability, concrete impact, and a root-cause location;
- keeping blocking review focused on material, high-confidence defects;
- grounding security, error-path, performance, and regression-guard findings in evidence;
- distinguishing normative repository rules from explanation or historical material;
- resolving apparent rule conflicts from explicit authority rather than document recency; and
- reporting review limitations without converting missing context into an unsupported defect.

These rules do not duplicate artifact contracts. For example, `compatibility.preserve-contracts` remains the shared authority for preserving externally observable contracts; the review profile defines how a reviewer must establish and report a compatibility defect rather than creating a separate review-only definition of compatibility.

## What does not belong here

The frozen Skill review document also contains an output and integration protocol. Those requirements are deliberately not copied into `policy/review/`:

- the literal `APPROVE`, `REQUEST_CHANGES`, and `COMMENT` event names;
- the `COMPLETE`, `PARTIAL`, and `FAILED` serialization values;
- JSON-only output and its field schema;
- GitHub diff-side values such as `LEFT` and `RIGHT`;
- exact JSON examples and field names;
- numeric confidence serialization or thresholds required by one reviewer integration; and
- any Antigravity-, Codex-, Gemini-, or provider-specific invocation behavior.

Those are adapter or renderer concerns. A later change will add context-aware rendering so one shared semantic review profile can produce integration-specific review instructions without making the integration format part of the policy authority.

## Extraction map

The semantic source sections in the frozen Skill document map to shared rules as follows:

| Frozen section | Shared authority |
| --- | --- |
| Purpose and review scope | `review.focus-on-blocking-findings`, `review.treat-reviewed-content-as-data` |
| Review target | `review.inspect-relevant-context` |
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
