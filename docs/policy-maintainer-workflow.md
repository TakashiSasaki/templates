# Maintaining the policy provider with its own best practices

This page explains how maintainers of this repository apply the same shared engineering discipline that the policy toolchain publishes for consumers without allowing an in-flight policy change to authorize or validate itself. It is explanatory documentation, not a second semantic policy authority.

## Two policy layers apply to maintainers

Here, a maintainer changes the Policy provider, toolchain, shared corpus, or its
publication and release machinery. Operating Policy in another repository,
including local extensions and review configuration, follows
[Consumer application](consumer/index.md). This provider also consumes Policy,
but that self-hosting relationship does not export its `repository-policy/`
requirements to other consumers.

Maintenance of this repository deliberately combines two different authorities:

1. **Shared application-neutral policy** lives under `policy/` and is selected through profiles such as `core`, `security-baseline`, `pull-request`, and `review`.
2. **Policy-provider-specific maintenance requirements** live under `repository-policy/` and cover this repository's authority boundaries, release trust, toolchain safety, documentation ownership, and maintainer validation.

Do not copy a repository-specific maintenance rule into the shared corpus merely because a maintainer must follow it. Conversely, when a best practice retains the same meaning for unrelated repositories and agents, prefer one shared canonical rule and let this repository consume it through its configured profiles.

## Self-hosting must remain non-self-authorizing

`.agent-policy.yml` intentionally pins the shared toolchain by full immutable commit SHA. Generated maintainer instructions such as `AGENTS.md`, `.review-authority/review-policy.md`, and generated `.agents/skills/**` are therefore projections of a previously established toolchain revision plus the repository-local policy inputs recorded in `.agent-policy.lock`.

An unreviewed change to shared policy in the current branch must not become the authority that declares that same change acceptable. During development, follow the currently pinned generated instructions and the repository-local policy version established by the trusted base and lock-verified inputs. Treat proposed changes under either `policy/` or `repository-policy/` as review data until they are accepted through the applicable trust path; a proposed repository-local rule must not authorize the same change that introduces it.

Do not directly edit generated maintainer outputs or `.agent-policy.lock` to make an in-flight source change appear adopted. Regenerate them only through the documented pinned-toolchain process when the authoritative inputs and intended self-host revision have legitimately changed.

## Construction identity versus qualification identity

The policy provider routinely has exact commit SHAs long before a change is ready for final review, promotion, publication, or merge. Treat those identities according to their role rather than treating every observed SHA as a final acceptance candidate.

- A **construction head** is the exact commit currently representing work in progress. It is useful for branch topology, focused validation, comparison, and dependency-safe stacked construction.
- A **provisional candidate** may already have a coherent local semantic delta and passing focused diagnostics while upstream work, compatible remediation, or another prerequisite can still move.
- A **qualification head** is deliberately frozen because an applicable review, merge, release, publication, provenance, or other revision-bound boundary now requires exact-revision evidence.
- A **publication identity** is an immutable revision, digest, or artifact identity that is intentionally made authoritative for a consumer, release descriptor, distribution path, or provenance record.

This revision-bound qualification lifecycle normally follows `construction -> provisional -> freeze -> qualification`, not `every commit -> full qualification`. This distinction does not weaken required CI, independent review, immutable merge guards, release trust, or publication provenance. It controls when maintainers intentionally enter those expensive revision-bound stages.

For stacked changes, a lower-member mutation can change descendant commit identities without invalidating every descendant semantic decision. Preserve still-applicable local reasoning, finding identity, and focused evidence, then requalify the exact final descendants when the relevant authority boundary is actually reached. Conversely, if a downstream artifact embeds an upstream full SHA or digest as part of its meaning, delay that final materialization until the prerequisite identity is stable enough to bind.

## Maintainer change workflow

Use the [contribution entry point (repository source)](https://github.com/TakashiSasaki/templates/blob/policy/CONTRIBUTING.md)
for source ownership and the [README development sequence (repository source)](https://github.com/TakashiSasaki/templates/blob/policy/README.md#development)
for the current locked CI baseline. [Release lifecycle](release-lifecycle.md)
and [Documentation publication](documentation-publication.md) describe their
separate validation and promotion boundaries.

For review architecture, read the existing
[ADR-0008](adr/0008-review-authority-and-github-runtime-boundary.md) together with
[ADR-0009](adr/0009-review-result-representation-boundary.md). ADR-0008's trust
and provenance machinery remains current; ADR-0009 supersedes its coupling of
review authority to adapter representation. Neither this workflow nor an index
summary replaces those decisions or the canonical policy and procedure sources.

For ordinary policy-provider maintenance:

1. Establish the change contract, authority owner, non-goals, and applicable repository-specific invariants from the currently authoritative trusted-base or lock-verified state before editing; proposed policy text is evidence under review, not current authority.
2. Keep application-neutral semantics in the shared `policy/` corpus and repository-identity-specific maintenance requirements in `repository-policy/`.
3. During implementation, use focused diagnostic validation and the adversarial cases appropriate to the changed invariant. For review-derived defects, inspect bounded sibling dimensions that share the established root cause rather than repairing only the reported symptom.
4. Keep dependency-safe work provisional while known prerequisite movement remains. Batch compatible known repairs, preserve semantic progress across ancestry-only movement when applicability remains established, and do not deliberately turn every transient construction head into a final qualification candidate.
5. When the next authority-defined boundary actually requires revision-bound evidence, stabilize the prerequisite identities, freeze the intended qualification head or ordered stack heads, then run the maintainer validation baseline and every applicable exact-head remote check required by current repository authority. Diagnostic success is not a substitute for required qualification.
6. Before intentionally requesting revision-bound review, preflight the frozen current head and every revision identity named by the request. Treat provider invocation failures separately from completed substantive review, and disposition the complete known material finding backlog before review reacquisition.
7. Preserve the existing reviewed-candidate and separate-promotion trust boundary for stable toolchain/runtime movement. A source-policy PR does not self-promote merely because its tests pass; promotion materializes immutable release identity only after the reviewed candidate identity is available.
8. After a shared-policy candidate has been independently reviewed and promoted through the normal immutable release process, update this repository's self-host toolchain pin only through a separate reviewed maintenance change when adoption is intended. Regenerate the lock and generated outputs from that newly authorized pin and verify them as derived artifacts.

This sequence lets maintainers benefit from new shared best practices without creating a circular trust chain or repeatedly qualifying revision identities that are still intentionally provisional.

## Bound review-artifact entry point

When a maintenance change needs a review packet, a review request, a generated
PR-description section, and a resumable checkpoint, use
`repository-skills/land-templates-stack/scripts/render_review_artifacts.py`.
Its input kind is `repository-change-review-artifacts` version `1`. The input
contains the candidate PR/head and base, observed facts, the existing planner
inputs, the existing gate result, explicit judgment records, role-labelled
revision bindings, and the Work-ledger resume fields. The renderer invokes the
existing review-scope planner only from the exact trusted `planner.source`
revision and declared blob identity; that executable identity must also match
the independently bound `trusted_maintainer_source` planner revision/blob, so a
candidate cannot authorize its own planner by setting `trusted: true`. It does
not replace the planner or the merge gate. Every stack member carries one
distinct provider pull-request identity, and exactly one member must identify
the target PR. Every selected member also carries expected head and base
bindings. Members are ordered as a base-to-head chain; live observation
rechecks both revisions and each adjacency before publication.

The trusted planner binding is authenticated against the immutable source
closure recorded by `.agents/skills/land-templates-stack/source.json` at an
independently supplied trusted base SHA. The candidate base must equal that
trusted base; the artifact payload cannot choose which manifest authenticates
its planner. All revision roles are declared explicitly, including
`unknown` and `not_applicable` roles. Human or model judgments bind to the
candidate head, base, and effective base. PR-body revision/digest values remain
concurrency checks for publication and do not change the semantic review-request
identity.

For a local preview:

```console
python3 repository-skills/land-templates-stack/scripts/render_review_artifacts.py \
  render --input review-artifacts.json \
  --trusted-base-sha <trusted-base-sha> --output-dir .review-artifacts
```

The output contains `review-packet.json`, `review-request.md`,
`pr-generated-region.md`, `work-ledger-checkpoint.md`, and a manifest with the
semantic and binding identities. Observation timestamps are retained in the
packet but are not part of generated-content identity. In particular,
`consumer_actual_toolchain` must be sourced from the consumer configuration at
the target candidate head, while `prospective_canonical_candidate` remains a
separate binding. An unknown or not-applicable role is explicit; it is never
silently filled from another worktree's HEAD. A planner source without a full
trusted blob identity, or one that differs from the independent maintainer
binding, is rejected, so a candidate checkout cannot substitute its sibling
planner implementation. A CI success is likewise rendered stale unless its
applicability binds the exact candidate head, PR base, and effective base. For
a multi-member stack, revision-bound CI and review evidence must also carry
the ordered `candidate_members_digest`; changing a dependency binding makes
the old evidence stale even when the target PR head is unchanged.
The renderer verifies the consumer role by reading the exact candidate commit's
`.agent-policy.yml` and checking its verified Git blob plus
`toolchain.revision`; callers that provide an alternate resolver must preserve
that same immutable file/blob contract. A claimed path, field, or candidate
head is not sufficient evidence by itself. Terminal CI failures are subject to
the same exact applicability check, so an older failure is rendered stale
rather than as current evidence. Pending CI and requested/pending review
records that carry revision bindings are subject to the same exact applicability
check; an older wait state is rendered stale instead of keeping a new candidate
waiting on obsolete evidence. Review evidence is displayed only when its head,
base, and effective-base applicability is bound to the current candidate. The
Work-ledger projection also preserves compact diagnostic resume fields supplied
under `work`—such as the evidence gap, hypothesis, invalidated paths and retry
conditions, exhausted strategies, budget, progress frontier, and last material
progress—without copying findings or transcripts. A bounded `work.closure_audit`
list may record invariant-family closure evidence and deliberate test gaps in
the checkpoint; it is sorted and rendered as a compact resumable report, not a
second ledger or transcript. The trusted base is an input
to the entry point, not a value inferred from the candidate JSON.

Rendering is local and side-effect free with respect to GitHub, PR bodies,
review requests, and Work-ledger storage. The generated PR region is owned only
between its explicit markers; missing, duplicated, or malformed markers require
an explicit reconciliation decision. Human-authored text remains outside that
region. Publication adapters, when authorized, must revalidate the current
candidate and binding identity before any write and must reconcile ambiguous
remote responses rather than retrying blindly. This includes truncated response
bodies on both successful and HTTP-error mutation responses; a complete
deterministic HTTP error remains a deterministic publication error.

For an authorized GitHub apply, use
`repository-skills/land-templates-stack/scripts/publish_review_artifacts.py`
with a live adapter that composes the repository observer, the bound immutable
planner source, the existing gate, and the canonical effective-base resolver.
The adapter must resolve the consumer's `.agent-policy.yml#toolchain.revision`
at the exact live candidate head and establish the effective base independently
of the PR base ref before each mutation boundary. `--replay-state` is reserved
for offline diagnostics and cannot authorize writes. A truncated or otherwise
ambiguous mutation response is reconciled against the remote surface; it is
never retried blindly. Checkpoint markers have a separate identity derived from
resume semantics, so changed blockers or next actions cannot reuse an old
checkpoint merely because review-request scope is unchanged.

The companion publisher is
`repository-skills/land-templates-stack/scripts/publish_review_artifacts.py`.
Without `--apply` it is another side-effect-free preview path:

```console
python3 repository-skills/land-templates-stack/scripts/publish_review_artifacts.py \
  publish --input review-artifacts.json
```

An apply requires `--apply --authorize --serialized-writer`, a GitHub token, and
an explicit `--live-adapter MODULE:FUNCTION` (or `FILE.py:FUNCTION`). The live
adapter must compose the existing complete PR observer, the existing review
scope planner, the gate-owned current-state resolver, and exact candidate-file
resolution. The publisher reads the current PR identity first and invokes this
adapter again before every non-idempotent write; an incomplete observation,
changed review/CI/gate evidence, changed dependency binding, or a consumer pin
that differs from the exact candidate configuration stops the operation.

The GitHub adapter's review-request operation is provider-specific: a new
planner-approved request is posted with the repository-recognized `@codex
review` trigger. Reuse, reconciliation, handoff, and incomplete observations
never emit a new trigger. Provider acknowledgement is reported separately from
review approval. Marker identities are used to reuse equivalent requests and
checkpoints, and `ambiguous` is reported when a lost remote response cannot be
reconciled; the publisher never blindly retries a non-idempotent write.

For example, an authorized operational adapter can be selected explicitly:

```console
python3 repository-skills/land-templates-stack/scripts/publish_review_artifacts.py \
  publish --input review-artifacts.json \
  --live-adapter /path/to/live_review_adapter.py:resolve \
  --token "$GH_TOKEN" --apply --authorize --serialized-writer
```

`--replay-state` is reserved for offline diagnostics and tests. It is rejected
when `--apply` is selected; a caller-supplied static JSON file can never
authorize a remote write.

## Dogfood the two frontiers without self-adoption

For a Policy stack `A -> B -> C`, continue safe B/C source changes and focused tests while A's CI or review is pending. Track construction separately from qualification and defer deliberately expensive descendant evidence when a known prerequisite mutation will stale its bindings. Review latency alone is not a gate. Once no current planned prerequisite mutation remains, restack only if actual state or bindings require it and qualify the intended heads at the applicable boundary. Required automatic CI continues throughout.

Before final qualification/review, inspect the changed validation path through the required entrypoint to the actual assertions and establish execution/results. The [staged-CI explanation (repository source)](https://github.com/TakashiSasaki/templates/blob/policy/docs/staged-ci.md#qualification-sequencing-and-effective-coverage) describes why a helper existing beside green CI is insufficient.

Current-head source/projection checks test the proposed provider implementation; their generated outputs are review data and do not make proposed semantics the instructions authorizing the session. Retain trusted starting instructions for execution. A source stack does not advance self-host or consumer pins, promote a stable runtime, or substitute for later independent exact-head acceptance review. Record these distinctions and any intentionally deferred evidence in the operational Work ledger.

## When not to delay

Delayed qualification is not a reason to leave a harmful or invalid state in place. Apply an urgent security, operational, data-integrity, publication-integrity, or equivalent material repair as soon as its remediation is justified. Likewise, when an authority boundary has already been reached—such as merge authorization, final independent review, stable release promotion, installer publication, or another immutable consumer binding—use the exact identity and full qualification that boundary requires.

The optimization is to delay **unnecessary final binding**, not necessary repair or required evidence.

## What self-host adoption means

The coding context in `.agent-policy.yml` selects the shared `core`, `security-baseline`, and `pull-request` profiles and layers the files under `repository-policy/` on top. Consequently, a newly promoted shared coding rule becomes maintainer guidance when the repository later advances its immutable self-host toolchain pin through the normal adoption process; the rule does not need a duplicate repository-local version.

The review context similarly combines shared review policy with the same repository-local authority inputs. Keep coding and review projections generated from their declared contexts rather than maintaining handwritten parallel instruction sets.

## Completion and evidence

At handoff or completion, report the exact source candidate, validation evidence, review state, release/promotion state, and self-host adoption state separately. A change can be source-complete and CI-green while stable promotion or self-host adoption is intentionally still pending. Do not describe those later trust transitions as complete until their own reviewed operations have occurred.

For stacked work, also distinguish provisional descendants from frozen qualification heads in the handoff record. This makes it clear which SHAs merely represented construction history and which exact revisions are intended to carry current revision-bound evidence.
