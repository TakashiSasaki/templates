# Trusted review bootstrap contract

This repository uses the Actions-native producer defined by
[ADR-0011](../docs/adr/0011-actions-native-trusted-review-bootstrap.md). This
contract applies to authenticated provider observation and freeze evidence only.
It does not define review semantics, merge authorization, or generic provider
review-result meanings.

## Provider observation

The authenticated observation is produced by a direct, non-reusable workflow
from the trusted default branch. It includes numeric repository ID and
`nameWithOwner`, numeric and node pull-request IDs, PR number, base commit/tree,
head commit/tree, API retrieval time, workflow path/revision, event, run ID, run
attempt, and OIDC identity. It does not synthesize reusable-workflow claims.
The producer reads identity fields from GitHub's API using the
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

The bootstrap retrieves the exact attested OCI image by digest and extracts its
roles; it does not execute the image as a reviewer container. Each materialized
role backing tree and each exposed role view must be mounted read-only. A
read-only bind view over a writable backing directory does not qualify; the
verifier checks both mount points and confirms the view aliases its declared
backing tree. The proposed head is supplied only as a separate read-only data
input and is never executed. Local copies and caches are not authorities. A
writable workspace followed only by digest checks is not an acceptable
substitute for the protected role views.

The durable handoff contains no producer-runner absolute paths. A reviewer on a
fresh runner verifies the handoff, provider-observation, and freeze-evidence
attestations against the original workflow run; rechecks the exact repository,
pull request, base, and head through GitHub's API; and pulls the image only by
its manifest digest. It validates the role inventories and semantic identities
before materializing new backing trees and protected views. The resulting
reviewer-local-view session binds the exact handoff digest, evidence digests,
OCI identity, role identities, and local paths. It is ephemeral and is never
uploaded with the durable handoff packet. The bootstrap workflow validates and
prepares authority but does not run review analysis or establish a read-only
container root filesystem, network isolation, or a sandboxed reviewer process.
Any later analysis executor must consume only the verified protected paths,
keep credentials outside analysis, and qualify process and network isolation
separately before those properties can be claimed.

The workflow's portability check first unmounts and deletes producer-local role
paths, then hydrates into a different temporary root. This check is in the same
workflow job; an independent later reviewer must run the hydrator with its own
API and GHCR credentials against the uploaded durable files.

## Submission and merge boundary

Review analysis has no GitHub credential. A separate submission job receives
only `pull-requests: write` after final live identity revalidation and sends the
frozen procedure's semantic result through GitHub's review API as
`github-actions[bot]`. The bot is transport identity, not semantic authority.
The automated review system is independent of a PR author when the trusted
workflow and verifier run from the repository's default branch, do not execute
author-controlled code, and bind the exact input and authority digests. Review
submission does not authorize merge.
