---
id: discovery.maintain-index-boundaries
severity: mandatory
overridable: true
order: 360
---
# Maintain progressive-discovery index boundaries

When a repository opts into this profile, maintain `index.md` files as semantic
discovery boundaries rather than as a mirror of the physical filesystem. Add an
authored index only where a meaningful group of related destinations needs an
orientation point; a deep destination may be linked directly and a directory
may deliberately have no index. Classify each relevant directory as needing an
authored index, a generated index, no index, or an explicit authority decision.

An authored index is a small navigation document: a level-one heading, useful
section headings when needed, Markdown links, short descriptions, and blank
lines. It must not duplicate path metadata, timestamps, Git identities,
provenance, release state, or other data owned by a catalog, manifest, schema,
or record. A README explains what a directory is; an index explains where to go
next.

A generated index is a projection of an authoritative inventory or other
declared source of truth. Generate it deterministically, validate its freshness,
and do not hand-edit it. The expected discoverable set must be derived from
authoritative inventories, catalogs, manifests, registries, schemas, contracts,
records, or documentation manifests before consulting an existing index; an
existing index alone cannot prove completeness.

When a relevant source, document, component, recipe, schema, policy rule,
record, generated document, or publication surface changes, re-run the
repository's progressive-discovery maintenance Skill. The Skill may propose
create, update, delete, or regenerate operations in dry-run mode, but it may
mutate authoritative sources only after an explicit apply authorization.
Provider-maintenance documentation and consumer-distributed documentation are
separate surfaces, and a consumer without a publication system must not be
forced to invent one. Repository-local adapters may add validation commands,
authoritative inventory locations, and explicit exclusions, but may not redefine
these generic semantics.
