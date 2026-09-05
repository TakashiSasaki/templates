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


## Validation status

The final candidate records the exact GitHub Actions run IDs and measured before/after samples in the pull request description after CI completion.
