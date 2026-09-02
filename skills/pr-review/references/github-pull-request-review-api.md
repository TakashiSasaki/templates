# GitHub pull-request review API reference

This is a **non-normative provider integration reference** for GitHub. It does not define `pr-review` semantics, review completion, merge authorization, or a required result representation. The current GitHub API or connected-tool contract is authoritative for the actual request shape at submission time.

The provider-neutral `pr-review` procedure produces a conceptual result and an identity-bound completion handoff. A GitHub integration may translate that result into GitHub API requests only after performing the live identity revalidation required by the procedure.

## Review request concepts

GitHub review submission APIs commonly expose concepts including:

- a review `body`;
- a commit SHA used to anchor the submitted review to a proposed head;
- review actions/events such as `APPROVE`, `REQUEST_CHANGES`, and `COMMENT`;
- inline comment `path`;
- target `line` and `side`;
- optional multi-line `start_line` and `start_side`.

Those names are GitHub transport vocabulary. They are not provider-neutral `pr-review` conclusion values.

## Commit anchoring

When the GitHub API/tool supports a commit identifier for review submission, use the exact proposed-head identity that was revalidated immediately before output. A later GitHub submission must not silently retarget a completed handoff to a different head.

**GitHub API request example only; it is NOT the required output format of `pr-review`.**

```json
{
  "body": "Review completed for the revalidated exact head.",
  "commit_id": "0123456789abcdef0123456789abcdef01234567",
  "event": "APPROVE"
}
```

The event above is merely one possible GitHub request field. The conceptual provider-neutral conclusion remains governed by `skills/pr-review/SKILL.md` and the bound semantic review policy.

## Inline comments

For a finding that the current GitHub API can anchor to changed lines, integrations may use the line-based review-comment fields supported by GitHub. Confirm the current endpoint/tool contract before constructing the request because provider behavior may change independently of the review procedure.

**GitHub API request example only; it is NOT the required output format of `pr-review`.**

```json
{
  "body": "The error path can leave the generated state inconsistent.",
  "path": "src/example.py",
  "line": 42,
  "side": "RIGHT"
}
```

For a multi-line range, GitHub may additionally accept `start_line` and `start_side` together with the ending `line` and `side`. Use only combinations permitted by the current GitHub API/tool contract.

**GitHub API request example only; it is NOT the required output format of `pr-review`.**

```json
{
  "body": "This range performs a non-atomic read-modify-write sequence.",
  "path": "src/example.py",
  "start_line": 35,
  "start_side": "RIGHT",
  "line": 42,
  "side": "RIGHT"
}
```

## Findings that cannot be anchored inline

A conceptual blocking finding does not stop being a finding merely because GitHub cannot represent it as an inline comment. A GitHub integration may place such material in the review body or another provider-supported surface. Transport lossiness must not alter the provider-neutral conceptual result.

## Submission-time revalidation

Immediately before submitting or displaying a completed review through GitHub, re-resolve the current repository identity, pull-request identity, base, head, and complete best-common-ancestor set. Require the resulting unique merge base and all identities to match the completion handoff. If they do not match, do not submit the stale result; return to the invalidation path defined by `pr-review`.

No JSON example in this document is a review-result schema. No GitHub event string, request field, or response object proves that semantic analysis completed or that a merge is authorized.
