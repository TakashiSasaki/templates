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
at the exact live candidate head using the publisher's duplicate-safe
`yaml.SafeLoader` boundary; it must not import a parser from the mutable
candidate checkout. The adapter must also establish the effective base
independently of the PR base ref before each mutation boundary. `--replay-state` is reserved
for offline diagnostics and cannot authorize writes. A truncated or otherwise
ambiguous mutation response is reconciled against the remote surface; it is
never retried blindly. Checkpoint markers have a separate identity derived from
resume semantics, so changed blockers or next actions cannot reuse an old
checkpoint merely because review-request scope is unchanged. A checkpoint may
be reused only when the publisher can prove ownership; a copied marker or
matching body from another contributor stops publication. After a
planner-approved review request is created or reconciled, the publisher updates
that same owned checkpoint to record the submitted request state. That update
has its own revalidation and ambiguity reconciliation boundary.

The provider-neutral PR observer snapshot is schema version 2. Version 2 makes
each dependency's expected and observed base part of the persisted binding, so
an older version-1 snapshot must be regenerated before it is resumed or
compared; it is never silently treated as a complete head-only observation.

For a cumulative whole-stack input with `candidate.integration_base_tree_sha`,
the live adapter resolves the Git tree attached to the independently resolved
effective-base commit and compares it with the bound tree before publication.
An asserted tree value, or a value from an unrelated worktree, is not accepted
as cumulative evidence.

The trusted base SHA is supplied by the trusted operational context, not read
from the artifact JSON; the publisher rejects an input whose candidate base
does not match it. Complete mutating 5xx responses are treated as ambiguous
and reconciled, while complete deterministic 4xx responses remain errors.

The companion publisher is
`repository-skills/land-templates-stack/scripts/publish_review_artifacts.py`.
Without `--apply` it is another side-effect-free preview path:

```console
python3 repository-skills/land-templates-stack/scripts/publish_review_artifacts.py \
  publish --input review-artifacts.json \
  --trusted-base-sha <trusted-base-sha>
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
never emit a new trigger. An equivalent request must have the canonical
provider-specific body and be authored by the authenticated publisher; a copied
or edited marker is not sufficient to suppress publication. A reaction counts
as Codex acknowledgement only when its actor is the configured Codex review
bot, not merely because an ordinary contributor added `eyes`. Provider
acknowledgement is reported separately from review approval. Marker identities
are used to reuse equivalent requests and checkpoints, and `ambiguous` is
reported when a lost remote response cannot be reconciled; the publisher never
blindly retries a non-idempotent write.

The `--serialized-writer` assertion covers the complete body-and-comment
publication sequence, not only the PR-body update. The publisher also rejects
an overlapping in-process publication for the same repository/PR. When more
than one process can publish, the caller must hold the repository's distributed
writer lock across the full sequence because GitHub has no atomic
create-if-absent issue-comment operation.

For example, an authorized operational adapter can be selected explicitly:

```console
python3 repository-skills/land-templates-stack/scripts/publish_review_artifacts.py \
  publish --input review-artifacts.json \
  --trusted-base-sha <trusted-base-sha> \
  --live-adapter /path/to/live_review_adapter.py:resolve \
  --token "$GH_TOKEN" --apply --authorize --serialized-writer
```

`--replay-state` is reserved for offline diagnostics and tests. It is rejected
when `--apply` is selected; a caller-supplied static JSON file can never
authorize a remote write.

### Finding-family review readiness

The shared Policy rule `testing.require-adversarial-invariant-coverage` remains
the semantic authority for closing a materially reachable finding family. The
maintenance Skill operationalizes that rule by recording compact family
references, sibling-audit evidence, deliberate gaps, and the next safe action
in the existing `work.closure_audit` projection. It is not a second finding
ledger or an acceptance gate.

The normalized Work state also supplies the planner packet's optional
schema-version-2 `review_readiness` field. Missing or unknown readiness, an open
family, an incomplete sibling audit, a material gap, or a planned candidate
mutation blocks a new intentional expensive review request. Repairing the exact
reviewer example is not family closure by itself. During this bounded review
freeze, required automatic CI, focused tests, read-only observation, and
additional justified repair remain active; applicable completed review results
may still be reused and in-flight or ambiguous requests reconciled. An explicit
urgent/authority-bound exception must include its reason and authority
reference, and does not erase the underlying gap.

The packet, review request, generated PR region, and Work-ledger checkpoint are
derived from the same normalized state. Candidate Policy changes do not
self-authorize their own readiness: use the currently trusted planner and
maintenance Skill until the proposed source has passed its normal review and
adoption boundaries.

The readiness projection is mutable routing state, not historical review or
request applicability identity. Existing request/review records are matched by
candidate, contract, input, and scope bindings without readiness; the canonical
review-request body likewise excludes mutable readiness and routing diagnostics.
A former recorded readiness field is ignored only after its original record
digest is validated. Checkpoint identity and the generated PR region remain
readiness-sensitive because blockers and resume instructions are operational
state. Legacy closure records without explicit sibling-audit evidence, or
planner family records without explicit status, fail closed instead of being
upgraded to ready.

## Dogfood the two frontiers without self-adoption

For a Policy stack `A -> B -> C`, continue safe B/C source changes and focused tests while A's CI or review is pending. Track construction separately from qualification and defer deliberately expensive descendant evidence when a known prerequisite mutation will stale its bindings. Review latency alone is not a gate. Once no current planned prerequisite mutation remains, restack only if actual state or bindings require it and qualify the intended heads at the applicable boundary. Required automatic CI continues throughout.

Before final qualification/review, inspect the changed validation path through the required entrypoint to the actual assertions and establish execution/results. The [staged-CI explanation (repository source)](https://github.com/TakashiSasaki/templates/blob/policy/docs/staged-ci.md#qualification-sequencing-and-effective-coverage) describes why a helper existing beside green CI is insufficient.

Current-head source/projection checks test the proposed provider implementation; their generated outputs are review data and do not make proposed semantics the instructions authorizing the session. Retain trusted starting instructions for execution. A source stack does not advance self-host or consumer pins, promote a stable runtime, or substitute for later independent exact-head acceptance review. Record these distinctions and any intentionally deferred evidence in the operational Work ledger.

### Machine-readable qualification sequencing

To prevent churn cycles (upstream change → downstream repin → rerun qualification → upstream fix → repin again), maintainers invoke `scripts/sequence_qualification.py`.

The sequencer operates strictly read-only and distinguishes four core frontiers:
1. **Construction (`construction`)**: Upstream is actively mutating or has planned mutations. Independent construction and focused unit tests are allowed; downstream repins and expensive full qualifications are deferred.
2. **Qualification (`qualification`)**: Upstream is frozen, undergoing qualification. Upstream acceptance is awaited before downstream repin.
3. **Adoption (`adoption`)**: Upstream is accepted. Downstream repin is eligible or no-op, followed by final qualification.
4. **Blocked (`blocked`)**: Open material findings or conflicting state halts progression (fails closed).

Planning and mutation remain separate: repin operations require explicit authorization (`authorized=True`) and exact expected-old-pin guards, failing closed on unexpected concurrent pin values.

### Canonical preflight orchestration

To avoid manual command discovery and uncoordinated multi-authority validation loops, maintainers use `scripts/orchestrate_preflights.py`.

The orchestrator:
- Binds to canonical per-authority entrypoints:
  - `policy`: `scripts/run_policy_preflight.py fast`
  - `composition`: `scripts/run_composition_preflight.py fast`
  - `modeling`: `tools/qualify.py`
  - `integration`: `scripts/run_integration_preflight.py fast`
  - `site`: `scripts/run_site_preflight.py fast`
- Binds to exact worktree heads via `git rev-parse HEAD` and verifies against `--expected-heads-json` when supplied.
- Executes validations with finite timeouts (`--timeout`) and bounded concurrency (default: 2, configurable via `-j / --jobs`; explicit `--jobs 1` selects serial execution).
- Captures full logs (`--log-dir`) while returning a concise, bounded summary table (`<= 8 KiB`).
- Preserves authority boundaries: does NOT re-implement or reinterpret authority validation semantics.

### Automation boundaries and operation taxonomy

To prevent orchestration helpers from accidentally assuming semantic authority, maintainer tooling adheres to an explicit operation taxonomy (`scripts/automation_boundaries.py`):
1. **Mechanical / Read-Only**: Fact acquisition, local preflights, deterministic routing calculations (`observe_pr_state`, `orchestrate_preflights`, `sequence_qualification`, `plan_review_scope`). These produce validation evidence only and cannot establish review acceptance or merge authorization.
2. **Guarded Mutation**: Reversible mutations requiring explicit authorization and concurrency guards (`execute_guarded_repin`, `publish_review_artifacts`).
3. **Semantic Judgment**: Qualitative determinations (finding validity, architecture correctness, acceptance contract evaluation). These cannot be synthesized by mechanical tools.
4. **Authority-Controlled Decisions**: Irreversible trust transitions (merge authorization, Policy self-host adoption, publication cutover). These strictly require separate, authenticated human authorization.

## When not to delay

Delayed qualification is not a reason to leave a harmful or invalid state in place. Apply an urgent security, operational, data-integrity, publication-integrity, or equivalent material repair as soon as its remediation is justified. Likewise, when an authority boundary has already been reached—such as merge authorization, final independent review, stable release promotion, installer publication, or another immutable consumer binding—use the exact identity and full qualification that boundary requires.

The optimization is to delay **unnecessary final binding**, not necessary repair or required evidence.

## What self-host adoption means

The coding context in `.agent-policy.yml` selects the shared `core`, `security-baseline`, and `pull-request` profiles and layers the files under `repository-policy/` on top. Consequently, a newly promoted shared coding rule becomes maintainer guidance when the repository later advances its immutable self-host toolchain pin through the normal adoption process; the rule does not need a duplicate repository-local version.

The review context similarly combines shared review policy with the same repository-local authority inputs. Keep coding and review projections generated from their declared contexts rather than maintaining handwritten parallel instruction sets.

## Completion and evidence

At handoff or completion, report the exact source candidate, validation evidence, review state, release/promotion state, and self-host adoption state separately. A change can be source-complete and CI-green while stable promotion or self-host adoption is intentionally still pending. Do not describe those later trust transitions as complete until their own reviewed operations have occurred.

For stacked work, also distinguish provisional descendants from frozen qualification heads in the handoff record. This makes it clear which SHAs merely represented construction history and which exact revisions are intended to carry current revision-bound evidence.

## Standard maintainer CLI and live adapter entry point

Maintainers of the Policy authority use the integrated CLI entry point and standard live review adapter instead of hand-writing transient scripts or bespoke revalidation code:

- **Candidate Bootstrap Runner**: `scripts/run_maintainer_workflow.py`
  - Before B1 adoption, this runner is a candidate bootstrap implementation undergoing prospective qualification. Once adopted, the trust root is anchored to the accepted Policy authority revision.
  - Verifies the complete finite trust root chain:
    $$\text{accepted Policy authority revision} \longrightarrow \text{adopted bootstrap / verifier} \longrightarrow \text{immutable source manifest} \longrightarrow \text{verified maintainer Skill closure} \longrightarrow \text{isolated workflow execution}$$
  - Authenticates the source reference against an immutable base Git commit or an explicit prospective manifest.
  - Verifies all declared closure blobs against the local Git object store.
  - Materializes the verified closure in an `IsolatedClosureEnvironment` and connects Git object storage.
  - Executes the verified entrypoint module inside the active isolation lifetime, guaranteeing immunity from mutable worktree alterations or local module shadowing.
- **Maintainer entrypoint**: `repository-skills/land-templates-stack/scripts/maintain_review_stack.py`
  - Assembles valid version 1 `repository-change-review-artifacts` input data with all 5 mandatory role-labelled revision bindings.
  - Resolves toolchain revision from `.agent-policy.yml` at the candidate head.
  - Authenticates the planner source and closure against the immutable manifest in `.agents/skills/land-templates-stack/source.json` at the independently trusted base SHA.
  - Executes `render_review_artifacts.py` to normalize and render the complete artifact suite (`review-packet.json`, `review-request.md`, `pr-generated-region.md`, `work-ledger-checkpoint.md`, `manifest.json`).
  - Supports offline `--preview` without writes and safe live `--apply` when authorized.
- **Live adapter**: `repository-skills/land-templates-stack/scripts/live_review_adapter.py`
  - Implements `resolve(context, payload, provider)` complying with `publish_review_artifacts.py` contracts.
  - Encapsulates `GitHubLiveRevalidationAdapter` with default planner packet builder, gate resolver, and effective base resolver.
  - Verifies exact PR head and base bindings against live remote metadata before allowing publication.
- **Fail-closed publication safety**:
  - Remote apply strictly requires `--apply`, `--authorize`, and `--serialized-writer`.
  - Without all three flags, execution aborts with `MaintainerWorkflowError` before performing any external or state-changing writes.

### Operational CLI Examples

```bash
# 1. Prospective qualification / preview execution from candidate Git objects (isolated, no writes):
python scripts/run_maintainer_workflow.py \
  --trusted-base-sha <POLICY_BASE_SHA> \
  --source-manifest <PROSPECTIVE_MANIFEST_PATH> \
  --pr 123 \
  --head-sha <CANDIDATE_HEAD_SHA> \
  --base-sha <BASE_SHA> \
  --output-dir ./artifacts_preview

# 2. Preview artifacts locally via adopted bootstrap runner post-adoption (isolated execution, no writes):
python scripts/run_maintainer_workflow.py \
  --trusted-base-sha <TRUSTED_BASE_SHA> \
  --pr 123 \
  --head-sha <CANDIDATE_HEAD_SHA> \
  --base-sha <BASE_SHA> \
  --output-dir ./artifacts_preview

# 3. Revalidate and publish when explicitly authorized by maintainer:
python scripts/run_maintainer_workflow.py \
  --trusted-base-sha <TRUSTED_BASE_SHA> \
  --pr 123 \
  --head-sha <CANDIDATE_HEAD_SHA> \
  --base-sha <BASE_SHA> \
  --apply --authorize --serialized-writer \
  --output-dir ./artifacts_applied
```

## Adoption and handoff boundaries

This implementation establishes the maintainer entry point and verified source closure within the Policy authority candidate stack. For maintainer clarity, the following boundaries remain strictly defined:

1. **Policy authority self-host adoption**:
   - The new maintainer entrypoint and live adapter are implemented in candidate branches (`feat/policy-maintainer-*`).
   - Self-host pins in `.agent-policy.yml` and `.agents/skills/**` on `policy` main remain unchanged until this stack is independently reviewed, accepted, and deliberately adopted.
   - During prospective qualification, candidate source verification is exercised end-to-end using prospective manifests constructed directly from immutable Git objects, without mutating the current adopted baseline pins.
2. **Other authorities**:
   - The other 4 authorities (`composition`, `site`, `integration`, `modeling`) maintain their own adoption lifecycles. No files or pins in those authorities are modified by this change.
3. **Efficiency measurement**:
   - Measured mechanically using `scripts/measure_maintainer_efficiency.py` over validated transition fixtures.
   - Demonstrates a 75% reduction in model execution interruptions (from 4 to 1) and unchanged poll suppression.
   - Token savings are explicitly accounted for as `proxy_unobserved` and are not asserted as unmetered live savings.

