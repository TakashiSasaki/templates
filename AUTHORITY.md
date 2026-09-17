# Authority contract: reusable information models

## Decision rights

`modeling` owns the meaning, identity, conformance constraints, and lifecycle of reusable information models explicitly authored or accepted here. Examples include information structures, controlled vocabularies, classification models, identifier schemes, local application profiles, and locally asserted semantic mappings.

It also owns its descriptive records and administrative record schemas. Ownership of a record does not imply ownership of the resource described. Governance here means normative decision rights, not copyright, hosting, publishing, or endorsement.

## Negative scope

Do not absorb a resource because its filename says schema, registry, catalog, profile, or vocabulary. Composition retains component/recipe, resolver/planner, lifecycle, topology, and managed-product contract semantics. Policy retains agent operating policy and repository-change orchestration. Integration retains cross-provider qualification, provider selection, publication protocols and bundles. Site retains presentation, browser runtime, accessibility, packaging, and deployment.

This authority has no approval right over unrelated changes in those domains. No automatic provider following, downstream adoption, publication cutover, or deployment is authorized.

## External and local resources

An external resource's normative owner remains its upstream authority. Local records must identify both that owner and their own record authority. Unknown facts are explicitly unknown. Never infer upstream approval from a local record.

A local profile owns its selections and additional constraints, not the definitions of its bases. A local mapping owns its assertions, not either endpoint. A local transcription or conversion is not an official upstream representation unless its provenance establishes that status.

## Identity and relationships

Separate resource identity, release/edition, representation, artifact, distribution/access, observed snapshot, record revision, and Git revision. A URL, digest, alias, and redirect are not interchangeable identities. Preserve upstream identifiers and version labels; do not invent an official identifier for an external authority.

Use typed assertions with subject/object scope, provenance, asserting party, and applicable versions. References, imports, profiles, restrictions, extensions, specialization, equivalence, exact/close match, broader/narrower, mapping, derivation, supersession, requirements, and membership are not a single dependency edge. SKOS matching is not OWL identity. Do not claim profile conformance merely because a schema extends another file.

Discovery collection membership does not imply dependency or adoption. A normative closed inventory or bundle must explicitly declare a different contract. Generated indexes are projections, not independently editable authorities.

## Validation and tooling

Separate normative definition, conformance constraints, validator implementation, test vectors, and validation results. Implementations are supporting/reference artifacts unless explicitly declared normative with runtime and precedence rules. Do not let implementation accidents silently define semantics.

Model-specific headless implementations may live here. Generic engines remain independently governed dependencies. Site owns demonstrations' UI and runtime, not the underlying model's constraints. Runtime failure or an unsupported constraint is not conformance.

## Lifecycle and history

This branch has its own root history. Never merge, rebase, or cherry-pick another authority's history into it. Adopt external/provider artifacts using explicitly selected immutable revisions and provenance instead.

A model release, record correction, implementation release, consumer adoption, Integration qualification, Site adoption, and deployment are distinct boundaries. Discovery references do not create a normative dependency. Actual semantic dependencies must be explicit and must not form circular authority decision rights.

Do not let qualification against Integration's publication protocol become the source of this authority's model semantics. Upstream freshness checks propose changes; they never silently change an existing release.

## Rights, provenance, and language

Do not mirror external full text, datasets, or software without checking applicable rights per artifact. An access URL is not permission to redistribute. A digest proves byte identity, not authenticity, authority, licensing, or future availability.

Canonical local governance documentation is English. Describe English-source standards in English and Japanese-source standards in Japanese. Translations must be labeled non-canonical and linked to their source; do not create competing normative translations.

The authority is pre-production. Backward compatibility with accidental local structure is not required, but semantic changes and their consumers must remain explicit.
