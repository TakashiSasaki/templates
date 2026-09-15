# Site CI performance boundaries

This document records the performance contracts used by Site CI.

## Generated repository browser

The repository-browser generator owns the deterministic source-viewer contract:

- every viewable source line has one contiguous `id="L<n>"`;
- its line-number link is `href="#L<n>"`;
- line numbers start at 1 and have no gaps;
- the viewer remains bounded, escaped UTF-8 HTML.

The generic generated-site link validator therefore does not resolve those generator-owned `/files/**#L<n>` references again. It continues to validate ordinary reader links, navigation links, cross-page links, assets, origins, and fragments. A malformed source viewer fails during generation.

## Freshness and provenance

Freshness annotation and its per-page structural check share one generated-HTML traversal. The operation remains fail-closed:

- malformed `<head>` structure fails;
- conflicting or missing Site revision metadata fails;
- `repository-trees/previews/**` remains excluded from mutation;
- the canonical `site-version.json` payload is still written and checked.

The public full verifier remains available for callers that need an independent post-write verification pass.

## Browser runtime

Ordinary browser acceptance uses Playwright's official `channel="chrome"` mode on Ubuntu 24.04. Each browser workflow verifies `google-chrome --version` and records the selected runtime. The acceptance scripts and scope are unchanged. The PWA worker-lifecycle fixture remains on Playwright-managed Chromium because runner Chrome 152 did not reliably activate the fixture update; that fallback is limited to PWA-sensitive jobs.

Performance comparisons must distinguish:

- unprofiled production-like wall-time baselines;
- cProfile diagnostic elapsed time, which includes instrumentation overhead;
- browser setup time;
- actual browser test time.

A single hosted-runner sample is not sufficient to claim an improvement; use repeated samples and report median and P90 where available. The final browser acceptance records the installed system Chrome version and the managed-Chromium exception for PWA worker lifecycle.


## Provider publication materialization lifecycle

Provider publications pass through an explicit, authority-preserving lifecycle in Pages CI:

1. **Source state**: the provider checkout owns its catalog, inputs, and optional `scripts/materialize_publication.py`; Site does not implement provider generator semantics.
2. **Explicit phase**: `.github/workflows/site-producer.yml` materializes providers before integration tests, assembly, and translation publication. The provider entrypoint runs in isolated Python mode with bytecode writes disabled.
3. **Stable state**: `.publication-materialization-stamp.json` binds the canonical root, exact Git revision when available, Git-visible tracked/untracked source state, catalog/materializer fingerprint, provider-owned semantic revision from `publication-descriptor.json` or `generated/publication-descriptor.json`, and SHA-256 snapshots of materialized products.
4. **Boundary revalidation**: source identity, semantic identity, and outputs are rechecked at stamp acceptance, stamp commit, and success return. Observed changes fail closed.
5. **Process-crossing reuse**: downstream processes validate the persistent stamp; missing, stale, malformed, or corrupted state cannot silently authorize reuse.
6. **Authority boundary**: Composition owns generation, semantic identity, descriptors, and products. Site owns generic orchestration, contract validation, and reuse verification and does not parse Composition-specific generated manifests.


## Validation status

The final candidate records the exact GitHub Actions run IDs and measured before/after samples in the pull request description after CI completion.

## Qualification-ready local precheck

Before pushing a repaired invariant, run `scripts/run_site_preflight.py fast
--base <exact-base-sha>` with the Site Python environment. Capability selection uses
`classify_site_ci.py`; missing, ambiguous, unknown, and CI-authority changes select
the complete core suite. Focused checks are local diagnostic evidence only.

For a built artifact, `scripts/run_site_preflight.py ready --base <exact-base-sha>
--site-root <artifact> --composition-root <locked-checkout> --policy-root
<locked-checkout>` runs the focused integration spine and audience static contract
before browser qualification. `scripts/check_audience_artifact.py` also exposes the
static checker directly. The real audience browser checker still validates that
contract before running all browser lifecycle assertions.

The small integration fixture traverses canonical manifest/catalog loaders,
assembly and translation publication, then the actual static consumer setup. It
covers required and generated document omission, optional source present/absent,
unexpected documents/routes and actual translation aliases. HTML rendering is a
fixture boundary; full exact-head browser acceptance remains required by CI.

### Disposable local capsule

Pass `--capsule-root /tmp/site-qualification` with both locked provider roots to
`run_site_preflight.py ready --base <SHA>`. `cross-assembly` retains its local
assembled output; `audience-static` and `audience-browser` consume that exact tree.
Use `--check audience-browser --channel chromium` to retry browser acceptance
without rebuilding; browser evidence is always fresh and is never cached as CI
acceptance. Named stage results include attempts and elapsed seconds.

Identity includes all three revisions, tracked/dirty/untracked source bytes,
materialized generated provider inputs, script identities, dependency lock bytes,
installed build dependency versions, Python/platform, and an artifact content and
mode digest. Results are atomically written under an exclusive local lock outside
all source checkouts. Modified artifacts and mismatched metadata are errors;
changed inputs select a new entry. Failed/interrupted stages cannot become cache
hits. Local capsules are disposable and do not authorize remote CI/review skips.

The local assembly scope supports audience/static and lifecycle diagnosis; full
remote production assembly additionally generates repository and guided viewers
and retains all its existing URL/link checks. Local success never replaces it.

## Scheduled producer and consumers

The ordinary PR dispatcher is `build-pages.yml`. Its build calls the single
`site-producer.yml`; core tests run independently of that producer. Browser,
reference and cross-authority consumers depend on the producer and receive its
artifact ID, immutable archive digest and complete build input identity. Each
consumer verifies API run/head binding, locked provider revisions, archive digest,
input manifest and publication provenance before extraction. No consumer searches
or polls for producer completion. Producer reuse probes only already-completed
eligible builds; it never occupies a runner waiting for another workflow.

Publication freshness still builds a genuinely different current Composition
candidate when required. Its artifact is separately named `freshness-pages` to
avoid collision with the locked canonical artifact in the same run. Reusable
workers have no concurrency group; the PR dispatcher owns cancellation. Scheduled
and manual freshness diagnostics remain available. Fork handling preserves the
conservative source build and read-only permissions of the existing boundary.

`Site Construction CI / validate` and `Site Full Qualification / validate` remain
the aggregate check names. Full qualification checks the complete `needs` result
set and rejects failed, cancelled, missing and skipped required jobs. Nested job
names are mapped explicitly in `verify_site_full_qualification.py`. The standalone
full-qualification workflow is a one-shot manual exact-head API audit. Its job
queries bind `run_attempt`; successful inherited producer jobs remain evidence of
the attempt that actually ran them. The provider-managed Website workflow remains
unchanged; the DAG invokes its canonical validator directly for its own gate.

Wall time is the critical path; runner occupancy is the sum of job execution
intervals. Waiting for dependency scheduling consumes no runner time. Reports must
separate setup, test body, polling and inherited retry evidence, using each step's
actual status/conclusion rather than inferring success from a later running step.

### Browser priority and failure evidence

Classification exposes `browser_priority` as a scheduling hint for audience,
search, PWA or layout changes. It does not alter required capabilities. A changed
feature executes after artifact validation and setup, before generic checks. Its
normal slot is suppressed only by that early step's actual `success` outcome.
Unknown/control changes still require full qualification; absent priority from an
older classifier preserves the normal checks. Generic slow PWA convergence runs
last. There are no additional browser shards or repeated setup jobs.

`check_pwa_freshness.py --output <json>` records bounded registration/worker state,
updatefound/statechange/controllerchange timestamps, observed fixture versions,
request/response failures, page errors, warning/error console messages, fixture hit
counts and browser/Python versions. Lifecycle events survive page reloads in the
controller's evidence buffer; failure snapshots run before context teardown. The
original convergence bounds and lifecycle assertions are unchanged.

Local same-artifact Chromium samples (three before/after, 2026-09-15) measured
3.60s median before and 3.61s after, ranges 3.58–3.68s and 3.59–3.62s. An injected
failure after an actual worker update also produced diagnostic JSON. These samples
show no material local observation overhead, not a hosted-runner speed claim.
Time-to-first-relevant-failure must be measured separately from total success time;
priority removes preceding unrelated checker bodies, not the required checks.
