---
id: pull-request.refresh-live-state-before-merge
severity: mandatory
overridable: true
order: 978
---
# Refresh live acceptance state immediately before merge

Immediately before authorizing or executing a pull-request merge, refresh the current proposed head, current target-branch head, applicable exact-head validation state, completed review evidence, unresolved review-thread state, effective change scope, and current mergeability.

Do not authorize merge from a previously accepted snapshot when any refreshed value is missing, stale, or materially different. If the proposed head or target branch moved, or if validation, review, scope, thread, or mergeability state changed, re-evaluate the affected acceptance evidence before merge.
