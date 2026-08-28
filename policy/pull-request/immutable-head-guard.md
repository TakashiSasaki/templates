---
id: pull-request.guard-merge-against-head-movement
severity: mandatory
overridable: true
order: 980
---
# Guard merge against proposed-head movement

A merge operation performed by an automated actor must be bound to the exact proposed head commit whose current acceptance evidence was approved. Use the strongest supported immutable-head precondition so that the merge operation is rejected if the pull-request head moves between final acceptance and merge execution.

If the merge operation reports that the proposed head or repository state changed, do not retry blindly. Refresh current state and re-run the affected acceptance gates for the resulting proposed head before attempting merge again.
