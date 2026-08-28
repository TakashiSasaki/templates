---
id: pull-request.require-current-mergeability
severity: mandatory
overridable: true
order: 976
---
# Require current mergeability before merge

Immediately before merge authorization, verify from current repository state that the pull request can be merged. Historical mergeability, conflict-free status observed for an older head, or an earlier successful dry run must not substitute for the current state.

If mergeability is unknown, false, or changes before the merge operation completes, keep or return merge authorization to a blocked state and refresh the relevant current evidence before attempting merge again.
