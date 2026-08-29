---
id: pull-request.refresh-live-state-before-merge
severity: mandatory
overridable: true
order: 978
---
# Refresh mutable live state and validate evidence bindings before merge

Immediately before authorizing or executing a pull-request merge, refresh the mutable repository state that can invalidate the accepted snapshot, including the current proposed head, current target-branch head, current review state, unresolved review-thread state, and current mergeability. Validate that relied-upon scope, exact-head validation, and completed review evidence are still bound to the resulting current state.

Do not unconditionally reacquire exact-head validation, completed review, or scope evidence whose binding facts remain unchanged and whose continued validity is established by current policy. Re-evaluate only the acceptance evidence affected by a changed head, target branch, scope, validation definition, review state, thread state, mergeability state, or other concrete invalidation signal.

If a required current value is missing, stale, materially different, or cannot be reconciled to the accepted evidence, leave merge authorization blocked and reacquire the affected evidence.
