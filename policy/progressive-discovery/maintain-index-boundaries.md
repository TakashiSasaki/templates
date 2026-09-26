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

Each authority has one root `index.md`. All operational navigation indexes,
including the root, are front-matter-free. An authored index has a level-one
title, useful section headings, ordinary Markdown links and short boundary
paragraphs explaining location, responsibilities and non-responsibilities, adjacent
areas, authoritative definitions and next steps. Physical directories need not
have an index; ancestor deep links and useful nested indexes may coexist. It must not duplicate path metadata, timestamps, Git identities,
provenance, release state, or other data owned by a catalog, manifest, schema,
or record. A README explains what a directory is; an index explains where to go
next. Boundary prose is orientation, not a second ownership schema or an
OKF bundle declaration. Fixture and distributed material indexes are not thereby
operational navigation in the provider checkout. Links in code, comments and
quotations do not establish navigation.

A generated index is a projection of an authoritative inventory or other
declared source of truth. Generate it deterministically, validate its freshness,
and do not hand-edit it. The expected discoverable set must be derived from
authoritative inventories, catalogs, manifests, registries, schemas, contracts,
records, or documentation manifests before consulting an existing index; an
existing index alone cannot prove completeness.

When a relevant source, document, component, recipe, schema, policy rule,
record, generated document, or publication surface changes, re-run the
repository's discovery validation against those authoritative sources. Keep
proposed navigation changes distinguishable from completed changes, preserve
authored ownership, and respect the repository's mutation authorization boundary.
Provider-maintenance documentation and consumer-distributed documentation are
separate surfaces, and a consumer without a publication system must not be
forced to invent one. Repository-local adapters may add validation commands,
authoritative inventory locations, and explicit exclusions, but may not redefine
these generic semantics.

Local adapters must keep bootstrap entry requirements independent of existing
indexes. Distinguish file, directory entry, index, source input, foreign reference
and deployment location. A directory entry may lead to its operational index;
it does not prove reachability of all files beneath it. Keep global exclusion,
per-index nonpublication and delegated internal enumeration independent, with
reasons and diagnostics for contradictions. Delegating interior management does
not remove the required entry or explicitly inventoried members.

Inventory extraction must use declared namespaces and bounded selections or
domain-owned projections, never arbitrary filename-shaped strings or embedded
domain ID resolution rules. Missing, malformed, ambiguous or stale inputs must
not silently become empty successful inventories. Discovery input inventories
must themselves remain discoverable. Adapters configure local validation and
generation, not repository topology, authority ontology or executable hooks.

Schema, runtime and adapter versions must agree through supported launch and
distribution paths. Candidate semantics remain proposals until explicitly
accepted and adopted; preserving a legacy qualification path during migration
does not authorize a mixed-version operational configuration.
