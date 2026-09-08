---
id: pull-request.require-exact-head-ci-evidence
severity: mandatory
overridable: true
order: 972
---
# Require exact-head CI evidence before merge

Before declaring a pull request merge-ready or merging it, identify the checks that are applicable to the current proposed head from the current repository workflow and validation definitions. Rely only on CI or validation evidence that applies to that exact head commit. A successful result for an older head is historical evidence and must not satisfy the current merge gate.

When the repository uses staged CI, the stage taxonomy does not reduce this requirement. Passing CI preflight, core validation, or another earlier stage must not substitute for an applicable later-stage verification. Qualification for the current proposed head consists of every check that current repository authority requires and establishes as applicable at that boundary, including conditional integration and full qualification when required.

Treat check applicability as evidence with its own bindings. When a repository uses a classifier, dependency map, changed-surface rule, or equivalent mechanism to decide whether a verification applies, bind that decision to the exact relevant revision, comparison base or other declared input, classifier definition, and verification definition that produced it. A not-applicable decision is valid only when those bindings establish that the verification cannot be affected by the proposed change under current repository authority. **Not-applicable is applicability evidence, not a passing check result.**

Applicability classification must fail closed. If the relevant diff, dependency relation, classifier input, classifier definition, or verification definition is missing, unsafe, ambiguous, or cannot be established for the current candidate, treat the verification as applicable until repository authority establishes otherwise. A classifier or dependency-map change must not use the behavior it is changing to self-exempt from verification unless an independent current rule establishes that exemption. Repository policy or workflow may provide an explicit full-verification override for a qualification checkpoint.

Selective applicability must not weaken required verification. Do not use applicability classification to substitute focused diagnostic validation for required qualification or to infer that a skipped or unobserved expected check passed. Applicability classification must not suppress repository-required automatic checks contrary to the repository workflow or policy that owns those checks. A repository may itself define conditional automatic execution when the applicability decision is fail-closed and auditable.

Do not treat an expected but not yet observable check as successful, non-applicable, or absent merely because one live query returns no result. Until applicable exact-head checks have been positively identified or their non-applicability is established by current repository policy, keep merge authorization fail-closed.

If a newer applicable exact-head run supersedes an older cancelled or stale run, evaluate the newest applicable evidence rather than treating the superseded run by itself as the current result. Reuse a previously established not-applicable decision only while every fact that binds that applicability evidence remains unchanged; otherwise reclassify only the affected verification scope.
