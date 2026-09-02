<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Concurrency and temporal consistency

This is a **provider-neutral procedure-support reference** for `pr-review`. It supports candidate discovery and falsification; semantic policy remains the authority for findings.

## Trigger

Use this domain when a correctness, safety, identity, ownership, authorization, existence, version, or resource decision depends on mutable state that can change before or during the operation that relies on it.

## State and authority model

Model the sequence `observe -> decide -> mutable interval -> act -> commit/use`. Identify every actor capable of changing material state during the interval and whether the operation relies on a stable resource identity, atomic primitive, transaction, serialization mechanism, version guard, or commit-boundary revalidation.

## Candidate seeds

Generate candidates when:

- a check and the dependent operation are separable while another actor can change the checked state;
- existence/non-existence, ownership, version, or authority is assumed to persist without protection;
- two workers can both pass a precondition and then collide or duplicate effects;
- retry/recovery races with an in-flight or concurrently completed operation;
- a cached decision remains valid after the state version or effective target changes.

A seed is not a finding.

## Falsification evidence

Construct a realistic interleaving and then try to prove it impossible. Use actual atomicity guarantees, stable identities/handles, serialization/locking, compare-and-set/version semantics, transaction isolation, idempotency, revalidation, actor capabilities, and exact-head tests. Discard candidates whose harmful interleaving cannot occur.

## Closure

Close this domain only after every material decision-to-use interval either has no relevant concurrent mutator or is protected so the decision remains valid at the effective operation boundary.