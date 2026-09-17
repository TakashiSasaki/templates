# Primary sources, licensing, and coverage

This branch contains descriptive references, not copied standards or classification databases. Sources are recorded in each record's provenance. A source review is scoped: metadata inspection is not distribution retrieval, conformance validation, authenticity verification, or legal clearance. Unverified references remain visibly unverified.

The initial collection covers DCAT, DCTERMS, ADMS, PROF, PROV-O, SKOS, RDF, RDFS, OWL 2, MOD, SSSOM, ISO/IEC 11179-3, JSON Schema, SHACL and SHACL 1.2, SPDX, DataCite, RO-Crate, ODRL, JSON-LD, URI/RFC 3986, SemVer, XSD, MODS, PREMIS, NDC, UDC and UDC Summary, DCAT-AP, and FOAF. The local resource-record schema is separately described. This is coverage of the design discussion, not an adoption manifest or an exhaustive standards registry.

Primary upstream source language controls resource documentation. NDC is documented in Japanese. English-source specifications and local governance documents are documented in English. Generated prose takes its language and authoritative content from the record; generation does not create an independent translation.

## External material

Do not copy a complete standard, ontology, schema, license text, or database solely because its URL is public. Review the rights of the exact artifact first, including attribution, modification, and redistribution conditions. Do not apply one license across unrelated representations. ISO full text, the full UDC database, and NDC classification tables are not included here.

A future admitted snapshot must record exact source, edition, retrieval provenance, byte digest, applicable rights evidence, base URI, and reference closure. The current draft deliberately rejects external local-path artifacts. Such an extension needs its own design, validation, and review; an agent must not evade it by changing ownership to local.

The bounded publication export is narrower still: `subject_ownership` records the normative owner of the described external subject, and `redistribution` records what the Bundle may carry. Modeling's record export is `external-as-recorded` plus `local-record-metadata`; it carries only the locally authored administrative JSON. A reference URL or download URL is never fetched or vendored by publication materialization.

## Adoption is separate

A record's `not-adopted` state describes this inventory's registration act. It does not claim that no other authority or outside project uses the standard. Downstream adoption is a consumer fact, not an endorsement inferred from registration.

No legal license is assigned to upstream content by this repository. No new blanket license grant for local material is made by this bootstrap; licensing of local contributions is a maintainer decision.
