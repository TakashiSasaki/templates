# ADR-0011: Actions-native authenticated trusted-review bootstrap

- Status: Accepted for implementation
- Date: 2026-09-28
- Related decisions: [ADR-0008](0008-review-authority-and-github-runtime-boundary.md), [ADR-0009](0009-review-result-representation-boundary.md)

## Context

The current `pr-review` handoff correctly rejects caller-declared authentication and simulated production freeze. It cannot complete because the repository has no production provider verifier or deployment-established freeze provider. This decision selects an Actions-native trust producer and records the exact limits of that design before implementation.

The design changes provider-authentication and freeze-evidence mechanisms. It does not change review semantics, semantic policy, procedure authority, merge authorization, or the requirement that authority bytes be consumed from a read-only protected view.

## Decision

Use a workflow_dispatch workflow sourced from the repository's default branch. The workflow accepts only a validated pull-request number, reads all repository and pull-request identity fields from GitHub APIs using that run's `GITHUB_TOKEN`, and never checks out, imports, or executes proposed-head code. It verifies the selected pull request and exact base/head/tree identities again immediately before handing a result to GitHub.

The API observation is signed as an attested subject. It records the pull request's base ref and accepts only `policy` as the target authority branch. Production verification accepts it only when GitHub Artifact Attestations validate the artifact digest and identify the expected repository, trusted workflow path, default-branch source ref, workflow revision, run ID and run attempt. The verifier also checks every identity in the signed observation, including the base ref, against a fresh authenticated API observation. A JSON `authenticated` field is never evidence. The producer is a direct, non-reusable workflow: it records the standard workflow ref and workflow SHA claims and does not fabricate `job_workflow_ref` claims that GitHub emits only for reusable workflows. The workflow has one fixed job, `bootstrap`; the attested observation records the runner-provided `GITHUB_JOB` value, and the verifier requires that exact job identity together with the attested workflow revision and run. GitHub does not expose a separate reusable-workflow job claim for direct workflows, so adding jobs or changing this job identity requires a reviewed workflow revision change.

The workflow attests the aggregate OCI image, pulls it by digest, extracts its four roles, mounts each role read-only, and checks each closed inventory. Only after that protected-view verification succeeds does it write and attest the freeze-evidence JSON. Those evidence bytes bind the target PR identity, all four role inventories and their semantic identities, the OCI manifest digest, and the completed protected-view verification. The verifier checks a GitHub Artifact Attestation over the exact evidence-file digest as well as the provenance attestation over the OCI image digest. A caller cannot copy a valid image attestation and invent different target or role claims around it. The handoff records the evidence-file digest and its independent verifier checks the exact bytes and protected inventories again before and after handoff use. Any later reviewer must also recheck its own read-only image view before and after review analysis; the bootstrap's successful handoff does not claim that review analysis has already run.

The four existing authority roles (`bootstrap_run_image`, `trusted_base_snapshot`, `runtime_image`, and `review_bundle`) are carried in a single OCI image published to GHCR. The immutable OCI manifest digest is the object identity. An Artifact Attestation binds the digest to the trusted workflow run. The bootstrap retrieves that exact image by digest and extracts the roles; it does not execute the OCI image as a reviewer container. Each materialized role backing tree and each exposed role view must be mounted read-only; a read-only bind view over a writable backing directory does not satisfy this invariant. The verifier checks that each exposed view aliases its declared backing tree and validates the closed inventory through both paths. The proposed diff is a separate data-only, read-only input; its exact head identity is checked before and after review. The image manifest contains each role's closed path/type inventory and digest so a role cannot be substituted across evidence sections.

The OCI digest is immutable with respect to content but the registry object can be deleted. Deletion or unavailability is a hard failure. No tag, artifact name, branch, mutable local cache, workflow input, or download path is an authority identity. A local OCI pull is not itself trusted: signature/provenance and manifest digest are verified before roles are extracted, and the verifier checks the closed inventory before and after authority use.

The durable handoff contains no producer-runner absolute filesystem paths. The uploaded packet consists of the attested handoff and reviewer packet plus the provider observation and freeze evidence. A reviewer on another runner verifies the producer run and all file attestations, rechecks the repository and pull request identities through the GitHub API, verifies the evidence and OCI attestations, then pulls the image only by its manifest digest. It checks each role's inventory and semantic identity before creating a fresh local read-only backing tree and exposed view. Both mounts must be read-only and the view must alias its backing tree.

After hydration, the verifier writes an ephemeral reviewer-local-view session. It binds the exact SHA-256 of the durable handoff bytes, provider-observation and freeze-evidence digests, OCI manifest digest, role inventory and identity digests, and fresh local view/backing locators. The session is consumed only on that machine and is never included in the uploaded artifact. A changed handoff, evidence file, role, or local mount invalidates the session or fails verification.

Before the workflow's portability check, it unmounts and removes all producer-local protected role paths, then hydrates into a different temporary root. This prevents the check from accidentally succeeding through the old locators. That self-check runs in the same workflow job; a later independent review runner must invoke the same hydrator against the uploaded durable files and establish its own API/GHCR credentials.

This retains the ADR-0008 protected-view invariant. It does not replace an immutable local authority view with a writable workspace plus periodic digest checks. This implementation qualifies the read-only role backing trees and exposed views; it does not establish a read-only OCI container root filesystem, network isolation, or a sandboxed reviewer process. The bootstrap workflow validates and prepares authority but does not run review analysis. Any later review executor must consume only the verified protected paths, keep credentials outside analysis, and qualify its process/network isolation separately before those properties can be claimed.

### Trust layers

1. **Semantic review authority** remains the provider-neutral policy bound into the frozen review bundle.
2. **Authenticated provider observation** comes from GitHub API responses fetched with the run-scoped token and from an attestation verified against trusted workflow identity.
3. **Frozen review artifacts** are the four role inventories inside the digest-addressed OCI image, authenticated by Artifact Attestation.
4. **Reviewer workload identity** is the GitHub Actions OIDC identity represented by the attestation's issuer, repository and owner IDs, workflow path and revision, event, run, and attempt. The one trusted observation job is selected by the pinned workflow revision; reusable-workflow claims are not used.
5. **Review submission transport** uses a separate minimal-privilege job and the repository-scoped `GITHUB_TOKEN`; GitHub's `github-actions[bot]` identity is the transport actor.
6. **Merge authorization** remains a separate human/repository gate. Neither a successful workflow nor a submitted review authorizes merge.

The workflow-dispatch actor is recorded in the attested provider observation and compared with the pull-request author returned by the authenticated API. A dispatch by the PR author is rejected by stable actor ID and login. Workflow re-runs (`run_attempt` greater than one) are rejected; a fresh dispatch is required. This preserves an independent trigger boundary in addition to the distinct `github-actions[bot]` transport account.

### Replay and freshness

Observation, attestation, OCI image, handoff and reviewer packet are bound to repository numeric ID and `nameWithOwner`; pull-request numeric and node IDs; PR author identity; workflow-dispatch actor identity; the exact `policy` base ref, commit and tree; exact proposed head and tree; workflow revision; event; run ID and attempt; and the digest of each role inventory. A replay with a different repository, pull request, author, dispatcher, base ref, base commit/tree, head, workflow, run or artifact digest is rejected. Immediately before review submission, the workflow fetches these identities again and requires exact equality. Any movement discards the run and requires a fresh workflow dispatch.

### Threat model

| Input or actor | Trust treatment and required guard |
| --- | --- |
| Malicious or untrusted PR author | Controls proposed files, metadata, commit messages and patch bytes. All remain review data. No PR code or workflow is executed. |
| Proposed-head workflow/tooling/policy/lock changes | Untrusted data only; all executable authority and policy are selected from exact trusted base/workflow revisions. |
| Forged observation JSON or `authenticated: true` | Rejected unless its digest has a valid attestation from the pinned trusted workflow and all fields match fresh API responses. |
| Observation replay across PRs, repositories, actors, base/head or runs | Rejected by numeric repository/PR identities, author/dispatch actor identity, exact commit/tree identities, workflow revision, run ID/attempt and subject digest. |
| Stale base/head or mutable Git ref | Full commit and tree IDs are resolved through authenticated API and Git objects; live identity is refreshed before submission. No branch name is authority. |
| Git replacement objects or hostile Git configuration | Bootstrap uses isolated Git configuration, disables replacement refs and hooks, resolves full object IDs, and verifies commit/tree object identities. |
| Mutable runtime cache | Cache is a hint only. It is ignored as authority and every selected byte is checked against the OCI manifest inventory and attestation. |
| Artifact replacement, digest substitution, cross-job confusion | Consume one role-indexed OCI image only by its verified manifest digest. Validate role labels and inventories. Missing/deleted objects fail closed. |
| Handoff moved to a fresh reviewer runner | Reconstruct only the original producer identity from the attested observation and freeze evidence, verify their exact bytes and live PR identity, then hydrate the exact OCI digest into new local read-only backing trees and views. Producer paths are absent from the durable handoff. |
| Writable alias behind a protected bind view | Require both the materialized backing tree and exposed view to be read-only mounts, confirm that they alias the same directory, and compare both closed inventories before and after use. |
| Fork PR | API observation may be read-only. No fork-controlled code runs with credentials. The PR author cannot dispatch a review of their own PR, including a fork PR. Review write permission exists only in a separate submit job after successful verification. |
| Privileged workflow injection or attacker-controlled text | Only default-branch workflow code is trusted. Parse PR number as an integer; pass data through files/API bodies, never interpolated shell. No `pull_request_target` or `workflow_run`. |
| Concurrent head movement | Re-fetch immediately before submission; mismatch invalidates the completed analysis and blocks posting. |
| Repository maintainer or default-branch workflow compromise | In scope as root trust. Repo administrators who can change the trusted default-branch workflow or attestation policy can authorize a different producer; auditability and explicit revision binding make that change visible but do not defend against an authorized owner. |

### Alternative evaluation

| Alternative | Trust properties and disposition |
| --- | --- |
| Actions-native (`GITHUB_TOKEN`, OIDC, Artifact Attestations, GHCR OCI) | Satisfies repository-scoped API access, ephemeral workload identity, provenance binding, content-addressed image identity, and protected read-only role views. Selected. A workflow default-branch trust root is accepted and auditable. |
| Dedicated GitHub App | Could supply a distinct API principal, but adds no required provenance or freeze property: OIDC/attestation already authenticates the workflow and `GITHUB_TOKEN` can read PRs and submit reviews. The app would not make a writable workspace immutable. Not required. |
| External trust/freeze service | Could supply independent signing and immutable storage, but introduces an operator-managed trust relationship without adding a required property unavailable from Actions-native attestation plus digest-addressed OCI and protected role views. Not selected. |

## Consequences

- The GitHub-specific producer, verifier and submission transport remain in the platform adapter. GitHub event names, claims and review payloads do not enter semantic policy.
- Workflow permissions must be explicit and job-scoped. The observation job needs `contents: read`, `pull-requests: read`, `id-token: write`, and `attestations: write`; only the OCI publisher needs `packages: write`, `id-token: write`, and `attestations: write`; the verifier needs the least permissions required to read attestations and the GHCR image; only the submit job needs `pull-requests: write`. Do not grant `artifact-metadata: write` because linked artifact storage records are not part of the trust contract.
- This workflow performs bootstrap and verification only; it does not run review analysis. Its GitHub token is used for provider and attestation verification. A later analysis executor must not receive that token and must consume the read-only protected role views; this ADR does not claim its root filesystem or network is isolated.
- Absolute local locators exist only in the ephemeral reviewer-local-view session bound to the durable handoff digest; they are not part of the portable handoff artifact.
- `github-actions[bot]` is technically able to submit a pull-request review with `pull-requests: write`. Repository policy accepts the automated transport only when the authenticated workflow dispatcher differs from the PR author. The semantic conclusion remains owned by the frozen procedure and policy, not the bot account.
- GitHub-hosted workflow execution is required for deployment qualification. Local tests can qualify rejection behavior but cannot establish deployed OIDC, attestation, registry, token-permission or bot-review behavior.
- The first deployment is a bootstrap transition: the new infrastructure may not formally accept its own unreviewed implementation. Independent review of its exact PR stack and authorized merge must occur before the first production run. No PR is merged by this change.
