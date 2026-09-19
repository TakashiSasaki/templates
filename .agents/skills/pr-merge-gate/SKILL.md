---
name: pr-merge-gate
description: Load the exact immutable Policy-owned pull-request merge-gate adapter for Modeling maintenance.
---

# Pull Request Merge Gate

This thin Modeling-local shim is only a reference to the shared Policy-owned
gate. Verify the adjacent `source.json`, fetch the exact revision/path, and
compare the observed blob before loading it. Missing or mismatched source is
blocked; a mutable `policy` branch or local copy is not a fallback.

Use the gate after Modeling-specific record, catalog, generation, and
qualification evidence is complete. CI and review remain separate evidence
layers, and review or green CI does not authorize merge. This shim does not
restate shared semantics or authorize Integration/Site adoption or deployment.

Require schema version 2 and the explicit immutable `closure` of the selected
pull-request profile, its rules, and gate references. Verify every closure
path/blob at the declared revision before loading the gate.
