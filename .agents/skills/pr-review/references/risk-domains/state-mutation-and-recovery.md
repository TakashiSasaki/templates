<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# State mutation and recovery

This is a **provider-neutral procedure-support reference** for `pr-review`. It broadens and falsifies candidates; semantic policy remains authoritative for findings and severity.

## Trigger

Use this domain when the change creates, replaces, deletes, migrates, publishes, rolls back, partially updates, or otherwise mutates externally meaningful state.

## State and authority model

Model pre-state, each mutation step, commit boundary, post-state, failure points, ownership of newly created state, pre-existing/concurrent state, cleanup behavior, and any compensating or rollback path.

## Candidate seeds

Generate candidates when:

- partial failure can expose an invalid intermediate state;
- rollback or cleanup can remove or overwrite state not owned by the operation;
- replacement semantics silently destroy pre-existing or concurrently created state;
- commit order can publish references before required state is durable;
- retrying a partially completed operation is not idempotent or can duplicate effects;
- recovery depends on stale observations rather than current ownership/identity.

A seed is not a finding.

## Falsification evidence

Trace actual write order, transaction/atomicity guarantees, ownership markers, idempotency rules, conflict detection, commit-boundary validation, recovery tests, and realistic concurrent actors. Discard candidates that are impossible under the operation's real mutation semantics or are contained without material impact.

## Closure

Close this domain only after success, failure, retry, and rollback paths preserve the applicable invariants and the reviewer can distinguish operation-owned state from pre-existing or concurrently created state.