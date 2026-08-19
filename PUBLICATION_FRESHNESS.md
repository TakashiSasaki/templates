# Publication source freshness

This contract applies to the `site` integration authority and defines how Site checks whether the current canonical Composition source remains compatible with the reviewed publication snapshot.

It is separate from [`FRESHNESS.md`](FRESHNESS.md), which governs deployed-document identity, cache behavior, and PWA/runtime freshness. Publication source freshness is a build-time provider-integration concern.

## Reviewed release input

`publication-sources.json` remains the reviewed immutable release input for Site builds and deployments. A provider branch moving after review does not invalidate the deployed Site, and this diagnostic does not update the lock automatically.

Advancing a provider lock remains an explicit Site review decision followed by the normal full Site build and review process.

## Composition candidate diagnostic

`.github/workflows/check-publication-freshness.yml` evaluates one specific question:

> Does the current exact Composition HEAD snapshot still pass the normal complete Site publication build when combined with the reviewed Site integration and reviewed Policy input?

The workflow:

1. checks out the exact Site revision being diagnosed;
2. resolves the reviewed Composition lock from `publication-sources.json`;
3. resolves the live `composition` branch through the GitHub API to one immutable full commit SHA;
4. classifies the reviewed lock as `current` or `different` from that snapshot;
5. invokes `.github/workflows/build-pages.yml` with that exact SHA as `composition_ref`;
6. leaves `policy_ref` unset, so Policy remains at the reviewed Site lock;
7. reports the lock, candidate snapshot, relation, and complete candidate-build result.

This is deliberately a Composition-only candidate check. It closes the Composition publication integration gap without converting the Site release model into an implicit "latest providers" build.

## Result semantics

The lock/head relation is informational; the full candidate build is the compatibility signal.

| Reviewed Composition lock | Current Composition snapshot | Candidate build | Meaning |
| --- | --- | --- | --- |
| same | same | success | Site is current for Composition and the snapshot is compatible. |
| different | newer/different | success | The reviewed Site remains valid; emit a warning that a newer compatible Composition snapshot is available for explicit review. |
| any | exact current snapshot | failure | Current Composition does not pass the normal Site publication pipeline; integration triage is required. |
| any | unavailable or build skipped | not executed | No compatibility conclusion is valid; the diagnostic itself must not report this as a tested incompatibility. |

A `different` relation is therefore not a failure condition. It must not cause an automatic lock update.

## Validation boundary

The candidate uses the normal reusable `build-pages.yml`, not a reduced diagnostics graph. Consequently compatibility covers the same Site-owned integration boundary as an ordinary publication build, including catalog/manifest assembly, link rebasing, strict static generation, glossary and guided navigation, repository views, public URL checks, provenance, final generated-site link/fragment validation, and Pages artifact construction.

The artifact is validation output only. The freshness workflow has `contents: read` permission and no Pages or OIDC write authority. `.github/workflows/deploy-pages.yml` remains the only deployment route.

## Triggers

The diagnostic runs:

- for pull requests targeting `site` when publication-integration inputs or the diagnostic itself change;
- once daily at `17:23 UTC` (`02:23 JST`);
- on explicit `workflow_dispatch`.

The scheduled run is intended to detect Composition movement after the last reviewed Site pin even when Site itself has not changed.

## Triage responsibility

A red scheduled or manual freshness run is owned initially by the Site maintainer because the failed boundary is the integrated Site publication projection. Triage should identify the authority of the underlying cause before changing content:

- missing/incorrect Composition publication authority or catalog declaration -> `composition` change;
- Site destination mapping, assembly, navigation, or final URL graph issue -> `site` change;
- coordinated semantic/publication change -> separate authority-specific PRs with explicit merge order.

A compatible but different Composition snapshot is review input, not an incident. The Site maintainer may open a normal pin-forward PR when the newer Composition revision should become the reviewed publication source.
