---
name: land-templates-stack
description: Load the immutable repository-maintainer landing procedure for a single or stacked Integration authority change.
---

# Templates maintainer landing reference

This is a thin Integration-local reference shim. Read the version-2
`.agents/skills/land-templates-stack/source.json`, validate the repository,
full lowercase revision, canonical path, blob identity, and rule/planner
closure, and prove every declared object at the exact revision before loading
the canonical Skill.

The pinned Skill resolves `repository-policy/stacked-pr-landing.md` from the
same immutable snapshot. Do not use a consumer/worktree copy, mutable branch,
latest ref, or historical PR text. Missing, malformed, unavailable, or
mismatched source identity or closure is blocked.

After source verification, follow the canonical Skill and the separate
`.agents/skills/pr-merge-gate/SKILL.md` shim. The landing Skill orchestrates
that shared gate and does not call this shim recursively. Keep Integration's
provider tuple, Bundle, receipts, deterministic qualification, and Site
adoption/deployment boundaries separate from the shared PR acceptance gate.
This route applies to a single PR and a same-authority stack; it does not
authorize merge, auto-merge, publication, deployment, or provider-lock changes.

Before an independent review request, use the pinned review-scope planner with
the exact provider tuple, Bundle contract, ordered members, local preflight
result, existing review coverage, and request state. Integration's cheap checks
are exact provider inputs, owner/destination closure, collision detection,
deterministic pack/extract/consumer paths, and negative receipt/identity
fixtures. A declared provider-reference update inside the current Bundle
contract can use an independent exact-head delta review; a Bundle/protocol,
cross-provider closure, transport binding, trusted-controller, promotion, or
authorization change expands to the related Integration stack. Provider-source
review and tuple qualification remain separate. An existing result is reusable
only when its explicit candidate, tuple, purpose, coverage, and completion
bindings still apply; CI success or cost does not waive independent review.
