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

## Maintainer routing and operational handoff

Start from [README.md](README.md), [AUTHORITY.md](AUTHORITY.md), and the
[Integration publication maintenance skill](.agents/skills/integration-publication-maintenance/SKILL.md).
The connected Site-side event/PR/deployment sequence is documented in the
[publication automation handoff](https://github.com/TakashiSasaki/templates/blob/site/docs/publication-automation.md);
that document is a projection of these contracts and the current workflow code,
not a second Integration authority.

The current capability is Bundle v4 with a historical v3 reader/fixture contract.
The selected provider tuple is the committed `publication-sources.json`; a
deployed Site input is a separate Site `integration-source.json` lock and Pages
artifact. Never infer either selected or deployed state from this branch's
capability or from a `publication.integration-promoted` notification. A mode
change is not a replay of a previous candidate: re-check the latest base, exact
candidate, existing automation PR, run attempt, receipt/artifact expiry, and
external authorization before any future authorized operation.
A new Integration release alone is not Site-adoption authorization; the guarded
Site controller path is separately activated and still requires its own receipt,
qualification, protected review/merge, and deployment boundary.

## Local qualification

Install the locked minimal dependency closure in an isolated environment and run pip
check. Materialize provider-owned declared outputs with
`scripts/materialize_publication_assets.py --publication modeling=ROOT --publication composition=ROOT --publication policy=ROOT`.
Then run:

```
python -m unittest discover -s tests -v
python scripts/qualify_integration.py \
  --integration-root ROOT --producer-revision FULL_SHA \
  --composition-root COMPOSITION_ROOT --composition-revision FULL_SHA \
  --policy-root POLICY_ROOT --policy-revision FULL_SHA \
  --modeling-root MODELING_ROOT --modeling-revision FULL_SHA \
  --output OUTPUT_OUTSIDE_SOURCE_CHECKOUTS
```

Historical P5 bootstrap equivalence remains documented in the archived bootstrap
evidence, but it is not part of the current Bundle-v4 qualification workflow. The
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

## Trusted reconciliation receipt

The report produced by the candidate qualification checkout is untrusted input;
its `passed` strings and `AUTO_PROCESSABLE` claim are never an adoption gate.
The reconciliation workflow first consumes the exact Bundle artifact through the
run/head/attempt/artifact binding above. Its read-only controller checkout then
validates the Bundle, reads provider capability declarations as data, and checks
that a trusted-controller regeneration is byte-equivalent to the candidate
generation. The producer identity may differ from the controller code revision:
the latter is an independently pinned execution root, while the former remains
the exact Integration revision represented by the Bundle. Only the resulting
verified receipt can reach the authorization classifier. The privileged lock-PR
job executes only the trusted deterministic lock updater and never checks out or
runs provider/Integration candidate code.

Activation must pin both `PUBLICATION_CONTROLLER_REVISION` and
`PUBLICATION_POLICY_REVISION` to reviewed exact commits. An empty pin is
report-only, even when the artifact and all qualification checks are valid.
Changing a provider revision does not change the execution Policy pin, and
publishing Policy documentation does not update that pin.

The committed production lock is schema 2 and names the exact Modeling, Composition and
Policy revisions that carry the declaration contract. It produces Bundle v4, including
Integration's normalized requirement closure. Bundle v3 remains available only for
historical Site compatibility and explicit regression fixtures; new production
publication does not silently fall back to the old two-provider lock. Structurally valid
stale reader derivatives remain available with exact provider-owned reviewed/current
canonical evidence, while provider repository source/tree payloads are no longer
transported for Site browsing. The P5/P7 releases used v1 current-only publication and
P8 used v2. These versioned changes do not update Site, provider translation prose, or
synchronization hashes by implication. Site adoption and warning presentation remain a
separate gate; after activation the controller may perform only the pre-authorized
mechanical lock mutation, never a semantic approval.

When a fully qualified candidate already matches the current `publication-sources.json`,
there is no lock diff to review. The trusted controller records the exact base, selected
lock digest, provider tuple, Bundle identity, run/artifact identities, and active pins in
the deterministic `publication-promotion-intent.json` included in the
`automation/publication-*` PR. That intent is a reviewable handoff record, not a promoted
receipt. After merge, the notification workflow verifies the intent against the merge's
first parent, selected lock, branch idempotency key, and active pins, then performs a new
trusted qualification for the exact merged Integration revision in the `promoted`
artifact namespace. It does not reuse the pre-merge candidate Bundle as promoted evidence.
