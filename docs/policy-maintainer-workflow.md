# Maintaining the policy provider with its own best practices

This page explains how maintainers of this repository apply the same shared engineering discipline that the policy toolchain publishes for consumers without allowing an in-flight policy change to authorize or validate itself. It is explanatory documentation, not a second semantic policy authority.

## Two policy layers apply to maintainers

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

## When not to delay

Delayed qualification is not a reason to leave a harmful or invalid state in place. Apply an urgent security, operational, data-integrity, publication-integrity, or equivalent material repair as soon as its remediation is justified. Likewise, when an authority boundary has already been reached—such as merge authorization, final independent review, stable release promotion, installer publication, or another immutable consumer binding—use the exact identity and full qualification that boundary requires.

The optimization is to delay **unnecessary final binding**, not necessary repair or required evidence.

## What self-host adoption means

The coding context in `.agent-policy.yml` selects the shared `core`, `security-baseline`, and `pull-request` profiles and layers the files under `repository-policy/` on top. Consequently, a newly promoted shared coding rule becomes maintainer guidance when the repository later advances its immutable self-host toolchain pin through the normal adoption process; the rule does not need a duplicate repository-local version.

The review context similarly combines shared review policy with the same repository-local authority inputs. Keep coding and review projections generated from their declared contexts rather than maintaining handwritten parallel instruction sets.

## Completion and evidence

At handoff or completion, report the exact source candidate, validation evidence, review state, release/promotion state, and self-host adoption state separately. A change can be source-complete and CI-green while stable promotion or self-host adoption is intentionally still pending. Do not describe those later trust transitions as complete until their own reviewed operations have occurred.

For stacked work, also distinguish provisional descendants from frozen qualification heads in the handoff record. This makes it clear which SHAs merely represented construction history and which exact revisions are intended to carry current revision-bound evidence.
