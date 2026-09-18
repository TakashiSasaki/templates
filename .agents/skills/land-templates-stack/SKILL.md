---
name: land-templates-stack
description: Load the immutable repository-maintainer landing procedure for a Policy authority change.
---

# Templates maintainer landing reference

This is a thin Policy-local discovery shim. Validate the adjacent
`source.json` and prove its repository, full lowercase revision, canonical
path, and blob identity before loading the pinned Skill. The canonical Skill
resolves the maintenance rule from that same immutable snapshot, never from
this worktree, a mutable branch, latest, or an unverified copy. Missing or
mismatched source identity is blocked.

After verification, follow the canonical Skill and then the local
`.agents/skills/pr-merge-gate/SKILL.md` shim. Validate that shim's separate
`source.json` before loading the pinned `skills/pr-merge-gate/SKILL.md` source.
The landing Skill orchestrates that shared gate without calling either local
shim recursively. This route applies to a single PR and a same-authority
stack; it does not authorize merge, auto-merge, publication, deployment, or
cross-authority history changes.
