# Site CI performance and validation scope

Site consumes one exact Integration Bundle. Provider compatibility, materialization,
catalog/translation validation and Bundle production are Integration responsibilities.
The removed local provider capsule and provider profiling workflow are historical;
there is no second active provider build/cache subsystem in Site.

## Construction and qualification

Run `python scripts/run_site_preflight.py fast --expected-head <exact Site SHA>`
for the complete local Site core suite. For a verified Bundle and generated Site,
run `python scripts/run_site_preflight.py ready --expected-head <exact Site SHA>
--bundle <verified Bundle directory> --site-root <artifact directory>`.
This reaches core, browser-controller and Bundle reader contracts. It accepts no
provider checkout roots. Integration owns source semantics and provider qualification.

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
The full qualification aggregator verifies actual required jobs rather than treating
a workflow shell or skipped browser suite as acceptance.
