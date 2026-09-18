---
name: land-templates-stack
description: Load the immutable repository-maintainer landing procedure for a single or stacked templates authority change.
---

# Templates maintainer landing reference

This is a thin Composition-local reference shim. It does not reproduce landing
rules, CI/review acceptance, Composer semantics, or publication policy.

Read the adjacent version-2 `source.json`, require
`kind: repository-maintainer-skill-reference`, a full lowercase commit SHA,
the expected repository/path, the declared blob SHA, and the explicit
rule/planner closure. Prove every declared object at the exact revision before
reading it. The Skill's rule and review-scope planner must be loaded from that
same snapshot as
`repository-policy/stacked-pr-landing.md`; never substitute a Composition
worktree file, mutable `policy` branch, latest ref, or an unverified copy.
Missing, malformed, unavailable, or mismatched source identity or closure is
blocked.

At the pinned snapshot, load the canonical landing Skill and then the separate
local `.agents/skills/pr-merge-gate/SKILL.md` reference. The landing Skill
orchestrates the shared gate; it does not call this shim recursively. Keep
Composition implementation, schema, Composer, generated-output, release, and
publication evidence separate from the shared merge gate. A single PR and a
same-authority stack both use this route; actual merge authorization remains a
human-controlled boundary.

Report the repository, exact source revision, expected/observed blobs, exact
PR head, Composition-specific evidence, and the shared gate result. Do not
merge, auto-merge, publish, deploy, or use a mutable fallback from this shim.
