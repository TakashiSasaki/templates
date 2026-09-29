# Integrated Publication Bundle 5

Integration publishes a complete semantic snapshot. Site reads it without provider
checkouts or an Integration runtime. Any named provider with a
`docs/publication-catalog.json` can publish documents; glossary, translations and
source-index navigation are optional. See [the architecture](../../docs/asynchronous-publication.md).

`bundle.json` records the producer revision, a map of provider revisions, the build
configuration digest and the size and SHA-256 of every payload file. Its identity
hash covers this manifest. These revisions describe the bytes already built; they
are not source pins or an adoption transaction. Moving a branch does not invalidate
an existing Bundle. Timestamps and Actions run IDs are separate transport metadata.

The payload contains:

- `documents.json`: catalog IDs, source provenance and publication-relative paths;
- `publication/`: the declared Markdown, assets and translation derivatives;
- `translation-publication.json` and `translation-availability.json`: translated
  content destinations and provider-declared current/stale status;
- `glossary.json`: integrated terms;
- `guided-navigation.json` and `guided-locales.json`: optional source-index graphs;
- `provenance.json`: the sources and configuration used for this snapshot.

Every catalog document is included automatically. Canonical destinations are
`<provider>/<document-id>.md`, with `<provider>/index.md` for the provider home.
Cross-provider links can use `template:<provider>/<document-id>#fragment`. Site
resolves these IDs to its own public routes. Links to tracked source documents
outside a publication catalog use immutable GitHub URLs. Provider repository
inventories and unpublished source bytes are not shipped to Site.

Public URLs, audience assignment, navigation menus, Site-local pages and visual
configuration belong to Site. They are absent from this contract. A new provider
needs neither a new Bundle version nor a Site capability declaration. A malformed
optional source index produces a diagnostic; its catalog documents still publish.

[`bundle-v5.schema.json`](bundle-v5.schema.json) describes the manifest structure.
`publication_bundle.contract.validate` also checks actual payload hashes, safe
paths, closed inventory, provenance and model references. Consumers must validate
the bytes, not just the JSON schema. Corrupt or incomplete output is not published.

The old v3/v4 schemas remain only for isolated regression fixtures. The production
publisher and Site channel use v5; no migration or compatibility promise applies.
