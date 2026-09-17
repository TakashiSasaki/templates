# Integration qualification and release boundary

Construction uses focused tests. At a stabilized qualification frontier, run the full
contract suite and `scripts/qualify_integration.py` with full producer/provider SHAs.
It validates every Bundle model and generates twice from identical exact inputs.
Existing Policy evidence-applicability and expected-invalidation rules apply. This
bootstrap adds no parallel frontier model or mandatory ledger schema.

The `Validate Integration authority` workflow validates the exact proposed head and
calls Integration qualification. It checks out only Integration, Composition and Policy,
with read-only contents/actions permission, and stops at the immutable Bundle artifact.
There is no Site checkout, rendering/browser/PWA lane, Pages artifact or deployment.

Default companions come from `publication-sources.json`. Explicit full-SHA candidate
overrides and staged mappings qualify compatibility without writing the lock. The
read-only `classify_publication_freshness.py` reports current/different for exact selected
and observed revisions; it never adopts either input. A green candidate is not adoption,
promotion, a Site release, or deployment authorization.

The sequence is provider candidate → Integration candidate → qualification → explicit
reviewed Integration promotion → STOP. To promote later, refresh exact merged provider
SHAs, deliberately change only intended locks, qualify a stable exact candidate, obtain
applicable review, and guard the Integration merge by its accepted head. Record the exact
released producer/provider identities and Bundle identity/digests. Requalify changed
inputs; do not reuse stale evidence. The first reviewed bootstrap release is
`a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d` (#894–#896). Its provider pair and
payload reference remain historical bootstrap evidence, separate from the current
reviewed provider selection. Release acceptance is established by exact-head review,
qualification and guarded landing; an authority status string is not acceptance.

Site adoption requires a separate explicit human instruction selecting an exact reviewed
Integration release and Bundle identity. Site qualification/release and explicit deployment
remain separate, Site-owned actions. Integration releases can occur without Site releases;
Site-only runtime fixes must be able to retain the same adopted Integration input.

## Local qualification

Install the locked minimal dependency closure in an isolated environment and run pip
check. Materialize provider-owned declared outputs with
`scripts/materialize_publication_assets.py --publication composition=ROOT --publication policy=ROOT`.
Then run:

```
python -m unittest discover -s tests -v
python scripts/qualify_integration.py \
  --integration-root ROOT --producer-revision FULL_SHA \
  --composition-root COMPOSITION_ROOT --composition-revision FULL_SHA \
  --policy-root POLICY_ROOT --policy-revision FULL_SHA \
  --output OUTPUT_OUTSIDE_SOURCE_CHECKOUTS
```

Historical P5 bootstrap equivalence remains documented in the archived bootstrap
evidence, but it is not part of the current Bundle-v3 qualification workflow. The
browser/source-corpus payload was intentionally removed from the public contract, so
future candidates are qualified against the current producer and exact provider inputs.

## Immutable transport and reuse

`ci_artifacts` is materialized from the already qualified shared transport implementation.
It verifies artifact digest and safe extraction; Bundle validation verifies schema,
producer/provider identities, full inventory/content digests, all projections and
provenance. Reuse also binds workflow run/head, attempt, artifact namespace, the unique
successful uploading job and creation time inside that attempt's producing-job window.
Corrupt or misbound evidence fails closed; absent evidence can require regeneration.
No workflow timestamps, run IDs or attempt counters contaminate deterministic identity.
The artifact is a candidate artifact, not an automatically promoted release.

The current output contract is Bundle v3: structurally valid stale reader derivatives
remain available with exact provider-owned reviewed/current canonical evidence, while
provider repository source/tree payloads are no longer transported for Site browsing.
The P5/P7 releases used v1 current-only publication and P8 used v2. This breaking version
change does not update Site, provider translation prose, or synchronization hashes. Site
adoption and warning presentation remain a separate human decision.
