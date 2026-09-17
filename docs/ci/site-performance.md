# Site CI performance and validation scope

Site consumes one exact Integration Bundle. Provider compatibility, materialization,
catalog/translation validation and Bundle production are Integration responsibilities.
The removed local provider capsule and provider profiling workflow are historical;
there is no second active provider build/cache subsystem in Site.

## Construction and qualification

Run `python scripts/run_site_preflight.py fast` for the L0 checks: diff hygiene on
committed, staged and unstaged changes, changed-file syntax/tests, JSON syntax and
classifier validation. `fast` is a cheap development preflight and may run on a dirty
tree; untracked non-ignored files are included in its changed-path inventory.

Run `python scripts/run_site_preflight.py ready --expected-head <FULL_SITE_SHA>` before
spending CI resources. `ready` is the clean exact-head local gate: the current
committed HEAD must match the supplied SHA and the index, working tree and untracked
file inventory must all be clean. It then runs the complete core suite, all applicable
pure Node tests, acquires the exact Bundle named by `integration-source.json`, renders
the real Site renderer, and validates the generated artifact. It accepts no provider
checkout roots and fails when the exact qualified Bundle is unavailable.

`python scripts/run_site_preflight.py full --bundle <verified Bundle directory>
--site-root <artifact directory>` remains available for isolated local assembly and
artifact checks. None of these local profiles runs Playwright/browser/PWA acceptance;
those remain conditional/full remote CI checks.
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
Site-only fixes can qualify against an unchanged Bundle. Explicit manual deployment
runs the full Site DAG against its timestamped artifact and deploys only after success.
The full qualification aggregator verifies the eleven actual required DAG jobs rather
than treating a workflow shell or skipped job as acceptance. Browser acceptance is
provided by the applicable Playwright workflows; there is no empty Python browser
suite.
