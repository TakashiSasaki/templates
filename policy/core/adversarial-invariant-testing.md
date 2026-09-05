---
id: testing.require-adversarial-invariant-coverage
severity: mandatory
overridable: true
order: 310
---
# Test material invariants beyond the nominal path

When a change relies on a structured contract, mutable lifecycle, asynchronous completion, relation set, identity mapping, generated projection, resource boundary, or effective containment boundary, identify the material invariants that make the changed behavior correct and add focused adversarial coverage for the applicable negative, transition, stale-state, malformed-input, converse/completeness, or boundary cases.

Derive the cases from the changed invariant rather than from a fixed universal matrix. Do not require unrelated combinations, speculative stress cases, or exhaustive permutations when they do not exercise a material failure mode. A focused test may be unit-, integration-, system-, or workflow-level as long as it reaches the layer where the invariant can actually fail.

When a defect or review finding proves that one dimension of an invariant was previously unguarded, inspect the bounded sibling dimensions that share the same root cause before declaring the repair complete. Examples include success versus failure completion, current versus stale context, listed relation versus required converse, missing versus extra structured fields, and nominal outer bound versus effective inner containment boundary. Add regression evidence for sibling cases that are materially reachable; do not broaden the change into unrelated cleanup.
