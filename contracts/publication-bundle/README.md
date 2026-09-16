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

Source eligibility is authenticated, including non-viewable files. The repository
model carries exact base64 blob bytes for non-viewable regular files; viewable
files retain their UTF-8 text. Consumers verify Git blob identities, exact sizes,
and shared decoder results before deriving the complete preview set. The complete
regular-file byte corpus is bounded to 64 MiB per provider before Git blob reads;
existing browser candidate, preview candidate and preview text limits still apply.
Non-viewable evidence is contract data and is never published as an inline preview.
Qualification uses `scripts/qualify_integration.py` and produces the same contract
as `scripts/produce_publication_bundle.py`, with a mandatory second generation and
content identity comparison. `scripts/render_publication_bundle.py` accepts only a
Bundle identity, Bundle directory, Site-owned source, and output/rendering options.
`qualify_bundle_renderer.py` exercises a real disposable checkout after physically
removing Integration implementation and omitting both provider checkouts.

Transport evidence is deliberately outside `bundle.json`: artifact ID/digest,
workflow head and run, attempt, successful uploading job and its creation window.
`ci_artifacts` validates this evidence before shared contract validation and atomic
extraction. The Site Pages identity records the adopted Bundle identity separately
from Site revision, preserving the contract for future Site-only fixes.
