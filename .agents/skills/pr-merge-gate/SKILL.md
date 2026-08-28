---
name: pr-merge-gate
description: Load the exact reviewed Policy-owned pull-request merge-gate adapter and fail closed if its immutable source cannot be verified.
---

# Pull Request Merge Gate

## Purpose

Provide a repository-local reference shim to the reviewed Policy-owned GitHub pull-request merge-gate adapter. This file does not define shared pull-request policy or duplicate the adapter's GitHub orchestration semantics.

The immutable source identity is recorded in the adjacent `source.json`. The canonical shared pull-request rules and canonical GitHub adapter live on the pinned `policy` revision named there.

## Use when

Use this shim whenever Composition work reaches pull-request merge readiness or merge execution, as routed by the repository `AGENTS.md`.

Load the canonical adapter before making any merge-readiness decision. Task-specific Composition implementation, schema, runtime, release, and validation authorities remain local to `composition` and must be satisfied before final merge authorization.

## Do not use when

Do not use this shim to:

- reconstruct merge policy from this repository's historical pull requests;
- treat this file as an independently maintained merge-policy authority;
- fall back to a mutable `policy` branch head when the pinned source cannot be loaded;
- substitute old local merge-gate prose for the exact canonical adapter;
- replace Composition-specific implementation or validation contracts.

## Canonical authorities

Read `.agents/skills/pr-merge-gate/source.json` and require all of these provenance fields:

- `repository` — canonical source repository;
- `revision` — immutable full commit SHA;
- `path` — canonical adapter path at that revision;
- `blob_sha` — expected Git blob identity of the adapter source.

Use the GitHub connector to fetch `path` from exactly `revision` in `repository`. Verify that the returned file blob SHA equals `blob_sha`. Do not resolve the source through a branch name, latest revision, historical PR body, or inferred equivalent file.

After provenance verification succeeds, load and follow the fetched canonical adapter. Its referenced `policy/pull-request/` rules are the shared normative authority. Current Composition code, schemas, validators, tests, workflows, and release contracts remain authoritative for Composition-specific semantic acceptance.

## Inputs

Before handing control to the canonical adapter, record:

1. the local `source.json` identity;
2. the fetched repository, exact revision, and source path;
3. the expected and observed adapter blob SHA;
4. whether immutable-source verification succeeded;
5. the current Composition PR number and exact head to which the adapter will be applied.

## Loading workflow

1. Read the adjacent `source.json`.
2. Validate that `schema_version` is `1`, `kind` is `policy-adapter-reference`, `revision` is a full 40-character lowercase hexadecimal SHA, and `blob_sha` is a full 40-character lowercase Git blob SHA.
3. Fetch the exact `repository` / `revision` / `path` with the GitHub connector.
4. Compare the fetched blob identity with `blob_sha`.
5. If any source field is missing, malformed, unavailable, or mismatched, stop in a blocked state and do not declare merge readiness.
6. If verification succeeds, follow the fetched canonical adapter for CI, review, base freshness, live-state, guarded merge, and post-merge verification.
7. Keep Composition-specific acceptance evidence separate from the shared Policy adapter; do not copy shared merge semantics back into this shim.

## Stop conditions

Do not declare merge readiness or execute merge if:

- `source.json` is missing or malformed;
- the exact pinned revision cannot be fetched;
- the canonical adapter path is missing at that revision;
- the fetched adapter blob SHA does not equal the pinned `blob_sha`;
- only a mutable branch or an unverified copy is available;
- the canonical adapter itself reports a blocked or unresolved gate;
- Composition-specific required acceptance evidence is incomplete.

Source unavailability is a blocked condition, not permission to reconstruct or waive the merge gate locally.

## Evidence to report

Report:

- canonical repository, revision, path, expected blob SHA, and observed blob SHA;
- immutable-source verification result;
- exact Composition PR head evaluated;
- the canonical adapter's final gate result and merge evidence;
- any separate Composition release/publication state.
