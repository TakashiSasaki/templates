---
id: pull-request.guard-merge-against-head-movement
severity: mandatory
overridable: true
order: 980
---
# Guard merge against proposed-head movement

When executing a pull-request merge, bind the operation to the exact proposed head commit whose current acceptance evidence was approved, using the strongest supported immutable-head precondition available on the execution surface. The merge must not silently apply to a different head that appeared after final acceptance.

If the merge surface cannot enforce an immutable proposed-head precondition, treat that limitation as part of the final acceptance risk: refresh current state immediately before execution and verify the result afterward rather than assuming the earlier accepted snapshot is still current.

If the merge operation reports that the proposed head or repository state changed, do not retry blindly. Refresh current state and re-run the affected acceptance gates for the resulting proposed head before attempting merge again.
