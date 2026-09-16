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

The transition is deliberately incomplete: Site still runs its historical local
Integration implementation and has not adopted this independent authority. Existing Site
machine discovery continues to describe that runtime state. This repository's authority
histories do not imply adoption of Composition's reusable hub-and-orphan topology.

The landed I1–I3 stack established contracts, mappings, locks, provenance, the independent
producer, public read-model contract, deterministic qualification and immutable transport. Promotion requires explicit review and qualification; an Integration release
stops before Site adoption. Nothing here deploys or automatically follows provider heads.

`site-manifest.json` is retained as the existing destination/reader-IA contract filename.
`integration/site-slots.json` declares downstream Site content slots, without copying their
presentation bytes. Those names are compatibility vocabulary, not Site implementation
inputs. Provider lock identities are independent of coding-agent/toolchain adoption pins.
