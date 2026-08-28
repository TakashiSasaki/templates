---
id: pull-request.require-exact-head-ci-evidence
severity: mandatory
overridable: true
order: 972
---
# Require exact-head CI evidence before merge

Before declaring a pull request merge-ready or merging it, identify the checks that are applicable to the current proposed head from the current repository workflow and validation definitions. Rely only on CI or validation evidence that applies to that exact head commit. A successful result for an older head is historical evidence and must not satisfy the current merge gate.

Do not treat an expected but not yet observable check as successful, non-applicable, or absent merely because one live query returns no result. Until applicable exact-head checks have been positively identified or their non-applicability is established by current repository policy, keep merge authorization fail-closed.

If a newer applicable exact-head run supersedes an older cancelled or stale run, evaluate the newest applicable evidence rather than treating the superseded run by itself as the current result.
