---
name: land-templates-stack
description: Load the immutable repository-maintainer landing procedure for a single or stacked Site authority change.
---

# Templates maintainer landing reference

## Purpose

This is a thin Site-local reference shim. Read and validate the adjacent
`source.json`, requiring the repository, full lowercase revision, canonical
path, and blob identity, then prove the pinned Skill blob at that exact
revision. The canonical Skill resolves
`repository-policy/stacked-pr-landing.md` from the same immutable snapshot;
never use a consumer/worktree copy, mutable branch, latest ref, or an
unverified local file. Missing or mismatched source identity is blocked.

## Use when

Use this route for a Site-maintainer single PR or same-authority stack before
the shared merge gate is evaluated.

## Do not use when

Do not use it for consumer adoption, provider publication, Site deployment, or
to reconstruct the canonical rule from local prose.

## Canonical authorities

The pinned landing Skill and its same-snapshot maintenance rule are canonical;
Site-specific acceptance remains owned by the Site skills and project policy.

## Inputs

Read `.agents/skills/land-templates-stack/source.json` and record its expected
and observed blobs, repository, revision, path, and current PR head.

## Loading workflow

After verification, follow the canonical landing Skill and the existing local
`.agents/skills/pr-merge-gate/SKILL.md` shim. The landing Skill orchestrates
the shared gate without recursive shim calls. Keep Site source-ready,
browser/PWA, publication, Integration selection, artifact, and deployment
evidence separate from PR acceptance. A single PR and a same-authority stack
use this route; it does not authorize merge, auto-merge, publication, or
deployment.

## Stop conditions

Stop as blocked for missing or malformed source metadata, unavailable objects,
path/blob mismatch, mutable fallback, unresolved Site acceptance, or an
unresolved shared gate. Do not infer merge authorization from CI or review
absence.

## Evidence to report

Report the immutable source identity and observed blob, Site-specific
acceptance evidence, shared gate result, exact PR head, and separate
publication/deployment state.
