---
name: maintain-progressive-discovery
description: Discover, classify, validate, and safely maintain semantic index.md navigation boundaries from authoritative repository inventories.
---

# Maintain progressive discovery

<!--
agent-policy-generated: true
source-skill: maintain-progressive-discovery
DO NOT EDIT DIRECTLY
-->

Use this Skill when a repository has opted into the `progressive-discovery`
Policy profile and needs to keep `index.md` navigation aligned with documents,
components, recipes, schemas, policy rules, records, generated documentation,
or publication surfaces.

The Skill is repository-neutral. Read the repository's `.progressive-discovery.json`
adapter when present; it may declare only local facts such as authoritative
inventory paths, generated-index targets, the root index, closed inventories,
curated shortcut boundaries, and explicit exclusions. It must not redefine the
shared semantics. A curated shortcut says that an ancestor index intentionally
links directly to important descendants; it does not cause the Skill to rewrite
or delete an existing nested authored index.

Run the bundled script from the repository root. In a distributed consumer the
path is under `.agents/skills`; in the Policy source tree it is under `skills`:

```sh
python3 .agents/skills/maintain-progressive-discovery/scripts/maintain_progressive_discovery.py --root .
```

The default is a dry-run discovery and validation. Use `--format json` for a
machine-readable report. `--apply` is the explicit mutation authorization; it
updates only generated index outputs declared by the adapter and refuses to
overwrite a curated authored index. Run the command again after applying and
require the second report to be idempotent.

The workflow is:

1. discover the repository revision, policy selection, existing indexes,
   authoritative inventories, generated/source ownership, publication presence,
   provider-maintenance versus consumer-distributed surfaces, and exclusions;
2. classify meaningful boundaries as `authored-index-needed`,
   `generated-index-needed`, `index-unnecessary`, or `authority-needed`;
3. present create, update, delete, or regenerate plans without mutating in
   dry-run mode;
4. when `--apply` is explicitly authorized, mutate only declared generated
   outputs and preserve curated content;
5. validate authored grammar, local-link safety and fragments, nested-index
   reachability, expected-document coverage, and generated freshness;
6. report applied changes, exclusions and their reasons, unresolved authority
   decisions, and validation results.

The expected discoverable set comes from authoritative inventory data before it
comes from existing indexes. An existing index is not proof that a boundary is
still meaningful. A physical directory with one deep important document may be
skipped in favor of a direct link, and an adapter can record an intentional
curated shortcut when several deep documents are routed by an ancestor index. A
consumer without a publication system is valid; do not invent publication
metadata to satisfy the Skill.

The script is intentionally conservative about authored indexes. To change
curated navigation, make that source change explicitly and rerun validation;
the Skill can identify the missing or stale boundary without destroying curated
shortcuts.

For a repository-local adapter, keep validation commands and inventory paths
local. Do not copy this Skill into `repository-skills/` as a competing generic
implementation; enable the immutable Policy-distributed Skill through the
consumer's `.agent-policy.yml`.
