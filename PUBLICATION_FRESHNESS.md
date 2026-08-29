# Publication source freshness

This contract applies to the `site` integration authority and defines how Site checks whether the current canonical Composition source remains compatible with the reviewed publication snapshot.

It is separate from [`FRESHNESS.md`](FRESHNESS.md), which governs deployed-document identity, cache behavior, and PWA/runtime freshness. Publication source freshness is a build-time provider-integration concern.

## Reviewed release input

`publication-sources.json` remains the reviewed immutable release input for Site builds and deployments. A provider branch moving after review does not invalidate the deployed Site, and this diagnostic does not update the lock automatically.

Advancing a provider lock remains an explicit Site review decision followed by the normal full Site build and review process.

## Composition candidate diagnostic

`.github/workflows/check-publication-freshness.yml` evaluates one specific question when a candidate compatibility build is applicable:

> Does the current exact Composition HEAD snapshot still pass the normal complete Site publication build when combined with the reviewed Site integration and reviewed Policy input?

The workflow:

1. checks out the exact Site revision being diagnosed;
2. for pull requests, classifies the exact base/head changed paths and treats only the repository's explicit CI-observability-only path set as outside the publication-integration boundary;
3. for scheduled and manual runs, always requires a candidate compatibility build;
4. resolves the reviewed Composition lock from `publication-sources.json`;
5. resolves the live `composition` branch through the GitHub API to one immutable full commit SHA;
6. classifies the reviewed lock as `current` or `different` from that snapshot;
7. when the candidate build is required, invokes `.github/workflows/build-pages.yml` with that exact SHA as `composition_ref`;
8. leaves `policy_ref` unset, so Policy remains at the reviewed Site lock;
9. reports the Site revision, lock, candidate snapshot, relation, candidate-selection decision, and candidate-build result.

This is deliberately a Composition-only candidate check. It closes the Composition publication integration gap without converting the Site release model into an implicit "latest providers" build.

## Pull-request applicability

For a pull request on which the freshness workflow is already triggered, the second full candidate build may be skipped only when every changed path is classified by the same conservative Site CI-observability predicate used by the browser-acceptance selector. At the current contract that predicate recognizes only:

- `.github/workflows/ci-performance-report.yml`;
- `.github/workflows/composition-unittest-timing-report.yml`;
- `scripts/report_composition_unittest_timing.py`;
- `tests/test_composition_unittest_timing_*`.

These files can change CI measurement or reporting behavior but do not change the Site publication integration graph, the reviewed provider inputs, generated reader/runtime assets, or provider compatibility semantics. The freshness workflow's existing broad `scripts/**` and `tests/**` trigger patterns can therefore admit timing-report implementation/tests even though a second provider-compatibility build is non-applicable. The selector keeps the workflow/check result visible for those triggered cases while avoiding duplicate runner compute.

The two observability workflow files listed by the shared predicate do not independently trigger publication freshness under the current path filter. They remain part of the predicate so a freshness-triggering pull request that also changes those files is not forced into a candidate build merely because of an otherwise safe observability change.

The selection boundary is fail-closed. An empty or malformed changed-path set, an unknown path, a mixed change set containing any path outside the explicit predicate, a classifier failure, or any other qualifying freshness change requires the normal current-Composition candidate build. Changes to the freshness workflow, this contract, publication locks, Site assembly/build inputs, or the classifier itself therefore continue to execute the full candidate build.

Scheduled and `workflow_dispatch` diagnostics never use pull-request scope skipping. They always execute the full candidate build because their purpose is to detect Composition movement independently of Site pull-request changes.

## Result semantics

The lock/head relation is informational. When the candidate build is applicable, the full candidate build is the compatibility signal.

| Context | Lock/head relation | Candidate build | Meaning |
| --- | --- | --- | --- |
| candidate required | `current` | success | Site is current for Composition and the snapshot is compatible. |
| candidate required | `different` | success | The reviewed Site remains valid; emit a warning that a different compatible Composition snapshot is available for explicit review. |
| candidate required | `current` or `different` | failure | Current Composition does not pass the normal Site publication pipeline; integration triage is required. |
| candidate required | any | skipped / unavailable | No compatibility conclusion is valid; the diagnostic is incomplete and must fail. |
| CI-observability-only triggered PR | `current` or `different` | skipped | The second compatibility build is non-applicable to this PR scope; the workflow records that no new compatibility conclusion was produced. |

A `different` relation is therefore not a failure condition. It must not cause an automatic lock update. On an observability-only pull request, a `different` relation also must not be described as compatible because no candidate build was run; the scheduled diagnostic remains responsible for independent Composition-head compatibility coverage. An unexpected relation value is itself a diagnostic error rather than an implicit freshness conclusion.

## Validation boundary

When applicable, the candidate uses the normal reusable `build-pages.yml`, not a reduced diagnostics graph. Consequently compatibility covers the same Site-owned integration boundary as an ordinary publication build, including catalog/manifest assembly, link rebasing, strict static generation, glossary and guided navigation, repository views, public URL checks, provenance, final generated-site link/fragment validation, and Pages artifact construction.

The artifact is validation output only. The freshness workflow has `contents: read` permission and no Pages or OIDC write authority. `.github/workflows/deploy-pages.yml` remains the only deployment route.

Skipping a candidate build for an explicitly CI-observability-only pull request does not weaken the reviewed release graph: the ordinary PR build still validates the exact Site head against the reviewed provider locks, and the pull request cannot advance those locks through the allowed skip surface.

## Triggers

The diagnostic runs:

- for pull requests targeting `site` when the path filter identifies publication-integration inputs, tests, the diagnostic itself, or broad `scripts/**` / `tests/**` changes;
- once daily at `17:23 UTC` (`02:23 JST`);
- on explicit `workflow_dispatch`.

The scheduled run is intended to detect Composition movement after the last reviewed Site pin even when Site itself has not changed. Scheduled and manual diagnostics are not cancelled merely because another diagnostic starts; superseded pull-request diagnostics may be cancelled and replaced by the newer PR revision.

A qualifying Site pull request whose scope can affect publication integration normally causes two full publication builds: the ordinary locked-input PR build and this diagnostic's current-Composition candidate build. That duplication is intentional so integration changes validate both the reviewed release graph and the prospective Composition graph. Presentation-only changes remain excluded by the workflow path filter. Triggered pull requests proved to contain only the explicit CI-observability predicate retain the freshness workflow result but make the second full build non-applicable.

## Triage responsibility

A red scheduled or manual freshness run is owned initially by the Site maintainer because the failed boundary is the integrated Site publication projection. Triage should identify the authority of the underlying cause before changing content:

- missing/incorrect Composition publication authority or catalog declaration -> `composition` change;
- Site destination mapping, assembly, navigation, or final URL graph issue -> `site` change;
- coordinated semantic/publication change -> separate authority-specific PRs with explicit merge order.

A compatible but different Composition snapshot is review input, not an incident. The Site maintainer may open a normal pin-forward PR when the newer Composition revision should become the reviewed publication source.
