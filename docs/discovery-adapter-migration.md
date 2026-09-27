# Stage A discovery adapter migration design

This accompanies [ADR 0010](adr/0010-discovery-adapter-candidate.md). It proposes
separate Stage B migrations; nothing here adopts a runtime, changes a live adapter,
updates trusted self-host/review authority, promotes a provider or deploys Pages.

## Fixed real inputs and the audit

All five refs were fetched at the start of implementation. The captured revisions
are test inputs, not future migration bases:

| Authority | Source revision |
| --- | --- |
| Policy | `9b4ea04ce3bf9fab5399eb04ec74faeeac82ceda` |
| Composition | `3aa46982f6c5a74a3489476a2d7442c0e467a9e6` |
| Modeling | `4d0da7248e753aeeebd658d1795cecb73b855f8e` |
| Integration | `4e9fc11b42322c4832dc28a5a9a7dda572ae9246` |
| Site | `83a04f4e90425c8da1f11e60b6b7f886012ffb79` |

The actual adopted CLI on each full live checkout reported selected, valid,
`NO_UPDATE_REQUIRED`, with expected counts 139, 40, 41, 12 and 28 respectively.
The fixed corpus captures source bytes, blob identities, original configuration,
lock and runtime. The same parser/validator reruns on the fixture. It is not a
transcribed or reduced implementation. The source code and tests for reproduction
are `tests/test_discovery_consumers.py` and `scripts/qualify_discovery_candidate.py`.

| Prior observation | Reproduction and candidate disposition |
| --- | --- |
| F1 Site owner prose | Reproduced: `agent.json` says Integration; the old filename exclusion says Modeling. Candidate drops filename-specific ownership prose and uses explicit external selectors. |
| F2 same path in two authorities | Reproduced: old expected set contains `contracts/publication-bundle/README.md` from a foreign reference and a same-named Site file exists. Candidate records the foreign reference without local membership; collision regression uses actual data. |
| F3 source-only material | Reproduced: two Composition source-only documents are globally excluded. Candidate keeps them expected and omits them only from `docs/index.md`. Removing the root route fails. |
| F4 IDs are not paths | Reproduced for catalog-only extraction; **qualification**: recipes also appear in the publication assets, so the old manual recipe entries are redundant, not their sole effective source. Candidate executes unchanged Composition resolution; a new valid recipe changes the expected set. |
| F5 missing anchor guarantee | Reproduced: removing each Modeling README/AUTHORITY/AGENTS link leaves old discovery clean. Candidate fails each removal. Existing links were present originally. |
| D1 exclusion vs delegation | Reproduced: old closed inventory suppresses component members and nested indexes together. Candidate suppresses interior index scanning but retains entry and explicit domain members. |
| D2 ancestor shortcut | Reproduced: a useful nested authored index beneath Composition's `docs` shortcut is classified authority-needed. Candidate allows ancestor deep links and nested navigation together. |
| D3 boundary prose | Reproduced by appending an ordinary boundary paragraph to the actual root. Candidate accepts it without reading headings as an authority schema. |

Supplemental regressions cover missing/unknown version, duplicate JSON/YAML keys,
unknown nested fields, missing inventory, stale projection, incompatible member
kinds, global exclusion conflicts, orphan indexes, directory/fragment links,
front matter, code/comment/quote examples and distribution schema loss. Legacy
safety tests continue to exercise the unchanged generated mutation engine.

Run the following from the candidate Policy checkout:

```sh
python -m pytest tests/test_discovery_adapter_schema.py tests/test_discovery_candidate.py tests/test_discovery_consumers.py tests/test_progressive_discovery_skill.py
python scripts/qualify_discovery_candidate.py --output /tmp/discovery-preview.json
python scripts/run_policy_preflight.py --check tests
```

The last command is the existing required Policy CI entrypoint: ordinary pytest
discovery reaches the new consumer tests. The preview requires selected state,
valid validation and a clean semantic result on actual source and distributed
CLI runs. It emits deterministic complete expected-set differences, original and
candidate classifications, initial gaps and proposed index text. Initial gaps are
not rewritten to success: they remain separate from the patched sandbox result.
The package digest binds a sorted map of rendered relative paths to SHA-256 bytes;
it is separate from the adapter schema digest and source commit.

## Changes and domain prerequisites

- **Policy:** explicit profile `policy_files` selectors preserve rule membership.
  Publication glossary membership is selected explicitly. A proposed domain-owned
  `docs/source-discovery.json` carries the existing source-only documentation and
  distributed Skill document inventory currently hand-listed in the adapter.
  That manifest is the canonical replacement after migration, not a second list
  left beside the old adapter. One reader-index omission keeps these documents
  discoverable at root. Source/distributed Skill templates and renderer are the
  implementation sources; installed `.agents/skills` are not edited in Stage A.
- **Composition:** use publication document selectors and a domain-produced typed
  projection for catalog IDs and publication assets (which mix files/directories).
  The test projection producer calls the real Composer; a supported domain CLI and
  freshness gate must be added in Stage B. Bind both catalog and publication inputs,
  and let Composition's source validator qualify descriptor/recipe closure.
  A single proposed generated `components/index.md` presents the component source
  members; internal template `index.md` files remain distributed file members,
  not current navigation. Keep source-only WebMCP/glossary material at root.
- **Modeling:** require README/AUTHORITY/AGENTS and the publication capability and
  collection input. Select local record sources from `catalog.json`; retain the
  domain-owned `tools/catalog.py` freshness qualification (catalog source digests
  are not generic discovery proof). Proposed source-document manifest preserves
  existing source-only guides. Records/schemas/collections retain directory entry
  visibility while their internal scanning remains domain-owned. Existing generated
  resource navigation stays under the same safe generator.
- **Integration:** retain source configuration anchors and two required indexes.
  Site-slot source paths and provider capability paths are explicitly foreign.
  An empty publication document array is valid; a missing array/input is not.
  No compatibility/provider-promotion responsibility changes.
- **Site:** `agent.json` local maintainer/lock references and foreign Integration
  contracts use separate selectors. The only removed old expected member is the
  wrongly inferred foreign contract; Site's same-named consumer guide remains
  linked but is not required by a foreign authority's reference. `agent.json` and
  dotless `progressive-discovery.json` themselves become discoverable inputs.
  Dotless discovery stays under its existing publication schema and renderer.
  Existing assets/schemas entries remain discoverable; absent `build/` is not
  invented as a required local entry.

| Authority | Old expected | Candidate expected | Added | Removed | Index preview files |
| --- | ---: | ---: | ---: | ---: | ---: |
| Policy | 139 | 145 | 6 | 0 | 1 |
| Composition | 40 | 150 | 110 | 0 | 3 |
| Modeling | 41 | 80 | 39 | 0 | 1 |
| Integration | 12 | 15 | 3 | 0 | 0 |
| Site | 28 | 36 | 9 | 1 | 1 |

No previous local expected document disappears except the explained Site foreign
reference. Additional members come from explicit inventory-source discoverability,
bootstrap anchors, previously suppressed domain members and delegated entries.
The machine-readable preview provides each path, rather than duplicating a second
static expected-set list in this design document. Root and child coverage remain
independent; changing child publication scope never removes root obligations.

## Qualification scope and supported transition

Existing formal discovery gates are exercised directly in isolated fixtures:
Composition/Integration `RepositoryDiscoveryTests.require_clean`, Modeling
`tools.qualify.check_progressive_discovery` (including its lock verifier), and
Site's `test_mixed_discovery_contracts_remain_expected_source_documents`.
Tests render an explicitly selected version-2-default package, construct a
prospective isolated pin/lock using Policy's real lock constructor, and invoke the
unchanged canonical functions. No mocked subprocess, skip, weakened assertion or
report rewriting provides the result. Mixed new-runtime/old-config input must
fail through these same gates. Profiles and Skill selections are preserved.

These are discovery-gate integration tests, not full cross-authority CI. They do
not replace Composition publication qualification, Modeling catalog/export checks,
Integration compatibility qualification or Site build/browser qualification.
Source digest checks prove freshness of the declared projection closure only;
actual derivation remains the domain generator's responsibility. The candidate
manifest/projection producers and reviewed package identity must be accepted before
Stage B can establish full migrated-authority qualification.

Stage A keeps current formal root validation on the effective v1 adapter and pin.
Candidate-default rendering is an explicit isolated package construction option;
it cannot be selected by a config URL or guessed from an input version. Source
CLI uses `--candidate-v2`. An old independently distributed runtime without the
version gate is not safe for new input: install the matching package and adapter
as one candidate change before invoking ordinary authority qualification.

## Stage B execution order and stop boundary

1. Independently review the complete Policy stack, including source/template/schema
   identity, real-input differences, candidate-default launch and safe mutation
   reuse. Human acceptance precedes any merge or adoption. Freeze exact accepted
   source and rendered package identities; qualify current Policy CI, documentation
   and runtime distribution for that exact input.
2. In Policy's own migration PR, establish the source-document manifest, decide the
   final candidate version/default launcher transition, and update adapter/runtime/
   schema/lock together. Do not point the current author/reviewer at candidate
   instructions while deciding whether to accept them.
3. Prepare separate Composition and Modeling PRs on their own freshly fetched
   authority bases. Add their owned projection/manifest producers and freshness
   checks first, then minimal navigation and atomic adapter/runtime/pin/lock changes.
   Preserve progressive-discovery-only selections; never add `core` for pin updates.
4. Prepare independent Integration and Site migration PRs using the accepted exact
   Policy artifact. Each runs its full formal qualification plus discovery negatives.
   Dependency is artifact identity, never a Policy branch as a foreign Git base.
   The preview output supplies proposed index edits; review their boundary prose
   under the accepted rule before operational adoption.
5. Remove transitional legacy support after the coordinated migrations. Do not keep
   old aliases or duplicate registries permanently. Wider boundary-directory audits
   and bulk index placement are a later task, after the meaning is stable.

Keep provider publication promotion, `integration-source.json` changes, publication
cutover and Pages deployment out of these migrations unless separately authorized.
The next human action at Stage A handoff is an independent whole-stack design and
implementation review; the author prepares its scope but does not request it.
