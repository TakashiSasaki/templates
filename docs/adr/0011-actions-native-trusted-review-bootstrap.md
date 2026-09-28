# ADR-0011: Actions-native authenticated trusted-review bootstrap

- Status: Accepted for implementation
- Date: 2026-09-28
- Related decisions: [ADR-0008](0008-review-authority-and-github-runtime-boundary.md), [ADR-0009](0009-review-result-representation-boundary.md)

## Context

The current `pr-review` handoff correctly rejects caller-declared authentication and simulated production freeze. It cannot complete because the repository has no production provider verifier or deployment-established freeze provider. This decision selects an Actions-native trust producer and records the exact limits of that design before implementation.

The design changes provider-authentication and freeze-evidence mechanisms. It does not change review semantics, semantic policy, procedure authority, merge authorization, or the requirement that authority bytes be consumed from a read-only protected view.

## Decision

Use a workflow_dispatch workflow sourced from the repository's default branch. The workflow accepts only a validated pull-request number, reads all repository and pull-request identity fields from GitHub APIs using that run's `GITHUB_TOKEN`, and never checks out, imports, or executes proposed-head code. It verifies the selected pull request and exact base/head/tree identities again immediately before handing a result to GitHub.

The API observation is signed as an attested subject. Production verification accepts it only when GitHub Artifact Attestations validate the artifact digest and identify the expected repository, trusted workflow path, default-branch source ref, workflow revision, run ID and run attempt. The verifier also checks every identity in the signed observation against a fresh authenticated API observation. A JSON `authenticated` field is never evidence. The producer is a direct, non-reusable workflow: it records the standard workflow ref and workflow SHA claims and does not fabricate `job_workflow_ref` claims that GitHub emits only for reusable workflows. The single observation job is the attested workload boundary.

The four existing authority roles (`bootstrap_run_image`, `trusted_base_snapshot`, `runtime_image`, and `review_bundle`) are carried in a single OCI image published to GHCR. The immutable OCI manifest digest is the object identity. An Artifact Attestation binds the digest to the trusted workflow run. The reviewer executes that exact image by digest with a read-only root filesystem, no network, no added capabilities, no Docker socket, and no writable mount of authority bytes. The proposed diff is a separate data-only, read-only input; its exact head identity is checked before and after review. The image manifest contains each role's closed path/type inventory and digest so a role cannot be substituted across evidence sections.

The OCI digest is immutable with respect to content but the registry object can be deleted. Deletion or unavailability is a hard failure. No tag, artifact name, branch, mutable local cache, workflow input, or download path is an authority identity. A local OCI pull is not itself trusted: signature/provenance and manifest digest are verified before the image is run, and the runtime verifies the closed inventory before and after authority use.

This retains the ADR-0008 protected-view invariant. It does not replace an immutable local authority view with a writable workspace plus periodic digest checks. If implementation cannot execute the reviewer from a read-only container rootfs, it must fail closed.

### Trust layers

1. **Semantic review authority** remains the provider-neutral policy bound into the frozen review bundle.
2. **Authenticated provider observation** comes from GitHub API responses fetched with the run-scoped token and from an attestation verified against trusted workflow identity.
3. **Frozen review artifacts** are the four role inventories inside the digest-addressed OCI image, authenticated by Artifact Attestation.
4. **Reviewer workload identity** is the GitHub Actions OIDC identity represented by the attestation's issuer, repository and owner IDs, workflow path and revision, event, run, and attempt. The one trusted observation job is selected by the pinned workflow revision; reusable-workflow claims are not used.
5. **Review submission transport** uses a separate minimal-privilege job and the repository-scoped `GITHUB_TOKEN`; GitHub's `github-actions[bot]` identity is the transport actor.
6. **Merge authorization** remains a separate human/repository gate. Neither a successful workflow nor a submitted review authorizes merge.

### Replay and freshness

Observation, attestation, OCI image, handoff and reviewer packet are bound to repository numeric ID and `nameWithOwner`; pull-request numeric and node IDs; exact base commit and tree; exact proposed head and tree; workflow revision; event; run ID and attempt; and the digest of each role inventory. A replay with a different repository, pull request, base, head, workflow, run or artifact digest is rejected. Immediately before review submission, the workflow fetches these identities again and requires exact equality. Any movement discards the run and requires a fresh workflow dispatch.

### Threat model

| Input or actor | Trust treatment and required guard |
| --- | --- |
| Malicious or untrusted PR author | Controls proposed files, metadata, commit messages and patch bytes. All remain review data. No PR code or workflow is executed. |
| Proposed-head workflow/tooling/policy/lock changes | Untrusted data only; all executable authority and policy are selected from exact trusted base/workflow revisions. |
| Forged observation JSON or `authenticated: true` | Rejected unless its digest has a valid attestation from the pinned trusted workflow and all fields match fresh API responses. |
| Observation replay across PRs, repositories, base/head or runs | Rejected by numeric repository/PR identities, exact commit/tree identities, workflow revision, run ID/attempt and subject digest. |
| Stale base/head or mutable Git ref | Full commit and tree IDs are resolved through authenticated API and Git objects; live identity is refreshed before submission. No branch name is authority. |
| Git replacement objects or hostile Git configuration | Bootstrap uses isolated Git configuration, disables replacement refs and hooks, resolves full object IDs, and verifies commit/tree object identities. |
| Mutable runtime cache | Cache is a hint only. It is ignored as authority and every selected byte is checked against the OCI manifest inventory and attestation. |
| Artifact replacement, digest substitution, cross-job confusion | Consume one role-indexed OCI image only by its verified manifest digest. Validate role labels and inventories. Missing/deleted objects fail closed. |
| Fork PR | API observation may be read-only. No fork-controlled code runs with credentials. Review write permission exists only in a separate submit job after successful verification. |
| Privileged workflow injection or attacker-controlled text | Only default-branch workflow code is trusted. Parse PR number as an integer; pass data through files/API bodies, never interpolated shell. No `pull_request_target` or `workflow_run`. |
| Concurrent head movement | Re-fetch immediately before submission; mismatch invalidates the completed analysis and blocks posting. |
| Repository maintainer or default-branch workflow compromise | In scope as root trust. Repo administrators who can change the trusted default-branch workflow or attestation policy can authorize a different producer; auditability and explicit revision binding make that change visible but do not defend against an authorized owner. |

### Alternative evaluation

| Alternative | Trust properties and disposition |
| --- | --- |
| Actions-native (`GITHUB_TOKEN`, OIDC, Artifact Attestations, GHCR OCI) | Satisfies repository-scoped API access, ephemeral workload identity, provenance binding, content-addressed image identity, and read-only local execution. Selected. A workflow default-branch trust root is accepted and auditable. |
| Dedicated GitHub App | Could supply a distinct API principal, but adds no required provenance or freeze property: OIDC/attestation already authenticates the workflow and `GITHUB_TOKEN` can read PRs and submit reviews. The app would not make a writable workspace immutable. Not required. |
| External trust/freeze service | Could supply independent signing and immutable storage, but introduces an operator-managed trust relationship and service without satisfying a property unavailable from Actions-native attestation plus digest-addressed OCI and read-only execution. Not selected. |

## Consequences

- The GitHub-specific producer, verifier and submission transport remain in the platform adapter. GitHub event names, claims and review payloads do not enter semantic policy.
- Workflow permissions must be explicit and job-scoped. The observation job needs `contents: read`, `pull-requests: read`, `id-token: write`, and `attestations: write`; only the OCI publisher needs `packages: write`, `id-token: write`, and `attestations: write`; only the submit job needs `pull-requests: write`. Do not grant `artifact-metadata: write` because linked artifact storage records are not part of the trust contract.
- Review execution receives no GitHub token. Its OCI rootfs is read-only, networking is disabled, and proposed-head material is a read-only data mount.
- `github-actions[bot]` is technically able to submit a pull-request review with `pull-requests: write`. Repository policy accepts a distinct review system when the implementing actor cannot self-review; the Actions workload is separate from the PR author. The semantic conclusion remains owned by the frozen procedure and policy, not the bot account.
- GitHub-hosted workflow execution is required for deployment qualification. Local tests can qualify rejection behavior but cannot establish deployed OIDC, attestation, registry, token-permission or bot-review behavior.
- The first deployment is a bootstrap transition: the new infrastructure may not formally accept its own unreviewed implementation. Independent review of its exact PR stack and authorized merge must occur before the first production run. No PR is merged by this change.
