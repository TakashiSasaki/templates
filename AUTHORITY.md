# Integration authority boundary

Providers own their source, local validation, catalogs, translations and semantic meaning.
Integration owns assembly, cross-provider relationships, publication routes and the Bundle.
Site owns presentation, browser behavior and Pages. None has an approval dependency on
its downstream consumer. Histories stay independent; share artifacts, never ancestry.

Builds follow configured provider branches and record the resolved commits in their
outputs. A source revision is not a consumer lock. Adding a provider or catalog document
uses generic publication; specialized rendering is optional. Do not rewrite provider
translation freshness or invent content, provenance or successful validation.

The operational design is [asynchronous publication](docs/asynchronous-publication.md).
