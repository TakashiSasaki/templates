---
id: pull-request.require-independent-exact-head-review
severity: mandatory
overridable: true
order: 965
---
# Require an independent exact-head review before merge

Before merging a pull request, require at least one completed review from an independent reviewer or review system for the exact proposed head commit. A review request, pending review, absence of review findings, or zero completed reviews is not review evidence and must block merge. The agent or actor that implemented the proposed change must not count its own self-review as the required independent review.

A submitted or provider-recorded review object is not by itself evidence that the review's required analysis completed. The relied-upon evidence must establish, under the applicable review procedure or review contract, that the required analysis completed for the exact proposed head. A review that reports itself as incomplete, partial, failed, or materially limited such that required analysis was not completed must not satisfy the independent-review requirement, even when a provider records that review as submitted or completed. If current evidence cannot establish whether the required analysis completed, keep merge authorization fail-closed rather than inferring completion from a provider event, review state, or the absence of blocking findings.

The relied-upon review evidence must identify the reviewed exact head through review metadata or an unambiguous completed review result. If the proposed head changes after that review, treat the review as stale and obtain a new completed review for the new exact head before merge.

If the required reviewer is unavailable or does not complete the review, report the pull request as blocked rather than waiving the requirement. Only an explicit repository policy may define an exception; an implementing agent must not invent or self-authorize one.
