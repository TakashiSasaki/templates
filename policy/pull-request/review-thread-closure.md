---
id: pull-request.close-review-threads-before-merge
severity: mandatory
overridable: true
order: 970
---
# Close review findings before merge

Before merging a pull request, inspect the current submitted reviews, resolvable review threads, and actionable findings for the exact proposed head. Apply the canonical cross-surface review-result discovery rule so findings carried by ordinary comments, review bodies, inline comments, resolvable threads, or other applicable provider-supported surfaces are not omitted merely because they are absent from a submitted-review object or thread list. Treat each independently actionable finding as requiring its own repair or explicit disposition and validation, whether or not the provider exposes that finding as a resolvable thread.

When a resolvable thread exists, do not mark it resolved until the required repair or evidence-backed no-change disposition has been completed and validated for the current head. A code or documentation change by itself is not proof that the finding is resolved, and a provider's resolved UI state is bookkeeping rather than semantic proof of remediation.

When an actionable finding exists only in a top-level review body or another non-resolvable review surface, the absence of a thread does not mean the finding is resolved. Inspect it, repair it or record an explicit finding-level disposition, validate that outcome, and retain enough finding-level closure evidence to distinguish it from unresolved or deferred material findings.

Do not treat an unresolved material finding as complete merely by changing provider UI state. Do not merge while any material actionable finding lacks validated remediation or an explicit validated disposition, unless an explicit repository policy defines a documented exception. After that semantic closure is established, mark the corresponding provider thread resolved when such a thread exists and provider mechanics permit it.
