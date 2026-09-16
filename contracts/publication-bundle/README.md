# Integrated Publication Bundle v1

The public `publication_bundle.contract` validator and JSON schema define the versioned
Integration output. `integration/producer.py` is the independent implementation;
consumers must not import that implementation. The producer requires only its own exact
checkout and exact Composition/Policy checkouts, never a Site checkout or Site runtime.

Identity binds schema, Integration producer revision, provider revisions, configuration
and the complete payload inventory/digest. Canonical JSON sorts keys with ASCII escapes,
compact separators, no nonfinite numbers, and an LF. Execution timestamps and workflow
run/attempt IDs belong to separate transport evidence, never content identity.

The Bundle includes canonical and current translated publication content/assets, public
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

Only current translations are published. Stale and missing availability remain distinct;
P5 does not implement P8. Provider translation content and synchronization metadata are
read directly from their owning exact authority checkouts and are not Integration sources.

The P5 comparison records landed Site Bundle identity and payload hashes in
`bootstrap/site-bundle-reference.json`. All provider publication/read-model payloads and
provider glossary terms must match. Producer/provenance identity and Integration-owned
cross-authority glossary attribution/wording are the explicitly allowed differences.
This historical bootstrap comparison is not a permanent constraint on future reviewed
provider advancement; normal candidate qualification verifies current exact inputs.
