---
id: pull-request.discover-review-results-across-applicable-surfaces
severity: mandatory
overridable: true
order: 964
---
# Discover review results across applicable surfaces

Before classifying the current review cycle as complete, problem-free, or containing findings, inspect the applicable provider-supported review-result surfaces for the pull request rather than treating a review-submission object as the complete review result. The inspected set must include submitted review bodies, ordinary pull-request or issue comments that can carry reviewer results, inline review comments and resolvable review threads, and any other provider surface or signal that the applicable review procedure or provider contract defines as capable of carrying review-result semantics.

Do not infer `no findings` from an empty review-submission body, an approval state, an empty thread list, or the absence of findings on any single provider surface. A material actionable finding discovered on any applicable review-result surface remains a finding even when another surface reports approval or contains no finding. When provider mechanics separate a logical review across multiple surfaces, reconstruct the logical result before classifying it.

Treat reactions and similar provider signals as semantic review evidence only when the applicable workflow, review procedure, or provider contract establishes their meaning for the result being classified. A reaction without such a defined meaning is uninterpreted provider state; at most it may corroborate separately established evidence. Do not interpret an acknowledgement or attention signal as review completion, approval, or absence of findings merely from its glyph or provider presentation.

If the execution environment cannot inspect a provider surface that is known to be capable of carrying applicable review-result semantics, or cannot determine whether a discovered signal has result semantics, record the limitation and keep any affected completion or no-findings conclusion fail-closed. This discovery rule determines whether the logical review result has been observed sufficiently; the separate review-result applicability rule determines which observed evidence belongs to the current review cycle and revision.
