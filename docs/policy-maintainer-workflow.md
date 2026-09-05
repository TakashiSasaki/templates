# Maintaining the policy provider with its own best practices

This page explains how maintainers of this repository apply the same shared engineering discipline that the policy toolchain publishes for consumers without allowing an in-flight policy change to authorize or validate itself. It is explanatory documentation, not a second semantic policy authority.

## Two policy layers apply to maintainers

Maintenance of this repository deliberately combines two different authorities:

1. **Shared application-neutral policy** lives under `policy/` and is selected through profiles such as `core`, `security-baseline`, `pull-request`, and `review`.
2. **Policy-provider-specific maintenance requirements** live under `repository-policy/` and cover this repository's authority boundaries, release trust, toolchain safety, documentation ownership, and maintainer validation.

Do not copy a repository-specific maintenance rule into the shared corpus merely because a maintainer must follow it. Conversely, when a best practice retains the same meaning for unrelated repositories and agents, prefer one shared canonical rule and let this repository consume it through its configured profiles.

## Self-hosting must remain non-self-authorizing

`.agent-policy.yml` intentionally pins the shared toolchain by full immutable commit SHA. Generated maintainer instructions such as `AGENTS.md`, `.review-authority/review-policy.md`, and generated `.agents/skills/**` are therefore projections of a previously established toolchain revision plus the repository-local policy inputs recorded in `.agent-policy.lock`.

An unreviewed change to shared policy in the current branch must not become the authority that declares that same change acceptable. During development, follow the currently pinned generated instructions and repository-local policy. Treat new shared policy text under review as the proposed product being evaluated, not as retroactive authorization for the work that introduced it.

Do not directly edit generated maintainer outputs or `.agent-policy.lock` to make an in-flight source change appear adopted. Regenerate them only through the documented pinned-toolchain process when the authoritative inputs and intended self-host revision have legitimately changed.

## Maintainer change workflow

For ordinary policy-provider maintenance:

1. Establish the change contract, authority owner, non-goals, and applicable repository-specific invariants before editing.
2. Keep application-neutral semantics in the shared `policy/` corpus and repository-identity-specific maintenance requirements in `repository-policy/`.
3. During implementation, use focused diagnostic validation and the adversarial cases appropriate to the changed invariant. For review-derived defects, inspect bounded sibling dimensions that share the established root cause rather than repairing only the reported symptom.
4. Stabilize the intended candidate before deliberately acquiring expensive revision-bound qualification. Batch compatible known repairs so exact-head evidence is not repeatedly invalidated by avoidable intermediate heads.
5. Run the maintainer validation baseline and every applicable exact-head remote check required by current repository authority. Diagnostic success is not a substitute for required qualification.
6. Before intentionally requesting revision-bound review, preflight the current head and every revision identity named by the request. Treat provider invocation failures separately from completed substantive review.
7. Preserve the existing reviewed-candidate and separate-promotion trust boundary for stable toolchain/runtime movement. A source-policy PR does not self-promote merely because its tests pass.
8. After a shared-policy candidate has been independently reviewed and promoted through the normal immutable release process, update this repository's self-host toolchain pin only through a separate reviewed maintenance change when adoption is intended. Regenerate the lock and generated outputs from that newly authorized pin and verify them as derived artifacts.

This sequence lets maintainers benefit from new shared best practices without creating a circular trust chain.

## What self-host adoption means

The coding context in `.agent-policy.yml` selects the shared `core`, `security-baseline`, and `pull-request` profiles and layers the files under `repository-policy/` on top. Consequently, a newly promoted shared coding rule becomes maintainer guidance when the repository later advances its immutable self-host toolchain pin through the normal adoption process; the rule does not need a duplicate repository-local version.

The review context similarly combines shared review policy with the same repository-local authority inputs. Keep coding and review projections generated from their declared contexts rather than maintaining handwritten parallel instruction sets.

## Completion and evidence

At handoff or completion, report the exact source candidate, validation evidence, review state, release/promotion state, and self-host adoption state separately. A change can be source-complete and CI-green while stable promotion or self-host adoption is intentionally still pending. Do not describe those later trust transitions as complete until their own reviewed operations have occurred.
