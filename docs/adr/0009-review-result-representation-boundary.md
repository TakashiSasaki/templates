# ADR-0009: Keep review-result representation outside review authority

- Status: Accepted
- Date: 2026-09-02
- Supersedes in part: ADR-0008

## Context

ADR-0008 separated semantic review policy, trusted bootstrap, review procedure, platform adaptation, and platform runtime integration. Its trust-boundary decisions remain necessary: automated review must use authenticated installed Skill provenance, a frozen exact-base authority snapshot, a frozen lock-selected runtime, a frozen reproduced `pr-review` procedure bundle, immutable semantic-policy projection bytes, stable repository/pull-request identity, and a strict separation between review execution and merge authorization.

ADR-0008 also made one transitional assumption that is no longer required: it treated a provider-specific adapter projection and its exact serialized bytes as part of the trusted review-authority closure. That led to dual semantic/adapter output binding, adapter renderer selection such as `github-review-json-adapter-v1`, and a requirement that final review completion remain bound to adapter-byte identity.

A semantic review does not need a repository-owned general-purpose wire format. The review procedure needs to preserve the meaning of findings, limitations, and its completion conclusion; the integration that submits or displays that result can choose a provider-specific representation. Requiring JSON fields, one exact response-object shape, GitHub event strings, or an adapter renderer would therefore turn transport representation into review authority without a semantic need.

## Decision

### Review authority stops before provider serialization

The normative automated-review authority chain is:

1. **Semantic review policy** under `policy/review/*.md` and its composed provider-neutral context. It defines what risks are considered and when a finding is admissible.
2. **Trusted bootstrap/runtime**. It establishes immutable provenance and exact-base authority but performs no finding analysis.
3. **`pr-review` procedure** under `skills/pr-review/*`. Its verified immutable procedure bundle is the sole procedural authority for review execution.

Provider submission and result serialization occur after those layers. They may faithfully represent the established review result, but they are not additional semantic or procedural review authority.

A review result may conceptually establish any of the following without adopting a repository-wide result schema:

- review completed and blocking findings exist;
- review completed and no blocking finding exists; or
- review did not complete sufficiently, with limitations or failure evidence preserved.

The executing integration may represent that result in prose, structured data, a provider API request, or another form as long as it preserves the applicable semantic findings, limitations, completion state, and conclusion. The provider-neutral review procedure must not require one JSON object, JSON-only output, `schema_version`, `analysis_status`, `comments`, `unanchored_findings`, numeric confidence serialization, or any other particular response-object field set.

### GitHub request shape is integration reference material

GitHub pull-request review concepts such as a review body, commit-SHA anchoring, `APPROVE`, `REQUEST_CHANGES`, `COMMENT`, and inline-comment fields such as `path`, `body`, `line`, `side`, `start_line`, and `start_side` are useful integration information. They are not semantic review policy and are not required `pr-review` result fields.

The repository may document those concepts in a non-normative reference at `skills/pr-review/references/github-pull-request-review-api.md`. JSON examples in that reference are GitHub API request payload examples only. Every such example must explicitly state that it is not the required output format of the review procedure. GitHub's current API documentation and the actual connector/tool contract remain authoritative for GitHub request shape.

The repository must not create a general-purpose review-result JSON schema merely to mediate GitHub submission. A concrete future consumer may justify a dedicated representation contract, but that contract must identify that consumer and must not silently become semantic review policy or `pr-review` procedure authority.

### Trusted review provenance excludes adapter identity

The trusted-review closure established by ADR-0008 continues to bind the authenticated installed `agent-policy` Skill source, frozen bootstrap run image, exact-base Git-object-backed authority snapshot, lock-selected frozen runtime image, reproduced frozen `pr-review` procedure bundle, provider-neutral semantic review projection, and the repository/pull-request/base/head identities required by the procedure.

It does **not** require:

- a provider adapter projection;
- an adapter renderer identifier;
- a repository-owned review-result schema;
- retained adapter projection bytes or their digest;
- adapter-byte identity in final stability checks; or
- a provider event name as a review-procedure conclusion.

The provider-neutral semantic projection remains immutable review authority for the run. The procedure must consume the exact verified semantic authority selected from the frozen base and must re-establish that authority when base movement invalidates the run.

### Final stability is preserved through the output handoff

ADR-0008's identity-stability requirement remains. Immediately before the review procedure completes, it re-resolves stable repository identity, pull-request identity, current base commit/tree, proposed head, and the complete best-common-ancestor set and verifies that they still match the state actually analyzed under the applicable movement rules.

The procedure's completed result is valid only for that verified identity set. Its completion handoff must therefore bind the stable repository identity, pull-request identity, base commit/tree, proposed head, unique merge base, and the applicable frozen trusted-base/bootstrap/runtime/procedure/semantic-authority identities. This **identity-bound completion handoff** is validity evidence for the review result; it does not prescribe a provider response schema or serialization format.

If the final output is emitted atomically with that final identity observation, no second serialization-specific contract is required. If an integration submits, displays, or otherwise emits the result later, it must re-resolve the live repository, pull-request, base, head, and best-common-ancestor identities **immediately before final output** and require them to match the completed handoff, or use an equivalent atomic checked handoff that makes intervening movement impossible. A mismatch makes the result stale: the integration must not present it as a current exact-head review and must return to the procedure or trusted bootstrap according to the applicable movement rule.

Base movement invalidates the trusted-base authority root and requires trusted bootstrap and review analysis to be re-established. Relevant head or merge-base movement invalidates affected evidence and analysis. These validity rules do not make provider request serialization review authority and do not require a provider adapter projection or particular wire format.

### Review and merge authorization remain separate

This decision does not weaken ADR-0008's separation between review and merge authorization. `policy/pull-request/*` and `skills/pr-merge-gate/*` remain responsible for merge readiness. A provider-recorded review event alone does not prove that the required independent exact-head review procedure completed.

## Superseded portions of ADR-0008

Where ADR-0008 requires or implies any of the following, this ADR is the current authority and those requirements are superseded:

- two explicit semantic/adapter output bindings for `pr-review`;
- a mandatory adapter-only renderer such as `github-review-json-adapter-v1`;
- immutable retention or re-verification of adapter projection bytes as review authority;
- adapter projection identity in final review stability;
- final review completion being defined as a serialization step; or
- a repository-owned provider response schema as the normative review result.

All other ADR-0008 trust machinery remains in force, including authenticated bootstrap provenance, freeze-before-verify ordering, closed path/type inventories, symbolic/hard-link rejection, exact-base Git-object-backed authority, frozen runtime and procedure bundles, provider-neutral semantic projection immutability, unique merge-base handling, identity refresh, movement invalidation, fail-closed behavior, and review-versus-merge separation.

## Migration

The existing `github-review-json-v1` renderer and generated `.github/REVIEW_GUIDELINES.md` are transitional self-hosting artifacts. This decision does not delete or hand-edit them. They remain until a reviewed stable toolchain can generate the provider-neutral `pr-review` procedure and semantic projection and the Policy branch performs the normal lock-bound generated-output cutover.

Implementation should proceed in narrow stages:

1. preserve and independently implement the trusted-review provenance primitives without provider serialization;
2. implement provider-neutral `pr-review` and its non-normative GitHub API reference;
3. harden merge-gate completion evidence without depending on proprietary result fields;
4. verify and promote the exact reviewed stable toolchain revision;
5. perform Policy self-hosting cutover through canonical generated-output lifecycle; and
6. only after proving zero configured consumers, remove obsolete GitHub JSON renderers, templates, tests, and documentation.

## Consequences

- Semantic policy can be reused across providers without importing their request schemas.
- `pr-review` has one procedural responsibility and does not become a serializer specification.
- GitHub integration remains practical because provider request examples and field semantics can be documented close to the Skill as non-normative reference material.
- Trusted-review attestation becomes smaller: provider-neutral authority bytes are immutable, while provider request serialization is outside the authority closure.
- A completed review remains valid only for its identity-bound handoff; later output must revalidate that identity without turning provider serialization into review authority.
- A future machine consumer that genuinely requires structured review results must justify its own representation contract rather than inheriting a transitional GitHub JSON format by default.
