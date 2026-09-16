# Integrated Publication Bundle v2

The public `publication_bundle.contract` validator and JSON schema define the versioned
Integration output. `integration/producer.py` is the independent implementation;
consumers must not import that implementation. The producer requires only its own exact
checkout and exact Composition/Policy checkouts, never a Site checkout or Site runtime.

Identity binds schema, Integration producer revision, provider revisions, configuration
and the complete payload inventory/digest. Canonical JSON sorts keys with ASCII escapes,
compact separators, no nonfinite numbers, and an LF. Execution timestamps and workflow
run/attempt IDs belong to separate transport evidence, never content identity.

The Bundle includes canonical and structurally valid current/stale translated publication content/assets, public
destinations, navigation and locale projections, exact translation availability, integrated
glossary, validated guided graph, immutable provider repository inventory and source bytes.
Site content slots contain declarations only; downstream Site supplies its own bytes.

Every regular source file is authenticated by Git blob identity and exact size. Viewable
UTF-8 text and bounded base64 evidence for non-viewable files feed the same eligibility
decoders as the producer. The complete regular corpus is limited to 64 MiB per provider,
with existing browser/preview candidate and aggregate bounds also retained. Missing or
extra eligible previews fail. Paths remain encoded model data, never extraction paths.

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
A stale derivative is never relabelled current. The availability submodel remains v1;
Bundle v2 explicitly changes the derivative publication contract from current-only v1.
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
