---
name: land-templates-stack
description: Load the immutable repository-maintainer landing procedure for a single or stacked Modeling authority change.
---

# Templates maintainer landing reference

This is a thin Modeling-local reference shim. Validate the adjacent
`source.json` and prove its repository, full lowercase revision, canonical
path, and blob identity before loading the pinned Skill. The canonical Skill
resolves `repository-policy/stacked-pr-landing.md` from that same immutable
snapshot, never from this worktree, a mutable branch, latest, or an unverified
copy. Missing or mismatched source identity is blocked.

After verification, follow the canonical Skill and the separately pinned local
`pr-merge-gate` shim. The landing Skill orchestrates the shared gate without
calling this shim recursively. Keep Modeling record/catalog generation,
qualification, and documentation evidence separate from PR acceptance. A
single PR and a same-authority stack use this route; it does not authorize
merge, auto-merge, Integration adoption, Site adoption, or deployment.
