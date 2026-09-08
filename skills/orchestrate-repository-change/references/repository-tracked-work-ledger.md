<!-- agent-policy-generated: true -->
# Isolated repository-tracked Work ledger

## Purpose

Use this procedure only when the consumer or independent repository authority has explicitly adopted repository-tracked operational state for repository-change resumption. It is an optional storage strategy under the canonical [Work ledger](work-ledger.md), not a replacement for provider-side checkpoints and not a new acceptance authority.

The purpose is to reduce interruption-recovery cost by preserving a compact resumability cache inside the repository while keeping operational writes independent from implementation and qualification candidate heads.

## Adoption boundary

Do not create a repository-tracked Work ledger merely because this procedure exists. Positive adoption evidence must come from repository-local policy, an explicit task instruction, or another authoritative consumer decision. Absence of a prohibition is not adoption.

Provider-side PR/Issue checkpoints remain the default when no repository-tracked strategy is adopted. Execution-local state may supplement either strategy for high-frequency ephemeral checkpoints.

Adoption must define or make discoverable:

- the operational ref or equivalent isolated repository namespace;
- how an active work scope is located on that ref;
- the writer/concurrency discipline;
- any retention or cleanup convention that matters to later consumers; and
- the provider/repository identity to which the operational state belongs.

A conventional branch name such as `work-ledger` and paths such as `active/<work-id>/state.json` are examples only. This Policy does not reserve those names.

## Isolation requirements

The repository-tracked Work ledger must remain independently addressable from implementation and qualification candidates.

A valid isolated strategy has these properties:

- updating operational state does not move a PR head, feature branch head, qualification candidate, release candidate, or product-authority ref merely to record progress;
- operational files are not interpreted as product semantic state, validated lifecycle history, generated-source authority, review-finding authority, or merge evidence;
- deleting, compacting, or archiving old operational state cannot change the meaning of a qualified implementation revision; and
- provider facts remain canonical when they disagree with cached ledger observations.

A commit that adds or refreshes a progress file on the implementation candidate itself is not isolated. Moving the candidate and then re-running exact-head CI/review is not an acceptable substitute for isolation when the only reason for the mutation was bookkeeping.

## Recommended logical layout

Keep a **current checkpoint** optimized for resume. An optional event history may exist for debugging or audit, but resume must not require replaying a tool transcript.

Example only:

```text
<operational-ref>
└── active/
    └── <work-id>/
        ├── state.json
        └── events.ndjson   # optional
```

The current checkpoint should carry the logical state required by [Work ledger](work-ledger.md), including the change contract locator, authority snapshot, stack topology, mutation state, stability/qualification bindings, evidence locators, review state, blockers/dependencies, diagnostic state when applicable, and `next_safe_action`.

A machine-readable representation is recommended when it materially lowers resume cost or permits safe automated comparison, but no JSON/YAML schema is mandatory. If a repository defines a schema, that repository-local contract governs its serialization.

Event history, when used, should record material transitions rather than every fetch, poll, command, endpoint attempt, or progress message. The current checkpoint is the resume index; history is secondary evidence for reconstruction when the index is incomplete or disputed.

## Write protocol and concurrency

Treat the operational ref as shared mutable state even though it is isolated from implementation history.

Before updating a mutable checkpoint:

1. resolve the stable repository identity and current operational ref head;
2. read the current checkpoint and identify its predecessor/version;
3. reconcile any provider facts needed for the intended write;
4. prepare one material checkpoint update;
5. publish only if the operational ref still has the expected predecessor/head; and
6. if the compare-and-swap condition fails, do not force or blindly overwrite—reload, reconcile competing successors, and explicitly select the next state.

When the provider cannot conditionally update the shared ref, use an established serialized single writer or append immutable successor checkpoints that name their predecessor. Competing successors are a conflict to reconcile, not last-write-wins state.

Do not use `force` ref movement to erase a concurrent checkpoint merely to simplify resumption. Preserve enough conflicting state to reconstruct ownership and provider truth.

## Resume protocol

Resume is a cache-validation operation, not a complete rediscovery by default. Read-side freshness of the shared operational ref is part of concurrency safety, not an optional deep refresh.

### Phase 1 — checkpoint recovery

1. discover the adopted operational ref and active work scope;
2. unless serialized ownership is positively established by an authoritative mechanism that excludes concurrent writers, resolve the current **live operational ref head before selecting or loading the checkpoint** and bind this recovery attempt to that immutable head;
3. load the latest valid current checkpoint from that live immutable binding rather than from an unverified local or previously cached ref state;
4. recover the work identity, objective/scope, topology, last-known provider heads, evidence bindings, diagnostic negative-capability state, and `next_safe_action`;
5. retain explicit `unknown`, `pending`, stale, and conflict states rather than filling gaps from assumption;
6. identify the minimum live facts whose current value can change the safety of the recorded next action; and
7. before following `next_safe_action` or performing an external mutation, confirm that the operational-ref binding still names the live head when concurrent writers remain possible. If that binding moved, discard the stale recovery decision and restart Phase 1 from the new live head.

A provider may combine live-head resolution and checkpoint retrieval when it guarantees that the checkpoint read is bound to the returned immutable ref head. That optimization may reduce round-trip depth; it must not weaken the binding.

### Phase 2 — minimal frontier refresh

Refresh the smallest live frontier needed to validate the checkpoint before broad discovery. Typical frontier facts include:

- stable repository/provider identity;
- relevant PR/member open/merged/closed state;
- exact current member head;
- applicable base/dependency identity or head when the next action depends on it;
- current state of a specifically bound CI/review/deployment dependency; and
- the live operational-ref binding established in Phase 1 when concurrent writers remain possible.

Compare these live facts to the cached observations before opening deeper surfaces.

Classify each cached observation as:

- **binding-valid / unchanged** — reuse it when all applicability conditions still hold;
- **changed** — refresh the directly affected dependent state;
- **stale** — retain the historical locator but do not use it for current qualification;
- **unknown** — refresh before relying on it; or
- **not relevant to the next safe action** — leave it unrefreshed until it becomes decision-relevant.

Only then retrieve deeper CI run details, review threads, comments, reactions, changed files, ancestry, provenance, or other provider surfaces when the changed/unknown binding or next action requires them.

Freshness is required; exhaustive rediscovery is not. Optimize **round-trip depth** as well as call count: independent frontier reads may be batched or parallelized when the provider permits it, while dependent discovery should stop as soon as the next safe action is established.

## Evidence reuse rules

Repository-tracked storage does not relax exact-head or other revision-bound evidence requirements.

- If cached CI/review evidence is bound to head `A` and the live head is still `A`, reuse is allowed only when every other applicability binding required by the governing policy remains established.
- If the live head moved to `B`, evidence for `A` becomes historical/stale for `B`; do not mark `B` qualified from the cache.
- If the head is unchanged but a relevant base, cumulative scope, configuration, environment, or provider identity changed, reassess the affected evidence instead of treating SHA equality as sufficient.
- A cached `success`, `approved`, `qualified`, thread count, or finding count never substitutes for the provider evidence locator and its current applicability.
- If the governing policy already permits valid evidence reuse, the operational checkpoint should make the binding easy to validate rather than force re-enumeration.

The ledger determines **what must be refreshed**; the provider determines **what is true**.

## Interrupted mutation recovery

If interruption may have occurred after an external mutation but before the checkpoint write, inspect the provider effect before retrying. The operational file is not proof that the mutation did or did not happen.

Recover ownership and the completed boundary of the mutation from provider facts and recorded preflight/commit-boundary observations. Do not create duplicate branches, PRs, review requests, comments, merges, deployments, or destructive cleanup because the cache is stale.

If ownership remains ambiguous, preserve the uncertain state and block the destructive/repeated mutation rather than manufacturing a clean resume state.

## Retention and completion

At handoff or completion, retain whatever checkpoint is needed for the repository's declared resume/audit horizon. A repository may archive, compact, or delete completed operational state under its own retention policy because the Work ledger is not product lifecycle authority.

Do not retain secrets, credentials, private tokens, unnecessary personal data, or raw transcripts merely because the operational ref is durable. Repository visibility and normal security policy apply to every committed operational artifact.

If a task requires stopping immediately after a final review request, follow the canonical Work-ledger stop boundary: persist the preflight checkpoint before the request and use the provider request event as the durable acquisition event. Do not mutate the operational ref after the request merely to record that the request was sent.
