# Integration qualification and release boundary

Construction uses focused tests. At a stabilized qualification frontier, run the full
contract suite and `scripts/qualify_integration.py` with full producer/provider SHAs.
It validates every Bundle model and generates twice from identical exact inputs.
Existing Policy evidence-applicability and expected-invalidation rules apply. This
bootstrap adds no parallel frontier model or mandatory ledger schema.

The `Validate Integration authority` workflow validates the exact proposed head in its
contracts job. Its qualification job is intentionally explicit `workflow_dispatch` only:
the operator must provide full producer, Composition and Policy SHAs (and may provide a
Modeling SHA for Bundle v4). Pull-request and push checks do not silently qualify against
the legacy reviewed lock, whose providers predate this declaration contract. Candidate
events and the dispatch path call Integration qualification with exact provider checkouts.
The qualification workflow checks out only Integration and the named providers, with
read-only contents/actions permission, and stops at the immutable Bundle artifact.
There is no Site checkout, rendering/browser/PWA lane, Pages artifact or deployment.

Default companions come from `publication-sources.json`. Explicit full-SHA candidate
overrides and staged mappings qualify compatibility without writing the lock. The
read-only `classify_publication_freshness.py` reports current/different for exact selected
and observed revisions; it never adopts either input. A green candidate is not adoption,
promotion, a Site release, or deployment authorization.

The initial sequence is provider candidate → Integration candidate → qualification →
Shadow report → STOP. After the one-time activation contract is reviewed and enabled,
the trusted controller may perform the pre-authorized mechanical promotion and guarded
auto-merge for an eligible exact candidate. It still cannot bypass branch protection,
required review, freshness, or the separate Site boundary. To promote a candidate,
refresh exact provider SHAs, deliberately change only intended locks, qualify a stable
exact candidate, and guard the Integration merge by its accepted head. Record the exact
released producer/provider identities and Bundle identity/digests. Requalify changed
inputs; do not reuse stale evidence. The first reviewed bootstrap release is
`a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d` (#894–#896). Its provider pair and
payload reference remain historical bootstrap evidence, separate from the current
reviewed provider selection. Release acceptance is established by exact-head review,
qualification and guarded landing; an authority status string is not acceptance.

Site adoption remains a separate Site-owned boundary. In the initial Shadow mode it is
report-only; after activation the trusted controller may create an idempotent Site lock
PR for the exact Integration release, subject to Site qualification and branch protection.
Integration releases can occur without Site releases; Site-only runtime fixes must be able
to retain the same adopted Integration input.

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

The current output contract is Bundle v3 for the committed Composition + Policy tuple and
Bundle v4 for the explicit Modeling + Composition + Policy tuple. Structurally valid stale
reader derivatives remain available with exact provider-owned reviewed/current canonical
evidence, while provider repository source/tree payloads are no longer transported for
Site browsing. The P5/P7 releases used v1 current-only publication and P8 used v2. These
versioned changes do not update Site, provider translation prose, or synchronization
hashes by implication. Site adoption and warning presentation remain a separate gate;
after activation the controller may perform only the pre-authorized mechanical lock
mutation, never a semantic approval.
