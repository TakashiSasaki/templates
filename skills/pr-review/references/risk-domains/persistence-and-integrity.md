<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Persistence and integrity

This is a **provider-neutral procedure-support reference** for `pr-review`. It supports candidate discovery and falsification; semantic policy remains authoritative.

## Trigger

Use this domain when durable records, schemas, serialization formats, indexes, identifiers, migrations, caches treated as authority, or other persisted state can change.

## State and authority model

Model the persisted representation, logical invariant, readers and writers, version/schema transitions, uniqueness and referential constraints, commit ordering, migration/recovery behavior, and any derived state that consumers treat as authoritative.

## Candidate seeds

Generate candidates when:

- a writer can persist a state that a valid reader cannot interpret consistently;
- migration loses, aliases, duplicates, truncates, reorders, or silently reclassifies meaningful data;
- uniqueness/referential invariants are enforced only in one caller rather than at the authoritative boundary;
- partial persistence or crash recovery can expose mixed schema/version states;
- derived or cached state can be mistaken for fresher canonical state;
- serialized identity or authority information can be replayed after its validity changes.

A seed is not a finding.

## Falsification evidence

Trace writer/reader compatibility, authoritative constraints, transaction boundaries, migration proofs/tests, recovery paths, version checks, canonicalization, exact-head fixtures, and realistic stored inputs. Discard candidates when the persisted state cannot violate an applicable invariant or all consumers safely reject/handle the transition.

## Closure

Close this domain only after durable success, failure, migration, retry, and readback behavior preserve the required logical invariants across the actual consumers of the persisted state.