---
id: pull-request.preflight-review-acquisition
severity: mandatory
overridable: true
order: 962
---
# Preflight revision-bound review acquisition

Before intentionally requesting an independent review that is expected to cover a named pull-request head, commit, branch ref, or stacked set of revisions, refresh the live identity facts needed to construct that request and verify that every revision binding the request depends on is currently resolvable.

For a single pull request, verify that the intended reviewed commit is the current proposed head and that any branch or ref supplied to the review provider still resolves to that commit. For cumulative or whole-stack review, also verify the ordered stack membership and every explicitly bound integration-base, member-head, and tip identity needed by the review contract. If a required identity is missing, stale, moved, ambiguous, or no longer matches the intended candidate, do not invoke the reviewer with that binding; refresh the affected state and construct a corrected request first.

For descendant exact-head acceptance review, first apply the expected-invalidation gate in `pull-request.defer-revision-bound-qualification-until-required`. A resolvable construction head alone does not establish that intentionally acquiring final review is appropriate. Pending prerequisite review alone is not a prohibition; the canonical gate governs sequencing by the affected evidence bindings.

This preflight protects review acquisition from avoidable transport and identity failures. It is not completed-review evidence, does not establish merge readiness, does not weaken exact-head review requirements, and must not become a fixed waiting period or an excuse to re-read unrelated state. Naturally delayed provider execution can still fail after a correct preflight; report such provider failure separately from substantive review completion.
