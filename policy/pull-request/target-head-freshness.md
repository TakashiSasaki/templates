---
id: pull-request.verify-target-head-freshness
severity: mandatory
overridable: true
order: 960
---
# Verify merge readiness against the current target branch

Before declaring a pull request merge-ready, fetch the current target branch full commit SHA and confirm that the proposed head is based on, or has been explicitly synchronized with, that state. If the target branch moves after validation or review evidence was collected, treat prior merge-readiness evidence as stale until the impact is re-evaluated. Do not claim target-branch freshness from cached, historical, or inferred branch metadata.
