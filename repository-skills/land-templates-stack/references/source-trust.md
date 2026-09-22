# Source Trust and Immutable Reference Verification

This reference contains detailed procedures for verifying immutable sources and operating the pre-request review planner guard. Consult this file only when validating source references or preparing a review planner packet.

## 1. Five-Step Source Reference Verification

Every consumer entry point must provide a version-2 `source.json` for `land-templates-stack` and a separate `source.json` for `pr-merge-gate`. Validate each reference before using the referenced text:

1. **Schema and revision**: Require the source-reference schema, a full lowercase 40-hex Git commit SHA, and an explicit immutable closure list.
2. **Repository and blob bindings**: Require repository `TakashiSasaki/templates`, the expected canonical path, and the declared blob SHA.
3. **Storage existence and blob equality**: Prove that the commit object, canonical Skill path, and every declared closure path/blob exist in Git storage and that `git rev-parse <revision>:<path>` equals each declared blob SHA.
4. **Snapshot retrieval**: Read the maintenance rule and the review-routing planner explicitly from the same immutable snapshot as this Skill, for example:
   - `git show <revision>:repository-policy/stacked-pr-landing.md`
   - `git show <revision>:repository-skills/land-templates-stack/scripts/plan_review_scope.py`
   rather than resolving a relative path in the consumer worktree.
5. **Fail-closed stop**: Stop as blocked on an invalid SHA, missing object or path, closure/blob mismatch, repository mismatch, or mutable fallback such as `latest`, a branch, or an unverified local copy.

## 2. Trust Anchor Separation

- The maintenance-rule revision and the shared gate revision are separate trust anchors.
- Do not treat a full SHA as evidence that the source was reviewed or adopted.
- A locally available Git object is an acceptable retrieval mechanism only when it proves the same immutable identity; network retrieval is not a reason to substitute a mutable ref.
- The canonical rule and this Skill are expected to be in the same frozen source snapshot. The source reference must resolve the rule through that snapshot, not through a consumer's same-named `repository-policy/` file. This prevents a downstream checkout from shadowing the canonical rule and keeps the source closure explicit.

## 3. Review Scope Planner Pre-Request Guard

The planner (`repository-skills/land-templates-stack/scripts/plan_review_scope.py`) is the canonical **adaptive scope selection** guard and an ephemeral, read-only pre-request guard.

- **Packet Construction**: Build its JSON packet from the live PR topology, exact bindings, authority-owned impact facts, local and remote evidence, known finding references, and actual request state.
- **Immutable Invocation**: Invoke the planner from the verified immutable snapshot before any external review request.
- **Action Selection**: Follow its selected action:
  - reuse explicit coverage;
  - reconcile an in-flight or submission-unknown request;
  - run an explicitly selected early diagnostic;
  - request independent delta coverage;
  - request the related stack; or
  - stop to acquire missing facts or hand off.
- **Authority Boundaries**: The planner never sends a request, interprets semantic test results, or authorizes a merge.
- **Concurrency & CAS**: Use the existing Work ledger action-ownership/CAS procedure when an adopted backend provides it; do not invent an idempotency guarantee or a lock service.
