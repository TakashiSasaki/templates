<!--
agent-policy-generated: true
source-skill: audit-frozen-change
DO NOT EDIT DIRECTLY
-->
---
name: audit-frozen-change
description: Audit a bounded change against its agreed acceptance baseline without inventing new gates or conflating evidence layers.
---

# Audit a frozen change

Use this skill when implementation is complete or paused and the task requires a bounded regression, closeout, or acceptance audit.

1. Identify the exact revision or artifact under review and the frozen change contract: requested outcome, allowed changes, preserved invariants, non-goals, completion criteria, required evidence, residual-risk expectations, and stop condition.
2. State the root of trust and the independent evidence available. Do not recurse indefinitely into proofs of proofs; use the declared stop condition.
3. Inspect the final diff or artifact inventory and classify every change as intended, derived, incidental, or unexplained.
4. Evaluate regressions only against the preserved invariants and agreed scope. Do not retroactively introduce a new completion gate.
5. Bind every command, report, CI result, and review to the exact revision or artifact it covers.
6. Report repository-local checks, environment-dependent checks, remote CI, and independent audit separately. Pending, skipped, stale, inferred, or unavailable evidence is not a pass.
7. For every regression, record the immediate correction, the generalized rule, the appropriate policy destination, and the verification that detects recurrence.
8. Identify unresolved owner decisions instead of guessing about behavior, data meaning, compatibility, architecture, risk, or scope.
9. State residual risks and whether each is accepted, deferred to a named future unit, or blocks completion.
10. Stop when the frozen criteria have been evaluated. Rebaseline only after explicit authorization and record its effect on prior work and evidence.

Use this report structure unless the repository defines a stricter one:

- Regression
- Immediate correction
- Generalized rule
- Policy destination
- Verification
- Residual risk
- Completion or stop decision

Do not modify the audited implementation, publish changes, or expand the task while performing a read-only audit unless repair was explicitly requested as a separate operation.
