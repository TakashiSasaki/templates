# Integration authority

Integration selects exact reviewed Composition and Policy revisions and produces a
versioned deterministic Integrated Publication Bundle. Provider semantics and source
translations remain owned by their providers. Site owns rendering, browser/PWA runtime,
Pages packaging and explicit deployment.

The first reviewed bootstrap release is
`a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d` (#894–#896). The initial anchor has independent
history. `bootstrap/provenance.json` records the landed Site snapshot and its reviewed
provider pair; bootstrap did not adopt newer provider heads. Subsequent explicit
promotions select exact inputs in `publication-sources.json` without changing that proof. `bootstrap/materialization.json`
records source blobs copied without transferring foreign Git history.

Site adopted an exact reviewed Integration release in #901 and added stale-translation
warnings in #902. It consumes the immutable Bundle without provider checkouts or
Integration implementation internals. Its explicit `integration-source.json` may
remain pinned while Integration advances; this authority never updates that selection.
This repository's independent histories do not imply adoption of Composition's reusable
hub-and-orphan topology.

The landed I1–I3 stack established contracts, mappings, locks, provenance, the independent
producer, public read-model contract, deterministic qualification and immutable transport.
The current Bundle v3 contract carries semantic publication/navigation projections and
exact provenance, not provider repository source corpora for a Site-owned browser.
Promotion requires explicit review and qualification; an Integration release stops before
Site adoption. Nothing here deploys or automatically follows provider heads.

`site-manifest.json` is retained as the existing destination/reader-IA contract filename.
`integration/site-slots.json` declares downstream Site content slots, without copying their
presentation bytes. Those names are compatibility vocabulary, not Site implementation
inputs. Provider lock identities are independent of coding-agent/toolchain adoption pins.

## Local validation

Run `python3 scripts/run_integration_preflight.py fast --expected-head "$(git rev-parse HEAD)"`
while editing or before a commit. Before starting expensive CI, run the clean
exact-head gate:

```sh
HEAD_SHA=$(git rev-parse HEAD)
python3 scripts/run_integration_preflight.py ready \
  --expected-head "$HEAD_SHA"
```

`ready` adds the reviewed publication-source lock, exact producer identity,
deterministic fixture Bundle generation and local pack/extract round-trip. The
`providers` profile is explicit and requires exact Composition and Policy roots
and revisions; it performs local provider materialization and qualification
without resolving mutable branches. GitHub artifact identity, immutable upload,
run/attempt evidence and cross-authority candidate qualification remain remote.
