---
name: land-templates-stack
description: Load the immutable repository-maintainer landing procedure for a single or stacked Integration authority change.
---

# Templates maintainer landing reference

This is a thin Integration-local reference shim. Read `.agents/skills/land-templates-stack/source.json`, validate the repository, full lowercase revision, canonical path, and blob identity, and prove the blob at the exact revision before loading the canonical Skill.

The pinned Skill resolves `repository-policy/stacked-pr-landing.md` from the
same immutable snapshot. Do not use a consumer/worktree copy, mutable branch,
latest ref, or historical PR text. Missing, malformed, unavailable, or
mismatched source identity is blocked.

After source verification, follow the canonical Skill and the separate
`.agents/skills/pr-merge-gate/SKILL.md` shim. The landing Skill orchestrates
that shared gate and does not call this shim recursively. Keep Integration's
provider tuple, Bundle, receipts, deterministic qualification, and Site
adoption/deployment boundaries separate from the shared PR acceptance gate.
This route applies to a single PR and a same-authority stack; it does not
authorize merge, auto-merge, publication, deployment, or provider-lock changes.
