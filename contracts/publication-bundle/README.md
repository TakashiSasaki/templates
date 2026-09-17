# Integrated Publication Bundle v3

The public `publication_bundle.contract` validator and JSON schema define the versioned
Integration output. `integration/producer.py` is the independent implementation;
consumers must not import that implementation. The producer requires only its own exact
checkout and exact Composition/Policy checkouts, never a Site checkout or Site runtime.

Identity binds schema, Integration producer revision, provider revisions, configuration
and the complete payload inventory/digest. Canonical JSON sorts keys with ASCII escapes,
compact separators, no nonfinite numbers, and an LF. Execution timestamps and workflow
run/attempt IDs belong to separate transport evidence, never content identity.

The v3 inventory is structurally closed: it contains the nine named semantic models
and the exact qualified `publication/` outputs declared in `bundle.json.files` only.
The validator compares that declaration with the physical Bundle inventory, so any
undeclared sidecar is invalid regardless of its path suffix or content. Semantic
source paths, exact provenance, guided navigation and publication content remain
valid; the contract does not classify ordinary publication content by field names.

The Bundle includes canonical and structurally valid current/stale translated publication content/assets, public
destinations, navigation and locale projections, exact translation availability, integrated
glossary and validated guided graph. Exact provider revisions remain in provenance and
the graph; Site source browsing uses immutable GitHub URLs instead of receiving provider
repository inventories or source bytes.
Site content slots contain declarations only; downstream Site supplies its own bytes.

Provider-owned translation manifests are authenticated against their exact source
checkouts during production. The Bundle carries the resulting translation availability,
exact source identities and published derivatives, but no provider repository tree or
source corpus. Paths remain encoded model data, never extraction paths.

The validator parses each authenticated provider `translations/manifest.json` with the
same authority-content parser used by the producer. Reader languages, declaration
closure, reviewed canonical identities and missing coverage are derived from those
manifests and compared to the Bundle; self-declared coverage cannot hide or invent
translations. The provider contract permits an absent manifest, but existing manifests
and all declared paths must be regular sources without symlink traversal.

Derivative destinations use the same deterministic language namespace function as
the producer. The complete files in each declared language namespace must equal
the qualified derivative set. All Markdown publication files must also be canonical
documents or qualified derivatives, because provider catalog contracts prohibit
Markdown assets. This rejects orphan translations even after a language loses its
last declaration.

Both current and stale declared reader translations must be published. Missing means
no reader declaration exists for that canonical page/language; declared missing files
remain failures. Availability preserves the owning provider, language, canonical and
translation paths, reviewed canonical blob and current authenticated canonical blob.
A stale derivative is never relabelled current. The availability and translation
submodels remain v1; Bundle v3 is a breaking transport change that removes the
provider repository/source-corpus model from the public contract.
Current-only fragment reconciliation is not applied to stale prose: newer English cannot
prove its intended fragment. Existing safe path/link projection remains mandatory.
Consumers must use the supplied status and canonical destination; freshness is not a
runtime computation. Site warning UI and adoption require separate authorization. Provider translation content and synchronization metadata are
read directly from their owning exact authority checkouts and are not Integration sources.

The P5 comparison records landed Site Bundle identity and payload hashes in
`bootstrap/site-bundle-reference.json`. All provider publication/read-model payloads and
provider glossary terms must match. Producer/provenance identity and Integration-owned
cross-authority glossary attribution/wording are the explicitly allowed differences.
This historical bootstrap comparison is not a permanent constraint on future reviewed
provider advancement; normal candidate qualification verifies current exact inputs.
