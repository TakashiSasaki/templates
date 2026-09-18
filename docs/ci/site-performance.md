# Site CI performance and validation scope

Site consumes one exact Integration Bundle. Provider compatibility, materialization,
catalog/translation validation and Bundle production are Integration responsibilities.
The removed local provider capsule and provider profiling workflow are historical;
there is no second active provider build/cache subsystem in Site.

## Construction and qualification

Run `python scripts/run_site_preflight.py fast` for the cheap construction loop:
diff hygiene on committed, staged and unstaged changes, changed-file syntax/tests,
JSON, YAML and TOML parser validation, and classifier validation. `fast` may run on
a dirty tree; untracked non-ignored files are included in its changed-path inventory.

Run `SITE_HEAD=$(git rev-parse HEAD) && python scripts/run_site_preflight.py
source-ready --expected-head "$SITE_HEAD"` before spending CI resources.
`source-ready` is the clean exact-head local gate: the current committed HEAD must
match the supplied SHA and the index, working tree and untracked-file inventory must
all be clean. It then runs the complete core suite, the canonical Playground Node
inventory, Site-owned source contracts, static Python dependency-boundary checks for
the core/build/visual/Composition requirements inputs. It does not run the managed
Composition consumer validator; run the explicit
`composition-validation` profile when that managed check is needed.
It does not acquire a Bundle, render a Site, use a provider checkout, or launch a
browser.

`python scripts/run_site_preflight.py artifact-local --bundle <verified Bundle directory>
--site-root <artifact directory>` validates an already produced Bundle and Site
artifact. Both paths are required; the profile fails closed when either is absent.
Neither local profile runs Playwright/browser/PWA acceptance; those remain
conditional/full remote CI checks.
Integration owns source semantics and provider qualification.

Remote construction uses the existing base-authoritative path classifier. Unknown
or CI-authority changes fail closed to broader checks. `ci/full-qualification`
selects all Site acceptance at a stable frontier. Diagnostic evidence never substitutes
for current exact-head acceptance. The routed Site acceptance skill uses these same
commands; stale CLI aliases have been removed.

## Immutable artifact reuse

`site-producer.yml` acquires the pinned Bundle with existing run/head/attempt,
upload-window, digest, extraction and provenance verification. Missing evidence may
invoke the pinned Integration workflow; corrupt evidence fails closed.

The Site build identity includes exact Site SHA, Bundle identity/provenance, recipe,
runtime/dependency environment and deployment timestamp. All browser consumers reuse
the one corresponding immutable Pages artifact. Changed effective inputs require
fresh evidence. Browser acceptance itself is never cached. Deployment timestamps
are outside Bundle identity and are qualified as Site artifact inputs.

## Release boundary

Provider work and Integration releases do not run Site Chromium, mobile or PWA suites.
Site-only fixes can qualify against an unchanged Bundle. While the repository remains in
Shadow, deployment is manually dispatched; after one explicit activation, the guarded
auto-publish route runs the full Site DAG against its timestamped artifact and deploys
only after success.
The full qualification aggregator verifies the eleven actual required DAG jobs rather
than treating a workflow shell or skipped job as acceptance. Browser acceptance is
provided by the applicable Playwright workflows; there is no empty Python browser
suite.
