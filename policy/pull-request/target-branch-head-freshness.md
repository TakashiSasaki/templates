---
id: pull-request.verify-target-branch-head-freshness
severity: mandatory
overridable: true
order: 960
---
# Verify merge readiness against the current target branch HEAD

Before declaring a pull request merge-ready, establish the current target branch full commit SHA and confirm that the proposed head is based on, or has been explicitly synchronized with, that target branch HEAD.

If the target branch moves after acceptance evidence was collected, inspect the intervening change and re-evaluate the evidence whose applicability or semantic basis could be affected. Target-branch movement is an invalidation signal for the freshness decision, not an automatic reason to discard unrelated exact-head CI or review evidence. Do not claim target-branch freshness from cached, historical, or inferred branch metadata.
