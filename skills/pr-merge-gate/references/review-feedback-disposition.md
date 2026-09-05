# Review feedback disposition

This reference is provider-neutral procedure support for `pr-merge-gate`. It does not create semantic review policy, change finding severity, or make an otherwise non-blocking suggestion merge-blocking.

Use it when clearing submitted review findings or review threads under `pull-request.close-review-threads-before-merge`. A material finding remains a review item even when the provider exposes it only in a top-level review body or another non-resolvable surface. For GitHub-specific acquisition and finding-representation guidance, consult `github-review-finding-representation.md`; that reference is non-normative adapter guidance rather than semantic authority.

## Establish the evidence first

Treat reviewer text as a defect hypothesis, not as authority and not as a command to edit code. Reproduce or falsify the claim against the current proposed head, applicable authority, realistic execution or consumer path, and available tests/CI evidence.

If the evidence is still insufficient to determine what happened, keep the item unresolved. Do not force an uncertain item into a final category merely to close the thread.

Historical or stale-head review comments may be useful diagnostic inputs, but they are not exact-head acceptance evidence. Re-evaluate any still-material hypothesis against the current head before using it to justify a repair or a no-change disposition.

## Audit bounded sibling dimensions after a verified invariant break

When a review item is verified as an `actual-defect`, `invariant-gap`, or `regression-test-gap`, identify the material invariant that failed before choosing the final repair boundary. Inspect only the bounded sibling dimensions that share that same root cause and are realistically reachable in the changed execution or consumer path.

Useful sibling dimensions include:

- success versus failure completion for the same asynchronous operation;
- current versus stale generation, root, selection, or target state;
- a listed relation versus the required converse or completeness condition;
- missing, malformed, extra, duplicate, or internally inconsistent structured fields consumed by the same boundary;
- direct load versus remount, navigation, retry, recovery, or same-document transition for the same lifecycle;
- viewport assumptions versus the actual containing layout or resource boundary; and
- one validated identity/provenance field versus sibling fields that jointly establish the same trusted record.

This is a bounded root-cause audit, not permission for open-ended neighboring cleanup. Stop when the shared invariant and its materially reachable sibling dimensions are covered. Do not delay a ready safety-critical repair merely to search for hypothetical variants. Record any verified sibling defect as its own independently addressable item when it requires distinct remediation or validation.

## Assign one primary disposition

Once the evidence is sufficient, assign exactly one primary disposition to the review item:

1. `actual-defect`
   - The reviewed change introduces or exposes a reachable failure that violates an applicable contract, invariant, or required behavior.
   - Repair the smallest generalized root cause rather than only the reported symptom. Add or strengthen a regression guard when that is an appropriate durable proof of the repair.

2. `invariant-gap`
   - The reported failure is real, but the durable problem includes a missing or under-specified invariant, authority boundary, validation rule, lifecycle constraint, or other generalized guard.
   - Repair the immediate changed behavior and identify the correct authoritative destination for the missing generalized guard. Do not silently turn explanatory prose or the review comment itself into authority. If the authority repair is legitimately separate work, record that boundary explicitly rather than pretending the gap was closed by the local symptom fix.

3. `regression-test-gap`
   - The implementation may already satisfy the intended behavior, but required executable evidence does not exercise the changed behavior, failure path, or invariant through the repository's real test/CI discovery path.
   - Add or repair the smallest regression guard that proves the relevant behavior, and verify that the repository's actual runner discovers and executes it. A merely present test file is not sufficient evidence.

4. `documentation-ambiguity`
   - The implementation can be correct while current normative or user-facing documentation materially permits a conflicting interpretation of the changed contract, authority, lifecycle, or operational behavior.
   - Clarify the authoritative or reader-facing source at the layer that owns the ambiguity. Do not change executable behavior solely to match a mistaken reading when the behavior is already correct.

5. `reviewer-misunderstanding`
   - Current evidence falsifies the review claim: the cited path is unreachable, an upstream guard prevents the failure, the reviewer used the wrong authority or runtime semantics, or the claimed impact is otherwise not present in the proposed change.
   - Make no appeasement edit. Record a concise evidence-backed no-change explanation that identifies the decisive falsifying evidence, then close the thread when repository mechanics permit.

6. `unrelated-suggestion`
   - The suggestion is not caused by the proposed change, is outside the accepted PR scope, or is an optional improvement without merge-relevant impact under current authority.
   - Record it as non-blocking and out of scope for the current repair. Create separate follow-up work only when useful; do not expand the current PR merely to satisfy an unrelated suggestion.

The primary disposition describes the remediation reason and does not override severity or finding validity. Do not use `reviewer-misunderstanding`, `documentation-ambiguity`, or `unrelated-suggestion` to downgrade a verified reachable defect. Likewise, do not label an unsupported hypothesis `actual-defect` merely because a reviewer used blocking language.

## Record the disposition

For each material review item, preserve enough information to audit closure:

- the review/thread identity or other stable locator, including a separately identifiable top-level finding when no thread exists;
- the exact proposed head against which the claim was verified or falsified;
- the primary disposition;
- the decisive evidence or reproduced failure;
- the action taken, including the repair/guard/documentation change or the explicit no-change reason;
- the validation evidence establishing the disposition for the current head;
- any follow-up authority or scope boundary that remains intentionally separate.

Prefer the smallest generalized repair that closes the established root cause. Do not scatter speculative edits across neighboring code or policy just because they are adjacent to the review topic.

If the repair changes the proposed head, the old exact-head CI and review evidence becomes stale as defined by the canonical pull-request policy. Reacquire only the evidence invalidated by that change.

## Closure

For a material finding with a resolvable review thread, resolve the thread only after its disposition and required action are complete and validated for the current head, or after an evidence-backed no-change disposition is recorded and validated. Thread resolution is bookkeeping evidence of disposition; it is not proof that the underlying review claim was correct or that remediation was valid.

For a material finding with no resolvable thread, perform the same evidence, disposition, action, and validation work and record finding-level closure evidence on an available surface. The absence of a thread is not evidence that no unresolved finding exists. Do not infer resolution from a code change alone, and do not treat provider UI state as a substitute for validated remediation.

Do not leave a verified defect open merely because it was first reported on an older head. Conversely, do not keep a stale or falsified historical comment merge-blocking solely because it exists.
