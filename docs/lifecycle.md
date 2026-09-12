# Lifecycle contracts and repository ledgers

This Site-owned reader page explains how the repository's different ledger and
lifecycle-history mechanisms fit together. It is an integration explanation,
not a new semantic authority. Canonical product lifecycle semantics remain
owned by the `composition` provider, while repository-change and review
procedures remain owned by Policy.

## Why several ledgers exist

Git history, pull requests, CI runs, and review threads preserve important
provider facts, but they answer different questions from product contracts and
validated lifecycle history. The repository therefore uses several distinct
logical records instead of treating every persistent record as one generic
ledger.

| Record | Question it answers | Authority | Normal durable storage | Git tracked? |
| --- | --- | --- | --- | --- |
| Requirement / evidence ledger | What does the product require now, what contract targets implement it, and what proof is required or recorded? | Composition lifecycle contracts | `contracts/implementation-evidence.json` | Yes |
| Lifecycle checkpoint ledger | Which validated planning/product states form the product's semantic transition history? | Composition lifecycle contracts | `contracts/lifecycle-checkpoints.json` plus content-addressed `artifacts/lifecycle/...` snapshots | Yes |
| Review-finding ledger | Which material review findings remain applicable, what is their disposition, and what closure evidence exists? | Policy review procedure | Review/PR surfaces or execution state | Not required |
| Repository-change Work ledger | What is the current resumable state of a repository change, what evidence is bound to it, and what is the next safe action? | Staged Policy repository-change candidate | Provider-side PR/issue checkpoint plus execution-local state | No, by default |

These records are related, but none should silently replace another.

**Publication status:** the Requirement/Evidence and lifecycle descriptions
below reflect the currently selected Composition contracts, and the
review-finding model is already published Policy procedure. The Work-ledger
row describes the reviewed but unmerged Policy candidate in PRs `#754 -> #755`.
The anti-stall section below projects the separate staged Policy candidates
`#773 -> #774`. The Site currently publishes Policy revision
`5574ea46d2076bb1f5c51d4b0e8c9483a17d8fe2`, which contains neither staged
candidate set. Therefore both the Work-ledger candidate and the anti-stall
projection are staged architecture here, not current published Policy
authority.

## Requirement and evidence: current product state

The [Implementation evidence](implementation-evidence/) contract is the
canonical requirement/evidence ledger for a selected Composition lifecycle.
It connects stable requirement IDs to contract targets and, in product mode,
to implementation boundaries, positive and negative proofs, authoritative
commands, execution capabilities, and release gates.

Planning mode records target-bound requirements before implementation evidence
exists. Product mode preserves those stable requirement identities while
activating the implementation/evidence graph. The ledger therefore answers
"what is required and what evidence supports the current product state?" It is
repository-tracked because those claims are part of the consumer/product
contract itself.

## Lifecycle checkpoints: validated transition history

The [Lifecycle checkpoints](checkpoints/) contract preserves historical
transition evidence without replacing the requirement/evidence ledger. A
planning checkpoint freezes the exact validated contract baseline that product
implementation is expected to satisfy. A product checkpoint closes that
transition. Later specification changes create a new planning checkpoint
parented to the preceding product state.

Checkpoint chronology is expressed through sequence, parent edges, phase
alternation, and content hashes. Snapshot manifests bind the historical
contracts, schemas, validation result, and available Composition validation
authority. The result answers a different question from current evidence:
"which validated semantic state did this product state come from?"

## Review findings: review-process state

Policy's review-finding ledger tracks every known material actionable review
finding until the current-head disposition is validated and required closure
evidence is recorded. It is a logical tracking model rather than a mandatory
repository JSON/YAML artifact. A finding may be represented on an inline
review thread, a durable PR/review comment, a PR body section, or execution
state according to the active procedure.

Finding details remain in that ledger. Repository-change orchestration should
reference it rather than copying disposition, repair reasoning, qualification,
and closure evidence into a second authority.

## Work ledger: resumable repository-change state

A repository-change Work ledger serves a different purpose again: it is an
operational projection of a change in progress. Its logical state can include
objective and scope, authority snapshots, PR/branch topology, mutation units,
stability and qualification state, evidence bindings, blockers, asynchronous
dependencies, the review-finding-ledger reference, the next safe action, and
the selected stop/handoff boundary.

The Work ledger is repository-associated but should not normally be a
Git-tracked progress file. A progress-only commit would move the candidate SHA
and can stale exact-head CI or review evidence merely to record that evidence.
A provider-side PR/issue checkpoint keeps the operational state durable without
changing the source candidate. GitHub commit, branch, PR, CI, review, and merge
objects remain canonical provider facts; a Work ledger records observations
and bindings to those facts rather than overriding them.

The Work ledger is also not an agent transcript. It should checkpoint material
state transitions and preserve a concrete next safe action instead of logging
every fetch, command, or poll.

## Anti-stall repository-change behavior

Policy remains the semantic authority for anti-stall repository-change
behavior. This Site section is only a reader-facing projection of that Policy
model and does not define independent retry thresholds, failure classes, or
orchestration semantics.

This explanation is **staged** with Policy PRs `#773 -> #774`. Until the Site's
selected published Policy revision includes those semantics, readers should not
attribute this section to the currently published Policy artifact. Site
publication of this reader text does not itself promote or authorize the
staged Policy candidate.

The central distinction is that tool activity is not material progress. A
repository-change worker may fetch evidence, discover capabilities, inspect
logs, or report status without changing what is known about the objective. If
repeated attempts do not produce a decision-relevant knowledge or repository
state change, the worker must reassess the current diagnostic strategy rather
than treating more calls as progress.

A strategy switch changes something material about how the evidence gap is
being reduced: for example, the evidence source, method, or hypothesis. Merely
renaming an endpoint or repeating the same unavailable retrieval through an
equivalent path is not a new strategy. When a path has been invalidated, the
Work ledger records why it failed, where that conclusion applies, and the retry
condition that would make it reasonable to try again. This prevents an
interrupted session from rediscovering the same dead end simply because it is
a new session.

An external wait is also different from a diagnostic stall. Waiting for an
already-running CI check, review, or other provider event can be legitimate
when that event can change the completion state. While waiting, parallel work
is productive only when it advances the same completion frontier. A diagnostic
stall instead means that the current evidence-gathering approach is no longer
producing material progress and should be switched or declared blocked when no
allowed alternative remains.

For resume, the Work ledger preserves the evidence gap, current hypothesis,
attempted and invalidated paths, exhausted strategies, current strategy,
diagnostic budget, progress frontier, last material progress, provider-bound
qualification, and the next safe action. In that model, resume does not restart
the investigation: it restores the compact operational state needed to avoid
repeating failed exploration. Finding-level review state stays separate: the
review-finding ledger remains authoritative, and the Work ledger does not copy
finding-level disposition or closure evidence.

## Authority and storage boundary

A useful rule is to distinguish product state from worker state:

- requirement/evidence and lifecycle checkpoints are product semantic state or
  semantic history, so they belong in repository-tracked Composition
  contracts and artifacts;
- review-finding and Work ledgers are operational process state, so their
  durable representation normally lives on provider-side work surfaces and
  does not create a new product contract;
- CI results, reviews, commits, and pull requests retain their own provider
  authority. A ledger entry such as `success` is not evidence unless its exact
  binding and locator still apply.

Head or base movement therefore invalidates only the observations whose actual
bindings changed. Semantic implementation progress need not be discarded just
because an old exact-head qualification became stale.

## How the records connect

```text
repository change
    |
    +-- Work ledger ---------------------- resumable orchestration state
    |       |
    |       +-- references review-finding ledger
    |                     |
    |                     +-- finding -> disposition -> closure evidence
    |
    +-- changes product contracts
            |
            +-- requirement/evidence ledger --- current semantic state
            |
            +-- lifecycle checkpoints --------- validated transition history
```

This separation keeps repository work resumable without turning operational
progress into product authority, while keeping product requirements and
historical lifecycle evidence reproducible inside the repository.

## `templates` as a reference consumer

The repository itself provides concrete examples of these roles rather than
only documenting them for other consumers.

### Requirement / evidence example

In the current canonical Site base, `contracts/implementation-evidence.json`
is in `product` mode. It declares executable Website/PWA commands and connects
product requirements to implementation records, proof kinds, implementation
boundaries, and release gates. That file is product state: changing the claims
changes the consumer contract and therefore belongs in Git.

### Lifecycle-history example

The authority baseline contains the following six validated checkpoints:

```text
1  site-reference-adoption
   phase: planning
   changeKind: initial
   parentId: null
   snapshotPath: artifacts/lifecycle/001-site-reference-adoption
   manifestSha256: 9ec8d87ea01cf6f178422ca39589882ac3aac86dbc6084d7cc71f5a03df667d4

2  site-reference-adoption-product
   phase: product
   changeKind: initial
   parentId: site-reference-adoption

3  routes-v5-publication
   phase: planning
   changeKind: specification-change
   parentId: site-reference-adoption-product

4  routes-v5-publication-product
   phase: product
   changeKind: specification-change
   parentId: routes-v5-publication
   snapshotPath: artifacts/lifecycle/004-routes-v5-publication-product
   manifestSha256: c3ba91ed78fc90f780213b443182b17c38316d77d92f0151fb3d00392e77d9f1

5  webmcp-reader-publication
   phase: planning
   changeKind: specification-change
   parentId: routes-v5-publication-product
   snapshotPath: artifacts/lifecycle/005-webmcp-reader-publication
   manifestSha256: a6c587cac040a7929fe4fc020acd61843598b6447bd733795d83e2b7182104dc

6  webmcp-reader-publication-product
   phase: product
   changeKind: specification-change
   parentId: webmcp-reader-publication
   snapshotPath: artifacts/lifecycle/006-webmcp-reader-publication-product
   manifestSha256: 2b434f5636675eeacc0d6c4a9676f68a64c953abfada439b1306449ed31ea2a1
```

`site-reference-adoption` identifies the first validated planning baseline,
not an individual requirement. The next checkpoint consumes that identity as
its parent. The later `routes-v5-publication -> routes-v5-publication-product` and
`webmcp-reader-publication -> webmcp-reader-publication-product` pairs show
specification changes continuing the same linear history after the initial
product state. The root requirement/evidence ledger represents current product
state while these snapshots preserve the validated states it passed through.

### Review-finding and Work-ledger dogfooding

The repository has also exercised the operational side of the model in real
Policy work. Policy PR stack `#754 -> #755` formalized a repository-change Work
ledger and then used a canonical provider-side checkpoint on the stack-tip PR
to manage that same implementation. The checkpoint recorded the objective,
P1/P2 topology and exact heads, current versus stale CI bindings, the linked
finding ledger, blockers, next safe action, and the immediate-stop review
boundary. Finding-level disposition and closure stayed on a separate finding
surface instead of being copied into the Work ledger.

The reviewed staged identities are P1 / #754 head
`c2e23789ebabee4d1f35653e86ebe8f61ab6e8bf` and P2 / #755 head
`e73757b93bb7a97c2e6a618d899f652933c9c795`. That stack reached green
exact-head Policy CI and a clean Codex diagnostic review at the P2 head. The
example demonstrates resumability and authority separation, but it does
**not** make the Work ledger part of the currently published Policy authority
by itself.

## Published lifecycle destinations

The canonical lifecycle semantics and source documents below are owned by the
`composition` provider. This Site page supplies the stable `/lifecycle/`
reader entry point and groups the published destinations.

- [Composition state](composition-state/)
- [Contract evolution](contract-evolution/)
- [Implementation evidence](implementation-evidence/)
- [Lifecycle checkpoints](checkpoints/)
- [Release execution](release-execution/)
- [Release evidence](release-evidence/)
- [Release bundle](release-bundle/)

For the repository-wide ownership model and the separation between Policy and
Composition, see [Policy–Composition coexistence](../coexistence/).

These reader paths do not create a separate provider. Their provenance in a
built artifact resolves to the exact provider revisions recorded in
`build-provenance.json`.

### Topology publication remediation history

These additional checkpoints record the current remediation, not retrospective proof that planning preceded the earlier implementation.

| Sequence | Phase | ID | Snapshot | Manifest SHA-256 |
| --- | --- | --- | --- | --- |
| 7 | planning | topology-publication-remediation | artifacts/lifecycle/007-topology-publication-remediation | 5e2203e246437b1ff536430db4e042b403dab7c757b35c2a88447fbfda80c287 |
| 8 | product | topology-publication-remediation-product | artifacts/lifecycle/008-topology-publication-remediation-product | 3c10eceba4ada27893a6868a7fe9188ce02aab90e8cd641c68237d67cf9f94b8 |
| 9 | planning | topology-consumer-overview-remediation | artifacts/lifecycle/009-topology-consumer-overview-remediation | acdd54017dd8e0ca560cf1e91d25b3124953ea07b00faa49fe1d3f3cde7543ce |
| 10 | product | topology-consumer-overview-remediation-product | artifacts/lifecycle/010-topology-consumer-overview-remediation-product | 5c5f8aa08dfe96393a1de3552c16a1ccbeb366411d8688a044b31dca353cac57 |
