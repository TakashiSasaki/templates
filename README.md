# Integration authority

Integration selects exact reviewed Modeling, Composition, and Policy revisions and produces a
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
The committed publication lock is the explicit schema-2 Modeling + Composition + Policy
tuple and produces Bundle v4. Bundle v3 remains a reader contract only for historical
Site releases and compatibility fixtures; new production publication does not fall back
to the former two-provider lock. Both carry exact provenance, and v4 also carries the
Integration-normalized requirement closure, not provider repository source corpora for a
Site-owned browser. Shadow is the initial release mode. After one-time activation,
pre-authorized exact candidates may be mechanically promoted subject to qualification,
freshness, branch protection, and the separate Site gate. Nothing here deploys Pages or
follows mutable provider heads.

`site-manifest.json` is retained as the existing destination/reader-IA contract filename.
`integration/site-slots.json` declares downstream Site content slots, without copying their
presentation bytes. Those names are compatibility vocabulary, not Site implementation
inputs. Provider lock identities are independent of coding-agent/toolchain adoption pins.

## Maintain the Integration authority in `templates`

This is the maintainer route for Integration, not a Site-adoption command. The
repository-wide task map and the connected publication runbook are in Site's
[templates maintainer onboarding guide](https://github.com/TakashiSasaki/templates/blob/site/docs/maintainer-onboarding.md)
and [publication automation handoff](https://github.com/TakashiSasaki/templates/blob/site/docs/publication-automation.md).
Confirm the checked-out branch is `integration`, capture its full `HEAD` and
dirty/untracked state, then read [AUTHORITY.md](AUTHORITY.md), [RELEASE.md](RELEASE.md),
the local [maintenance skill](.agents/skills/integration-publication-maintenance/SKILL.md),
and the active workflow definitions.

The editable publication source is `publication-sources.json`, together with
Integration's contracts and producer implementation. Bundle artifacts, receipts,
reports, and candidate locks are generated or workflow outputs; update their
source and pinned renderer/controller path rather than hand-editing evidence. The
cheap local route is `python3 scripts/run_integration_preflight.py fast --expected-head
"$(git rev-parse HEAD)"`; a committed frontier uses `ready`, and provider-backed
qualification uses `providers` with exact full-SHA checkouts. These checks establish
Integration evidence only. They do not authorize Site adoption, Pages deployment,
or changes to repository variables, credentials, protection rules, or kill switches.

Use branch names to discover a candidate and exact full SHAs for qualification,
review, receipts, and publication. Keep stacked PRs within Integration. A
dependency on Modeling, Composition, Policy, or Site is recorded in the existing
PR/Issue Work ledger and PR body; it is not represented by merging, rebasing, or
cherry-picking another authority's history. On resumption, reconcile the live
candidate, PR, run attempt, artifact/receipt, review, and external authorization
state before taking a next safe action. A notification is a candidate event, not
proof of adoption or deployment.

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
