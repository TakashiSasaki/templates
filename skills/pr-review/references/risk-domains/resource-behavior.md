<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Resource behavior

This is a **provider-neutral procedure-support reference** for `pr-review`. It supports candidate discovery and falsification; semantic performance/resource policy remains authoritative.

## Trigger

Use this domain when work, memory, storage, descriptors/handles, processes, requests, retries, queues, recursion, fan-out, buffering, retained state, or cleanup can scale with input, history, concurrency, or failure.

## State and authority model

Model the resource unit, who controls its growth, amplification factor, lifetime, release/cleanup path, concurrency multiplier, retry/backoff behavior, quota/bound, and failure behavior when the resource is exhausted.

## Candidate seeds

Generate candidates when:

- attacker/user-controlled input can amplify work or retained state disproportionately;
- retries or fan-out multiply requests/work without a hard bound or cancellation path;
- error/early-return paths leak resources or retain unbounded state;
- buffering/materialization converts a streaming/bounded path into whole-input growth;
- concurrency removes a previous effective bound;
- cleanup or compaction depends on successful completion and is skipped on persistent failure.

A seed is not a finding.

## Falsification evidence

Quantify or bound the relevant growth using actual limits, lifecycle behavior, cancellation/cleanup, backpressure, quotas, complexity, realistic workload/input control, and measurements/tests when available. Discard speculative performance candidates without a reachable material resource consequence.

## Closure

Close this domain only after material resource growth and lifetime are bounded or deliberately controlled for realistic inputs, concurrency, retries, and failure paths, with evidence sufficient under the semantic review policy.