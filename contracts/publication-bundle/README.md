# Integrated Publication Bundle v3/v4

Bundle schema 3 remains valid for the committed Composition + Policy lock.
Bundle schema 4 is the explicit three-provider extension: `modeling`,
`composition`, and `policy`. A v4 Bundle is never inferred from a v3 content
digest; schema, provider set, producer revision, and identity must all match.

Unlike v3, a v4 manifest carries an Integration-normalized `requirements`
closure and its `requirements_digest`. Each entry names the provider that
declared the requirement, its required/optional status, and the only permitted
fallback. The closure is part of Bundle identity. Site compares this exact
property with its support contract; it never reads raw provider declarations.

The public `publication_bundle.contract` validator and JSON schema define the versioned
Integration output. `integration/producer.py` is the independent implementation;
consumers must not import that implementation. The producer requires only its own exact
checkout and exact Composition/Policy checkouts, never a Site checkout or Site runtime.

Identity binds schema, Integration producer revision, provider revisions, configuration
and the complete payload inventory/digest. Canonical JSON sorts keys with ASCII escapes,
compact separators, no nonfinite numbers, and an LF. Execution timestamps and workflow
run/attempt IDs belong to separate transport evidence, never content identity.

The v3 inventory is structurally closed: the producer derives an exact qualified
`publication/` output set from the authoritative document destinations, provider
asset declarations, and translation-publication declarations. Sealing requires
the physical output set to equal that qualified set plus the nine named semantic
models. `bundle.json.files` records that already-validated result; it does not
authorize arbitrary files that happened to exist before sealing. Undeclared
sidecars and provider repository/source corpora are therefore invalid regardless
of path suffix or content. Semantic source paths, exact provenance, guided
navigation and ordinary publication content remain valid; the contract does not
classify JSON by field names.

The Bundle includes canonical and structurally valid current/stale translated publication content/assets, public
destinations, navigation and locale projections, exact translation availability, integrated
glossary and validated guided graph. Exact provider revisions remain in provenance and
the graph; Site source browsing uses immutable GitHub URLs instead of receiving provider
repository inventories or source bytes.
Site content slots contain declarations only; downstream Site supplies its own bytes.

The current guided-navigation read model is schema v2. Its provider discovery root is the
authority-root `index.md`, and each provider record retains the exact provider revision and
Git blob identity for every reachable index. The validator continues to read historical
schema-v1 graphs rooted at `docs/index.md`; new graph generation never falls back to that
legacy root.

The guided graph JSON Schema is a structural precheck, not a standalone acceptance
validator. Consumers MUST run the public `publication_bundle.graph.load_graph` on
the raw graph file and `validate_provider_graph` for each provider, using the
schema-selected root and provider order. Full Bundle consumers should use
`publication_bundle.contract.validate`, which already performs these checks.
JSON Schema treats `2`, `2.0`, and `2e0` as the same integer value; the canonical
runtime deliberately requires integer JSON tokens for schema versions, section
levels, depths, line numbers, and diagnostic counts. Decimal/exponent spellings
and booleans are rejected. Do not weaken that canonical check or claim acceptance
from a schema-only pass; provenance and cross-record constraints also require the
public validator.

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
