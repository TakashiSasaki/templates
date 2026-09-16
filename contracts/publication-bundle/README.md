# Integrated Publication Bundle v1

`publication_bundle.contract` is the shared contract validator. Producer and renderer
implementations must not import one another. Consumers validate exact expected identity
and revisions, the entire file inventory, model closure and provenance before rendering.

A Bundle directory contains `bundle.json`, the named JSON models in `MODELS`, canonical
and translated provider bytes under `publication/`, and immutable bounded source records.
Site-owned document records are slots; Site supplies those bytes downstream. No provider
checkout or network fetch is a renderer input. Repository filenames are encoded data,
never extraction paths. Provider source inventory includes all tree entries; viewable
source content retains the existing bounded UTF-8/browser/preview rules.

The manifest identity is SHA-256 of canonical JSON without `identity`. The content digest
is SHA-256 of the canonical exact payload inventory. JSON canonicalization sorts keys,
uses ASCII escapes and compact separators, prohibits nonfinite numbers, and ends in LF.
Execution metadata and archive transport digests are external evidence, not payload.
Producer provenance changes alter identity even when provider payloads remain equivalent.
