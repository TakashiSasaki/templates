# Asynchronous publication

The repository has five independent Git histories. This is the only repository-wide
structural invariant. Source meaning belongs to its author; publication and display
are downstream transformations, with no upstream approval or release dependency.

```text
Modeling / Composition / Policy / additional providers
              | branch discovery; snapshot once per build
              v
Integration: catalog -> semantic models -> complete Bundle 5
              | immutable successful Actions artifact
              v
Site: successful artifact + local presentation -> Pages artifact
              | successful build, Pages environment
              v
GitHub Pages
```

## Decisions

- `publication-sources.json` names provider branches. Resolve every branch once at
  build start. Clone those commits into disposable directories. Record the exact
  revisions in the Bundle; never write resolved SHAs back into source configuration.
- Integration checks catalog inputs, cross-document links, translation metadata,
  glossary and generated models. Provider PRs run provider checks only. A failed
  Integration build publishes nothing; it does not make a provider PR incomplete.
- Integration includes every catalog document under its provider namespace using stable
  IDs. Site alone assigns public routes and creates the two audience navigations.
  Provider names are data, not an enum shared with Site. Index navigation, glossary
  and translations are optional enhancements; a catalog can publish plain documents.
- Cross-provider links use `template:<provider>/<document-id>#fragment`. Site resolves
  them after route assignment. Links to unpublished source documents use immutable
  GitHub URLs. An unparseable optional source index emits a warning and omits that
  provider's index graph; it does not block ordinary catalog documents.
- Site accepts complete successful artifacts from the canonical publishing workflows.
  It verifies the GitHub origin, archive digest, paths, inventory, Bundle identity and
  renderable structure. It never checks out providers or regenerates Integration.
- The newest available successful publication is the default. A failed/in-progress
  newer build leaves the preceding success available. Selection happens once per Site
  build; source branch movement does not invalidate the selected bytes.
- A Site change builds against an existing publication. Integration refreshes do not
  commit to Site, request an adoption PR, or require a change to any executable pin.
- Deployment receives exactly the checked Pages artifact. No provider, Integration or
  rendering code runs in the Pages-write job. Failed acquisition/build/deployment leaves
  the currently served site in place. Use an explicit successful run ID to rebuild an
  older available publication; changing source branches is unnecessary.
- Publication artifacts expire after 90 days. Scheduled refresh creates another
  complete artifact; do not rely on permanent retention. If no artifact is available,
  refresh Integration. Site fails clearly and never starts a hidden upstream build.

## Removed coupling

| Former mechanism | Replacement |
| --- | --- |
| Provider CI executes a pinned Integration workflow/parser | Local provider export checks; Integration checks its own input |
| Committed exact provider tuple and explicit adoption | Branch configuration plus build-local snapshot provenance |
| Closed hand-maintained publication page list | Automatic semantic catalog projection; Site-owned navigation |
| Fixed two/three-provider Bundle versions | Generic provider map in Bundle 5 |
| Site `integration-source.json` and adoption PR | Successful-artifact channel, optionally selected by run ID |
| Shadow/controller/policy pins, promotion receipts and intent PRs | Read-only assembly and immutable artifact transport |
| Imported pinned maintenance Skill/closure and full review planner | Short local AGENTS and task-scoped local validation |
| Full upstream qualification on a Site visual change | Site tests and rendering against a fixed downloaded artifact |

Exact hashes remain useful for integrity and debugging. Published executable products
and third-party dependencies can retain their release pins; they are not publication
coordination state. There is no promise to preserve old internal commands or formats.

## Presentation ownership

Site has a neutral landing page with two clearly named entrances:

- `/use/` is for consumers building projects: Composition, Policy, Modeling,
  examples, capabilities and the playground.
- `/maintain/` is for providers maintaining this repository: authority ownership,
  local development, publication, recovery and source/build provenance.

`surfaces.json` belongs to Site. It assigns routes and selects maintainer documents
by provider and document ID; other provider documents appear in the consumer
reference automatically. Site's own catalog supplies its local guides. Source
semantics never depend on these audience decisions. New providers work with the
same generic section renderer, without new capability flags or a contract release.

Use one downloaded Bundle while changing the Site working tree. The preview command
creates a disposable source snapshot, so a CSS edit needs no commit and no upstream
build. Final deployment records the actual committed Site revision and Bundle identity.

## Operations and rollback

GitHub schedules run only from the default branch (`site`). Its
`refresh-publication.yml` is a timer adapter calling Integration's reusable workflow
at `integration`; it contains no provider selection or Site build. Integration also
publishes on its own branch pushes. The Site deployment workflow reacts to completed
successful publications and Site pushes. The two workflows do not wait on each other.
Manual refresh is available if a scheduled run is delayed or disabled.

Land provider-local maintenance changes independently, then Integration and Site.
Integration produces Bundle 5 before the new Site channel needs it. No migration or
adoption PR is needed. Validate local source, a real provider-backed Bundle, then a
real Site build before rollout. Existing Pages remains available until a successful
new deployment. If a regression is discovered, revert only the owning branch or
select an earlier retained successful publication run. Do not merge authority histories.

Repository rulesets currently name retired checks. Replace their required contexts
with `contracts` for Integration and `validate` for Site when rolling out the new
workflows; preserve branch deletion/non-fast-forward protection. Repository variables
from the previous publication controller are unused and may be removed separately.
No GitHub settings change is implied by a local test result.

## Verification

Exercise document/provider addition, removal, branch movement after snapshot resolution,
failed/expired/untrusted artifacts, corrupt archive/payload, same-artifact Site rebuild,
provider-free Site rendering, and authority-history overlap rejection. Run the real
producer and renderer, in addition to unit tests. Do not substitute workflow text
matching for proof that the publication can be built.

## Source discovery and reference translations

Each authority checks `index.md` locally with `scripts/check_discovery.py`. The
complete material index is generated from existing publication/product catalogs
and Git-tracked top-level entrypoints. There is no discovery-only membership list.
The normal test suite checks exact projection, reachability and broken local links.
After editing catalog membership, regenerate with `--write`; `--json` reports the
route to every required document and material. This never waits for Integration
or Site to accept a provider change.

Japanese is optional reference content. Missing translations use English. Current
and stale valid translations may be published, but stale pages display a prominent
warning and a link to current English. Translation review evidence always names the
English blob actually reviewed; an English edit does not advance that evidence.
If a canonical heading has moved, Site makes the older translation's section link
open the target page instead. This only changes the rendered reference page, never
the translation source or its review evidence. Canonical links remain strictly checked.

Translations are assembled separately. Invalid or orphaned translation inputs omit
that provider's translation batch with a diagnostic, while canonical content still
publishes. Guided locale overlays are also optional. The owner can fix translations
later without coordinating another authority. Source CI reports the backlog instead
of requiring it to be empty; the default-branch `Review translations` workflow offers
a manual report for Composition, Policy or Site. Translation work remains in its
owning branch and requires no reverse publication/adoption transaction.
