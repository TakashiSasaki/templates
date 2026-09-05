# Delaying revision-bound qualification

This page explains the execution model behind the canonical `pull-request.defer-revision-bound-qualification-until-required` rule. It is explanatory guidance, not a second semantic authority. The canonical pull-request policy, repository-local requirements, release trust rules, and explicit task instructions remain authoritative.

## Why the distinction matters

Git creates an immutable commit identity for every construction step, but not every commit should immediately become a final acceptance identity. In stacked work, a lower-member repair can mechanically change descendant SHAs even when the descendants' local semantic responsibilities remain valid. If every transient descendant is deliberately treated as a final review, provenance, publication, or merge candidate, the workflow repeatedly pays exact-head CI, review, restack, and evidence-reacquisition costs for identities already expected to move.

The optimization is therefore not to avoid immutable Git objects. It is to delay **authoritative revision-bound binding** until an applicable boundary actually needs it.

## Identity lifecycle

Use four concepts when reasoning about a changing candidate:

| Concept | Meaning | Typical evidence |
| --- | --- | --- |
| Construction head | Exact commit currently representing work in progress | diff inspection, focused tests, branch topology |
| Provisional candidate | Construction state whose semantic work can proceed but whose final revision is not intentionally frozen | focused diagnostics, finding ledger state, local invariants |
| Qualification head | Intended candidate deliberately frozen because a revision-bound acceptance boundary now applies | required exact-head CI, independent review, merge readiness |
| Publication identity | Immutable revision, digest, or artifact identity made authoritative for release, provenance, distribution, or another consumer | release descriptor, provenance record, signed/pinned artifact |

A candidate may move through these concepts without introducing new Git object types. The distinction is semantic: it describes what the current exact identity is being relied upon to prove.

## Construction phase

During dependency-safe construction, continue useful implementation and focused validation even when an upstream member is not yet permanently stable. A downstream pull request may have an exact current head and a complete local delta while still remaining provisional.

Appropriate construction-phase work includes:

- implementing downstream logic that does not embed a known-invalid upstream assumption;
- focused unit, invariant, schema, or regression tests;
- self-audit and review-finding disposition;
- pull-request creation and explicit stack topology;
- naturally triggered CI; and
- preserving semantic evidence whose actual bindings remain unchanged.

A successful automatic CI run on a provisional head is useful observable evidence, but it does not by itself mean the workflow intentionally entered or completed final qualification.

## Freeze point

Freeze the intended qualification identity when an applicable authority-defined boundary now requires exact-revision evidence. Common freeze points include:

- intentional merge-acceptance review;
- final whole-stack audit when explicitly required by the task;
- merge-readiness evaluation;
- provenance or generated material that embeds an upstream exact revision;
- release promotion;
- installer or artifact publication; and
- another externally authoritative revision-bound operation.

At that point, stabilize the actual prerequisite identities, freeze the intended head or ordered stack heads, and acquire every exact-revision check required by the applicable authority. Delayed qualification never replaces those requirements.

## Stacked pull requests

For an ordered stack `A -> B -> C`, suppose `A` still requires a semantic repair while `B` and `C` can continue dependency-safe implementation.

The preferred construction model is:

```text
A: repairing
B: provisional local delta complete
C: provisional local delta complete
```

After the known compatible work converges:

```text
A*: stable candidate
B*: rebased/restacked only as actually required
C*: rebased/restacked only as actually required
```

Only when the next authority boundary requires revision-bound evidence are `A*`, `B*`, and `C*` intentionally treated as qualification heads and subjected to the applicable full exact-head qualification.

An ancestry change does not justify discarding semantic reasoning that is still applicable. It does invalidate evidence that was explicitly bound to the former exact revision. Re-evaluate bindings selectively rather than treating the entire work history as one indivisible snapshot.

## Review findings

Separate a finding's semantic repair state from its qualification freshness. A repair can be understood, applied, and supported by focused diagnostics while the descendant remains provisional. If later ancestry movement changes the exact head without invalidating the repair, preserve the finding identity and semantic disposition, mark revision-bound evidence stale only where necessary, and complete exact-head qualification when the applicable review or merge boundary is reached.

Before intentionally reacquiring merge-acceptance review, the existing canonical known-finding rule still applies: every known material actionable finding needs the required current-head validated outcome and closure evidence. Delayed qualification does not permit an unresolved finding backlog to be hidden behind a provisional-state label.

## Release and publication

The policy repository's existing candidate/promotion model is the clearest example of delayed immutable materialization. Candidate source is implemented and reviewed first; a later promotion change records the already-known full candidate SHA in release descriptors. Installer publication likewise writes the immutable installer/source identity only after those candidate identities exist.

Do not generalize this into mutable publication references. Once a revision becomes part of an executable, release, provenance, or distribution contract, use the immutable identity required by that contract.

## Anti-patterns

Avoid these patterns when no authority boundary requires them:

- treating every pushed descendant SHA as a final whole-stack candidate;
- deliberately reacquiring full review between compatible known repairs;
- rematerializing provenance that is already known to become stale after an upstream repair;
- rewriting an upper head solely to make it look fresh after an unrelated lower merge; and
- converting diagnostic metrics such as CI count or candidate-head count into new acceptance gates.

The opposite error is also invalid: do not skip required full qualification merely because focused diagnostics passed.

## Safety and operational exceptions

Do not delay a justified repair when waiting would create a concrete security, operational, data-integrity, or publication-integrity risk. Candidate stabilization and mutation batching are efficiency disciplines; they never make a known-defective state acceptable.

Likewise, when an authority-defined freeze point has already been reached, use the required immutable binding immediately. The principle is "bind late enough to avoid predictable churn," not "avoid immutable identity."

## Practical decision rule

Before deliberately starting a revision-bound evidence cycle, ask two questions:

1. **Which authority-defined operation needs this exact identity now?**
2. **Are any known prerequisite mutations still expected to change that identity or the material derived from it?**

If no current boundary needs the immutable binding, keep the work provisional and continue focused validation. If a boundary does need it, stabilize the prerequisites, freeze the qualification head, and perform the required exact-revision qualification.
