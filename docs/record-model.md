# Resource description record 0.1 (draft)

This is a local administrative contract for `records/*.json`, not a claim to own the described standards. The canonical contract combines `schemas/resource-record-0.1.schema.json` (shape) and the semantic invariants below. The collection schema governs discovery collections only. Neither schema redefines Composition, Policy, Integration, or Site semantics.

## Source and identity

Each file is the authoritative **description record**, not the upstream resource. `id` is a repository-and-authority-scoped record key; it is not an identifier minted on behalf of an external standard. `resourceId` identifies its subject. `identityBasis` distinguishes an upstream identifier, a descriptive upstream entrypoint, and a locally authored identifier. Do not treat a selected homepage as an upstream-assigned persistent identifier. `recordRevision` versions the description separately from its subject. An existing record's material metadata correction increments this number.

An edition has its own ID and label. Labels preserve the upstream versioning system. The initial inventory is not an exhaustive release history and makes no latest-release guarantee. A distribution identifies a particular role and access mechanism, not a new edition. Multiple serializations do not establish semantic equivalence. Alias support and cached upstream snapshots are deliberately not part of this draft; extend the contract explicitly before adding them.

## Ownership and authority

`recordAuthority` is always `modeling`; `ownership` and `normativeAuthority` describe the **subject**. An external subject cannot name Modeling as its normative owner. A local subject must explicitly identify Modeling. Editorial assertions do not transfer ownership, imply upstream approval, or make the source trustworthy.

Resource kind is descriptive; it is not an ownership inference. Existing Composition/Policy/Integration/Site contracts are not migrated just because they use a registered language.

## Language

`canonicalLanguage` is the language of the canonical entry. Titles, descriptions, notes, and generated resource documentation use it. This draft supports canonical entry languages English and Japanese; add renderer coverage before admitting another canonical language. Distribution languages can differ. The NDC entry is Japanese; local schema and governance documentation are English. A future translation needs an explicit non-canonical marker and source relationship; parallel unmarked normative translations are not supported by this draft.

## Discovery, references, and relationships

Every initial registration has `purpose=discovery`, `adoption=not-adopted`, and `endorsement=not-assessed`. Inclusion does not adopt the resource, endorse it, or grant access rights. Collection membership has the same non-normative meaning; normative bundles need a separate explicit contract.

Relationships use absolute predicate IRIs, an object identity, asserting party, origin, normativity, evidence, scope, and optional subject/object editions. Local assertions must identify Modeling as the asserting party. Upstream assertions must not be attributed to Modeling. A subject edition must exist in the containing record. If an object is registered and its edition is supplied, that edition must exist in the target record. This is metadata checking, not an entailment engine or proof of equivalence/profile conformance. Source evidence must be inspected before a normative mapping is accepted.

Use the actual semantics of established predicates. Do not conflate `skos:exactMatch`, `skos:closeMatch`, `owl:sameAs`, `owl:equivalentClass`, `rdfs:subClassOf`, `prof:isProfileOf`, `dcterms:requires`, `dcterms:references`, `dcterms:isPartOf`, and `prov:wasDerivedFrom`. Import edges must retain the governing language's import semantics. A circular reference graph is not automatically a circular authority decision graph.

## Distributions, rights, and verification

External distributions are **references only** in this draft. `bytePin` must be null; no remote checksum is invented and no upstream bytes are mirrored. A known download reference is not proof of reachability. `access` describes access to the referenced item, not redistribution rights. Rights are per distribution. `not-assessed` is not permission. `identified` requires an explicit license URI and evidence source; it is not a legal compliance certification. A restricted full classification and a public subset must remain distinct resources.

The publication capability declaration uses two separate terms for the bounded export: `subject_ownership=external-as-recorded` says that Modeling does not claim normative ownership of the referenced subject, while `redistribution=local-record-metadata` says that only the locally authored record JSON may be copied into an Integration Bundle. It does not permit retrieval or redistribution of an external documentation, schema, dataset, or software payload. The exporter and canonical record validator enforce this distinction.

Local schema artifacts use a repository-relative path and SHA-256 of their exact bytes. Paths must be contained, normalized, non-symlink files; a checksum pins bytes, not authority or license. The current contract has no mechanism for admitting external cached snapshots; that requires explicit rights/provenance review and an extension rather than relabeling external content as local.

`metadata-observed` records a bounded inspection of a primary source page and requires a date. It does not claim a distribution download, rights clearance, current-latest verification, or conformance execution. `reference-not-verified` has no observation date. `recordedOn` is the local record creation/update date, not the source publication date. Source observations must not postdate that record date.

## Standards reuse and limits

The initial records are **plain JSON**, validated by JSON Schema 2020-12. They are not JSON-LD and do not claim DCAT, DCAT-AP, ADMS, MOD, or PROF conformance. A future RDF export must have a pinned context/profile, shape validation, explicit loss analysis, and tests. This avoids inventing a misleading RDF context before its semantics are implemented.

Conceptual crosswalk (not an executable equivalence mapping):

| Local concern | Established vocabulary candidate | Limitation |
| --- | --- | --- |
| Descriptive record / subject | DCAT CatalogRecord / FOAF primaryTopic | A record is not its subject. |
| Title, source, language, edition relations | DCTERMS | Publisher is not necessarily normative owner. |
| Structured asset identifiers | ADMS | Registration does not assign external identity. |
| Profile bases and supporting roles | PROF | Require actual profile conformance semantics. |
| Observations, agents, derivation | PROV-O | Provenance is not authentication. |
| Concept schemes and matching | SKOS | Matching is not OWL individual identity. |
| Class/property assertions | RDFS / OWL | Do not silently weaken predicate semantics. |
| Distribution integrity / licensing | SPDX terms and identifiers | Verify applicability separately. |

The controlled values in this schema are administrative local terms, not a repository-wide semantics vocabulary. This draft does not implement schema validation of the registered external subjects. It validates their **records** only.

## Lifecycle

Model definition, normative constraints, implementation, test corpus, and result evidence have distinct responsibilities. A validator implementation is reference/supporting unless explicitly designated normative. Report failure/unsupported/unknown separately from nonconformance. Never let a browser demo introduce unnamed constraints.

Local validation is offline after dependency installation. Upstream re-verification is a separate intake activity. Never update a registered release or mutable-source observation inside an ordinary build. Integration and Site must independently and explicitly adopt a qualified exact revision before any publication; this branch does not change their locks or release protocols.
