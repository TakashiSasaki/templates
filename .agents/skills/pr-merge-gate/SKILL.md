---
name: pr-merge-gate
description: Load the exact immutable Policy-owned pull-request merge-gate adapter for Integration maintenance.
---

# Pull Request Merge Gate

This thin Integration-local shim does not define shared pull-request policy.
Read the adjacent `source.json`, verify its full revision and blob identity,
and load `skills/pr-merge-gate/SKILL.md` from exactly that snapshot. Do not
fall back to a mutable `policy` branch or historical copy; source failure is
blocked.

Use this gate after Integration-specific provider, Bundle, receipt, and
qualification evidence is established. Keep CI and review evidence separate,
and keep Site adoption, publication, deployment, and external authorization
as distinct boundaries. A green check or absent review list is not acceptance
evidence. This shim does not authorize merge by itself.

Require schema version 2 and the explicit immutable `closure` of the selected
pull-request profile, its rules, and gate references. Verify every closure
path/blob at the declared revision before loading the gate.
