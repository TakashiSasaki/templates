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
2. **Explicit phase**: `.github/workflows/build-pages.yml` materializes providers before integration tests, assembly, and translation publication. The provider entrypoint runs in isolated Python mode with bytecode writes disabled.
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
