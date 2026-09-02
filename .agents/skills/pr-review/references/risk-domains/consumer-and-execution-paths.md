<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Consumer and execution paths

This is a **provider-neutral procedure-support reference** for `pr-review`. It supports candidate discovery and falsification; semantic policy remains authoritative.

## Trigger

Use this domain when correctness depends on how unchanged or downstream consumers interpret, load, execute, publish, deserialize, route, or otherwise use changed outputs, interfaces, configuration, metadata, generated artifacts, or persisted state.

## State and authority model

Model producer output, transformation/publication steps, actual consumer input, consumer interpretation/execution path, fallback behavior, and the observable effect. Keep unchanged consumers as review context; do not expand the changed surface merely because tracing them is necessary.

## Candidate seeds

Generate candidates when:

- producer-side validation/tests do not exercise what a real consumer actually receives;
- a generated, packaged, published, serialized, or routed representation differs from the source representation being reviewed;
- a consumer has fallback/default behavior that changes semantics when new data is absent, malformed, unknown, or reordered;
- a contract change is locally coherent but incompatible with realistic callers/readers;
- an authority or security decision occurs in one layer but the effective operation occurs in another consumer layer;
- documentation or metadata claims a path that the actual consumer does not follow.

A seed is not a finding.

## Falsification evidence

Trace at least one realistic downstream path far enough to establish or falsify the candidate. Use actual consumer code/configuration, generated/package bytes, integration tests, schemas/contracts, publication mappings, and reachable fallbacks. Discard candidates contradicted by the real consumer path.

## Closure

Close this domain only after material changed outputs are traced to the consumers needed to establish the relevant invariant, and the reviewer can explain the actual effective behavior rather than only producer-local intent.