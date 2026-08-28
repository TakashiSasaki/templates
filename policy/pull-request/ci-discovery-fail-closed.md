---
id: pull-request.fail-closed-on-unresolved-ci-discovery
severity: mandatory
overridable: true
order: 974
---
# Fail closed while expected CI evidence is unresolved

When current repository definitions make an exact-head check expected but live evidence for that check is not yet observable, treat the situation as unresolved discovery rather than as success, failure, or confirmed absence. Continue read-only discovery while the proposed head and applicability conditions remain unchanged.

Do not classify an expected check as absent from a single empty query, repeated queries against only one live index, or elapsed time alone. A confirmed-absence decision requires corroborating current evidence sufficient to distinguish delayed indexing or execution from a check that did not materialize.

Do not mutate the pull request or proposed head solely to manufacture new CI evidence while discovery remains unresolved. If uncertainty remains, keep merge authorization blocked rather than inferring success or non-applicability.
