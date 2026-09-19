# Resource intake and maintenance

This English document applies the authority contract to the current record profile. It does not transfer another authority's decisions into Modeling.

## Choose the right change

| Contribution | Appropriate change |
| --- | --- |
| External specification, vocabulary, schema, or classification | External descriptive record with upstream normative owner; reference-only distributions |
| New locally governed information model | Local definition plus explicit normative scope, conformance policy, versioned record, and tests |
| Restriction of an external model | Local profile with scoped constraints and attributed relationships; preserve its bases |
| Local semantic correspondence | Attributed mapping/assertion with endpoint versions, evidence, and applicability |
| Composition component contract or Policy operational profile | Change its current authority; optionally expose discovery metadata without transferring ownership |
| Integration provider selection or publication protocol | Integration change, not a Modeling metadata edit |
| Vocabulary browser or validator demo UI | Site change; consume an explicitly selected model/engine |

The initial records are plain JSON administrative records. Their use of familiar concepts or external predicate URIs is not a claim of DCAT, ADMS, PROF, MOD, or JSON-LD conformance. A standards-based export needs a named, validated profile and an explicit crosswalk. Do not maintain independently editable JSON and RDF copies of the same record.

## Worked entry points

`records/dcat.json` illustrates an externally owned resource with a bounded primary-page observation. `records/mod.json` deliberately declines to assert a fixed edition when the inspected generated page has inconsistent version cues. `records/premis.json` distinguishes the observed ontology page from an unverified landing page and unpinned XSD reference. `records/udc-summary.json` separates a subset from the full UDC system and leaves unverified rights unresolved.

`records/ndc.json` and `docs/resources/ndc.md` are canonical Japanese. Their source evidence distinguishes a printed edition, the MRDF10 machine-readable offering, and the NDC 8/9 Linked Data work. Do not rewrite these descriptions into English merely because the branch's governance documentation is English. A future translation must be labeled non-canonical and must not replace the Japanese source.

`records/resource-record.json` describes a genuinely local administrative schema. Its local artifact digest must match `schemas/resource-record-0.1.schema.json`. Modifying that schema requires updating its record's artifact digest and evaluating the schema/profile revision. This does not turn the registered external resources into locally owned definitions. In the publication declaration, the external subject ownership and the permission to redistribute the local record metadata are separate fields; no external distribution bytes are in the export.

## Minimal safe edit

1. Inspect the live authority head and the current record; read the actual primary source.
2. Change the individually authored source record. Preserve its subject identity and upstream owner; increment `recordRevision` for a record edit. Never replace an old exact artifact silently under the same release identity.
3. Add or refine edition, distribution, relationship, and provenance entries only to the extent supported by evidence. Keep unobserved values explicitly unknown.
4. Regenerate with `python tools/catalog.py generate`; qualify with `python tools/qualify.py`.
5. Inspect both authored and generated diffs, create the appropriate stacked PR, and state the source/rights limitations and exact validation evidence.

If a generated resource file is obsolete after an intentional removal, the generator fails rather than silently deleting it. Inspect the file and remove that work-owned obsolete projection explicitly, then regenerate. This is not permission to delete unrelated files or history.

## Review checklist

Check decision rights before syntax. Verify that the record owner is not being substituted for the upstream authority, a landing page is not presented as an immutable artifact, a subset is not presented as a full system, and an implementation is not silently made normative.

Check original language, identifiers, edition labels, status scope, each distribution's access/rights, and the difference between metadata observations and byte verification. Verify relation types and attribution; resource registration does not establish equivalence, endorsement, or adoption.

Check source/projection freshness and the actual canonical test entrypoint. Adding a test file alone is not coverage: it must be discovered and executed by `tools/qualify.py` and the effective CI lane. Tests validate metadata invariants, not the truth of semantic assertions.

## Current representational limits

This initial profile supports English and Japanese entry documentation, HTTP(S) resource identifiers, reference-only external distributions, and local in-tree schema/model artifacts with SHA-256. It does not yet provide arbitrary identifier schemes, aliases, externally cached snapshots, RDF entailment, schema payload validation, a release lock/closure resolver, executable package distribution, or normative bundle/adoption state.

These omissions are not statements that those concepts are invalid. They are explicit extension boundaries. Introduce the required contract and negative tests before adding them; never encode them under a semantically wrong existing field. A canonical identifier that cannot be represented must not be replaced with a made-up upstream identifier to satisfy the checker.

## Release and publication

The recorded edition label is not a Git commit, and a metadata-only correction is not automatically a semantic model release. A digest verifies specified local bytes, not authority, provenance trust, licensing, or perpetual retrievability.

Before future reproducible model adoption, define the exact release, representations, import/reference closure, base URIs, engine/dialect settings, and rights-compatible retention plan. Refresh checks propose new observations instead of mutating existing release inputs during builds.

The intended provider flow is Modeling to Integration to Site, with optional explicit Composition/Policy consumption. Discovery references are not normative dependencies. Keep model semantics independent of downstream presentation and qualification. Integration qualification, Site adoption, and deployment each require separate authorization and are not enabled by adding a record here.

## Discovery index generation safety

`tools/catalog.py generate` delegates `docs/resources/index.md` writes to the
selected immutable Policy discovery CLI after verifying its distribution lock.
It checks for an already unsafe index before generating other catalog outputs.
The CLI re-plans and revalidates ownership at its mutation boundary; a dirty or
authored index is refused, never overwritten. Generation is not a transaction:
if a later discovery apply is refused, the command exits nonzero and reports
which catalog outputs were already changed. Review those changes and the
reported index refusal before retrying.
