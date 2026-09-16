# Audience architecture implementation roadmap

> **Historical design record:** This pre-cutover design records the audience migration.
> The current public destination/semantic navigation authority is Integration's selected
> Publication Bundle. Site owns its audience UI and rendering. References below to
> a Site manifest or Site-owned integration describe the historical implementation.


This roadmap defines authority responsibilities, dependencies, and acceptance
criteria. It is not an execution ledger or a provider semantic specification.
Current heads, CI/review status, findings and next actions belong in GitHub.

## Establish the immutable architecture input

Call the reviewed Site commit containing this complete architecture **S**. The
stack-tip PR's canonical Work ledger records the exact full SHA selected at
handoff, the ordered PR bases/heads, and whether review is pending or complete.
A subsequent session MUST resolve that recorded commit, read this entire area at
S, and state its binding in its own PR. Do not substitute the current `site` tip,
the older audited Site revision, an A1-only commit missing this roadmap/validator,
or a remembered chat description. A proposed handoff SHA is not reviewed merely
because it is recorded; establish its review state before normative adoption.

Both provider sessions MUST use the same accepted S. If review changes the
architecture, select and record a new reviewed S and assess both providers'
affected decisions; do not silently let them use different models. This avoids
requiring a commit to contain its own SHA. The architecture is reconstructable
from these files and their immutable GitHub PR binding alone.

At S, the [model](audience-model.md), [target IA](target-information-architecture.md),
[matrix](migration-matrix.json), and [schema](migration-matrix.schema.json) are
normative design inputs. The [index](README.md) defines the evidence boundary.
The [independent future candidate scope](future-candidates.json) is also normative:
all declared candidates must retain a matrix decision. Use the validated count
summary in the index; do not infer future scope from whichever rows remain.
This roadmap defines dependencies, not provider behavior. The validator proves
the frozen design inventory against its audited sources; it is never the future
production manifest implementation.

## Dependency map

```text
Reviewed architecture S
├── Composition semantic/publication audit ── reviewed, qualified C
└── Policy semantic/publication audit ─────── reviewed, qualified P
          │
          └── if catalog additions require compatibility:
              Site staging at exact T → provider compatibility at T → provider landing

S + qualified C + qualified P
  → Site audience foundation
  → Site audience UX
  → final cross-authority qualification and exact-head acceptance
```

Dependencies across authorities are exact revision bindings, never Git ancestry.
Stacks may exist within each authority. Composition and Policy can audit their
own material independently after S; neither owns Site navigation.

The [existing staging contract](../../../PUBLICATION_STAGING.md) takes precedence
over a simplistic provider-first catalog addition. If adding a catalog document
would break current exact catalog/manifest coverage, a later **Site-owned staging
prerequisite** must land first with active publication unchanged. Validate the
provider candidate against that exact reviewed staging Site revision and staging
ID, then land the provider. Only the later Site cutover advances active publication
locks/mappings. Never weaken coverage, merge an invalid active state, or make
provider catalogs depend on Site portal labels to avoid this dependency.

## Composition session

Inputs: all normative design artifacts at S; exact current Composition code,
catalog, indexes, docs, release descriptors, tests, and provider procedures.
Reconstruct live state; compare it with the matrix's audited Composition revision.
The matrix classifies reader discovery, not a mandate to rewrite every page.

- Preserve the explicit distinction between consumer-product maintenance and
  Composition-authority maintenance. Product releases remain Use.
- Audit mixed technical references (`composer-mvp`, `composition-model`,
  `catalog-architecture`, `generated-contract-manifest`, `catalog-guide`,
  `schema-guide`, `composer-reference`) for clear semantic roles. Their existing
  content is sufficient for the proposed shared projection; splitting or rewriting
  them is not required simply because they serve both audiences.
- Resolve `provider-maintenance`: author a canonical human provider-maintainer
  overview linking component/catalog/Composer development, evaluation, validation,
  publication and release procedures. Choose its final source path and stable ID
  within Composition; record correspondence to the candidate matrix key.
- Resolve `installer-release`: assess `release/README.md` for publication and
  clarify provider release identities versus consumer installation. Preserve
  descriptor authority and the canonical consumer bootstrap path.
- Keep `evaluation-guide`, `publication-boundary`, and historical authority
  migration material discoverable as maintenance; keep consumer guides and
  product contracts independently usable.
- Where publication is justified, update provider-local catalog/index/links and
  translations through Composition's normal process, with Site staging when
  needed. Do not add Use/Maintain labels to the provider catalog protocol.
- Validate provider-local publication, source/catalog/translation coverage and
  applicable provider checks at the exact final candidate. Establish reviewed,
  qualified revision C and actual landing SHA separately when they differ.

Output: canonical Composition changes or evidence-backed no-change dispositions
for every declared Composition candidate, semantic-role clarifications where justified, stable
document IDs/paths and publication evidence. Record operational state in its PR;
Site later updates the projection for the accepted provider revision.

## Policy session

Inputs: the same S artifacts; exact current Policy catalog, docs, indexes,
toolchain/repository-policy sources, procedures and validation definitions.
Compare live state with the matrix's audited Policy revision before applying it.

- Preserve consumer application/adoption/configuration/CLI versus provider
  toolchain/release/maintenance responsibilities. Applying review or repository
  operating policy in another repository remains Use.
- Resolve `policy-authoring` clarification: make shared-corpus authorship and
  repository-local extension/override roles clear without duplicating rules.
- Resolve `pwa` clarification: establish what product its reader installation
  help describes and how it relates to the integrated Site PWA contract. Policy
  owns corrections to its prose; Site owns integrated reader-help projection.
- Resolve publication candidates `contributing`, `maintainer-workflow`,
  `adr-review-authority-and-github-runtime-boundary`, and
  `adr-review-result-representation-boundary`. Reconcile ADR-0008 partial
  supersession with ADR-0009 and index visibility under Policy's authority;
  this roadmap does not decide their review semantics.
- Keep source rules, generated maintainer instructions and explanatory guides
  distinct. Do not publish every runtime skill or repository-policy source merely
  because Maintain links to it through Source.
- Validate provider-local publication, indexes, translations and applicable
  toolchain/documentation checks at exact final candidate P. Observe the staging
  prerequisite when extending its catalog.

Output: provider-owned content/publication decisions, stable identities and exact
qualification evidence. Policy does not select Site navigation, audience themes,
or canonical integrated destinations.

## Site audience-foundation session

Inputs: S model/IA/matrix/schema/index, this dependency map, reviewed and qualified
C and P, their document-set changes and any reviewed staging revision T.

Implement the production audience model and separate Use/Maintain projections.
Migrate `site-manifest.json` and its schema deliberately: separate canonical
document/destination definitions from navigation memberships, retain exact
catalog coverage, and validate all membership/audience relationships. Choose and
document the concrete semantic-context representation, history restoration,
deep-link fallback, switch behavior and canonical URL normalization required by
the model. Do not use this design inventory as runtime configuration.

Publish the existing Site maintainer candidates declared in the independent scope
and described in the matrix,
following Site source-link, translation, and publication conventions. Audit any
newly authored architecture area for future canonical publication separately;
do not add uncataloged local copies of Composition material. Generate sparse
section overviews from memberships rather than inventing provider semantics.

Refresh the migration decisions against C/P and the final Site catalog/manifest;
preserve the original audited evidence or explicitly version/rebind the inventory
when its historical baseline is replaced. Reconcile candidate IDs with final
provider IDs. Close every candidate/action with published canonical content or
an owning-authority rationale before claiming the Maintain portal complete.

Acceptance: one canonical route per document, multiple valid memberships, exact
catalog/manifest coverage, no unknown audiences or duplicated canonical content,
direct/shared/single-audience context tests, canonical links, locale/guided
projection parity, and unchanged ownership of provider semantics. Update reader
navigation/localization and machine projections only at their actual integration
boundary; publication pins stay distinct from Site's self-host consumer pins.

## Site UX session

Inputs: S model and target IA, reconciled matrix decisions, foundation production
contracts and their exact Site/provider revisions.

Implement the neutral landing, explicit global audience switcher, blue/cyan Use
and amber/orange Maintain themes, audience navigation and breadcrumbs. Integrate
search badges and visible audience filtering, context-preserving Glossary/Source/
provenance utilities, and shared canonical technical references. Theme derives
from semantic context rather than scattered path tests.

Acceptance: responsive keyboard and assistive-technology operation, visible focus
and readable contrast, audience identity without color, canonical-document
preservation when switching, locale independence, reload/back/forward behavior,
direct links with no context, and unsupported-context fallback. Cover both
single-audience transitions and each shared-document primary in real browsers.

## Final qualification session

Inputs: S acceptance criteria, final foundation/UX Site head, final qualified
provider landing SHAs and reconciled document inventory. Bind all evidence to
the exact Site/provider combination actually built; do not claim exact-head
qualification using construction-head tests or an older Pages artifact.

Validate publication assembly and catalog coverage; navigation and breadcrumbs;
canonical URLs, deep links and fragments; search deduplication/classification;
Glossary semantics/locale/provenance; Source and tree identity; PWA offline,
freshness and update behavior; browser accessibility/responsiveness; independent
self-host consumer state; and cross-authority integration. Use the current Site
acceptance workflows and exact-head merge policy rather than freezing today's
check names in this roadmap.

Publication staging is build-only. Deployment remains the sole Site workflow.
Record review completion, merge authorization and actual deployment separately;
a whole-stack diagnostic review request is not merge acceptance. Final execution
heads, review findings, CI waits and blockers stay on GitHub workflow surfaces.

## Reproducing inventory validation

From a checkout containing these artifacts, install the declared Site requirements
and run:

```sh
python3 scripts/validate_audience_inventory.py --fetch-audit
python3 -m unittest tests.test_audience_inventory --verbose
python3 scripts/run_core_tests.py --verbose
```

`--fetch-audit` fetches only the recorded exact commit objects from the named
repository without updating any authority branch or checking it out. Omit it
when the clone already contains all audit objects. The validator reads committed
blobs with Git replacements disabled, uses the existing publication protocol
parser, and extracts literal generated-tree declarations without executing the
historical script. It fails on missing evidence; mutable heads are not fallback
inputs. The existing publication-contract CI runs this exact inventory check;
the normal core runner discovers the focused regression tests.

Schema validation includes date-time format checking and requires duplicate-key
rejection before parsing. Additional executable checks cover source uniqueness,
independent candidate identity coverage and documented counts, action ownership,
candidate source existence, source/destination/navigation equality, provider-lock
binding, audience/membership consistency, and full catalog/generated coverage.
The check proves inventory completeness and structural decisions, not editorial
correctness or the future browser implementation. Semantic review remains required.
