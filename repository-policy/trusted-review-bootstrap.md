# Trusted review bootstrap contract

This repository uses the Actions-native producer defined by
[ADR-0011](../docs/adr/0011-actions-native-trusted-review-bootstrap.md). This
contract applies to authenticated provider observation and freeze evidence only.
It does not define review semantics, merge authorization, or generic provider
review-result meanings.

## Provider observation

The authenticated observation is produced by a workflow from the trusted
default branch. It includes numeric repository ID and `nameWithOwner`, numeric
and node pull-request IDs, PR number, base commit/tree, head commit/tree, API
retrieval time, workflow path/revision, event, run ID, run attempt, and OIDC
identity. The producer reads identity fields from GitHub's API using the
run-scoped `GITHUB_TOKEN`; caller input is only a strictly parsed PR number.

The observation's canonical bytes are an Artifact Attestation subject. The
verifier checks the attestation issuer and signer workflow identity and compares
the attested digest to the exact observation bytes. It then refreshes GitHub API
identity and compares every repository, PR, base, head and tree field. The
producer, verifier and submission workflow must all agree on the exact
repository, workflow path, source ref, workflow revision and run identity.
Observation JSON fields, including any `authenticated` flag, never authenticate
themselves.

## Freeze evidence

The authoritative object is one GHCR OCI image pinned by manifest digest. It
contains four separately named roles and a closed inventory for each role:
`bootstrap_run_image`, `trusted_base_snapshot`, `runtime_image`, and
`review_bundle`. Each inventory records canonical path, regular-file type and
SHA-256; links and special files are rejected. Each role record binds its role
name, inventory digest and semantic identity to the same OCI manifest digest.

The workflow attests the image digest. The verifier requires Artifact
Attestation provenance from the expected default-branch workflow and checks the
repository ID, immutable workflow subject, workflow revision, event, run ID,
attempt and job identity. Evidence binds the same authenticated provider
observation digest and exact repository, PR, base/head commit and tree identities.
Post-freeze verification rechecks the OCI manifest and role inventories before
and after use. Missing, expired, deleted, unverifiable, cross-role, or mismatched
objects fail closed.

The reviewer executes the exact attested OCI image by digest with a read-only
root filesystem and no network, added capabilities, privileged mode, Docker
socket, or writable authority mount. The proposed head is supplied only as a
separate read-only data input and is never executed. Local copies and caches are
not authorities. A writable workspace followed only by digest checks is not an
acceptable substitute for the protected execution view.

## Submission and merge boundary

Review analysis has no GitHub credential. A separate submission job receives
only `pull-requests: write` after final live identity revalidation and sends the
frozen procedure's semantic result through GitHub's review API as
`github-actions[bot]`. The bot is transport identity, not semantic authority.
The automated review system is independent of a PR author when the trusted
workflow and verifier run from the repository's default branch, do not execute
author-controlled code, and bind the exact input and authority digests. Review
submission does not authorize merge.
