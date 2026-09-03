---
id: pull-request.require-explicit-stacked-review-coverage
severity: mandatory
overridable: false
order: 955
---
# Bind cumulative review evidence to an ordered pull-request stack

When a completed review is claimed to cover multiple members of a stacked pull-request topology, acceptance evidence must bind to the integration base exact SHA and tree, the ordered stack membership, each member exact head SHA, the stack tip exact SHA, the cumulative reviewed scope, the review contract, reviewer independence, the review completion state, and material limitations.

A review event, approval state, or tip-only review must not establish acceptance coverage for lower stack members by inference. Each covered member must be identifiable from explicit cumulative coverage evidence. Missing, ambiguous, or provider-only coverage is incomplete evidence and keeps merge authorization fail-closed.

Evaluate applicability again when a member exact head changes, stack ordering changes, integration base changes, cumulative scope changes, or the review contract changes. Reuse unchanged evidence only when its bindings and remaining stack applicability are established; if applicability is unknown, fail closed. A lower member merge may move a later member's base without mechanically invalidating all evidence, but the changed bindings and remaining coverage must be evaluated before relying on it.
