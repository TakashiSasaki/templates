---
id: pull-request.select-review-scope-from-current-bindings
severity: mandatory
overridable: true
order: 961
---
# Select review scope from current bindings

Select review work from the requested purpose, exact candidate bindings, explicit
coverage, known findings, and the authority-owned impact closure. `whole-stack` is
a scope description, not a review-count allowance and not an instruction to read
all five authority branches for every task.

Before acquiring review, establish the smallest scope that is supported by current
evidence. Reuse an existing completed result only when its purpose, candidate
binding, review contract, independence, completion state, and explicit coverage
cover every required member and invariant. A missing head, unknown scope,
partial or failed result, incomplete pagination, missing metadata, or unknown
applicability is not completed coverage.

Do not acquire the same objective, purpose, candidate, scope, contract, and input
binding twice. In other words, the duplicate key is the same objective, purpose, candidate, scope, contract, and input binding. If an equivalent request is in progress or its submission result is
unknown, reconcile the provider state and existing handle before considering a new
request. A request key is a comparison aid, not a provider idempotency guarantee;
when action ownership or serialized submission cannot be established, preserve the
uncertainty and hand off safely.

For a bounded local change, acquire an independent exact-head review of the change
and its affected closure when no applicable result covers it. A new head does not
automatically require a whole-stack audit. If a shared contract, trust boundary,
dependency topology, cross-member interaction, or unbounded/unknown impact is
changed, expand to the related stack and record the reason. Unknown impact remains
unknown until the required authority-owned inspection or review resolves it.

Additional diagnostic or whole-stack review is permitted when important new
evidence, an incomplete prior result, a changed contract, or newly uncovered scope
justifies it. There is no global numeric cap and no universal rule that forces every
post-review change into targeted-only coverage. Cost, elapsed time, line count,
green tests, or a warning threshold may be reported but never establishes a waiver.

The planner is not a semantic validator, reviewer, merge gate, or authorization
issuer. It must use the formal authority validation and the shared
`pr-merge-gate` for those decisions. A diagnostic result remains separate from
independent exact-head merge-acceptance evidence.
