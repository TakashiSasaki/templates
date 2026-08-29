---
id: pull-request.verify-target-branch-head-freshness
severity: mandatory
overridable: true
order: 960
---
# Evaluate merge readiness against the current target branch HEAD

Before declaring a pull request merge-ready, establish the current target branch full commit SHA and evaluate the proposed change against that exact target state. If the proposed head is not based on the current target head, inspect the intervening target change and determine whether it affects scope, validation applicability, review conclusions, mergeability, or another acceptance condition.

Synchronize or rebuild the proposed head only when that impact evaluation or current repository policy requires it. Do not require proposed-head synchronization solely because the target branch moved when the intervening change is established not to invalidate the applicable acceptance evidence.

Target-branch movement invalidates the freshness decision itself, but it does not by itself invalidate unrelated exact-head CI or review evidence. Do not claim target-branch freshness from cached, historical, or inferred branch metadata.
