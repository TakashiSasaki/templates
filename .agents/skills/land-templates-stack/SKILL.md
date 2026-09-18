---
name: land-templates-stack
description: Load the immutable repository-maintainer landing procedure for a single or stacked Site authority change.
---

# Templates maintainer landing reference

This is a thin Site-local reference shim. Read and validate the adjacent
`source.json`, requiring the repository, full lowercase revision, canonical
path, and blob identity, then prove the pinned Skill blob at that exact
revision. The canonical Skill resolves
`repository-policy/stacked-pr-landing.md` from the same immutable snapshot;
never use a consumer/worktree copy, mutable branch, latest ref, or an
unverified local file. Missing or mismatched source identity is blocked.

After verification, follow the canonical landing Skill and the existing local
`.agents/skills/pr-merge-gate/SKILL.md` shim. The landing Skill orchestrates
the shared gate without recursive shim calls. Keep Site source-ready,
browser/PWA, publication, Integration selection, artifact, and deployment
evidence separate from PR acceptance. A single PR and a same-authority stack
use this route; it does not authorize merge, auto-merge, publication, or
deployment.
