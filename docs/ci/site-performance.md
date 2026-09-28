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

## Service Worker update wait: measured case

The translation warning browser check in
`scripts/check_stale_translation_runtime.py`
replaces its locally served Service Worker and waits for `controllerchange` to
verify that the new worker controls the existing page. The page's
`assets/javascripts/pwa.js` also calls `register()`, sends a
`templates:get-current-freshness-state` message, and calls `update()` after page
load. An offline cached reload followed immediately by the check's explicit
update can overlap that page-owned update.

The exact-head CI runs on 2026-09-28 showed:

| Evidence | Before page-update settlement | After page-update settlement |
|---|---:|---:|
| Run | [36435967154](https://github.com/TakashiSasaki/templates/actions/runs/36435967154) | [36440431857](https://github.com/TakashiSasaki/templates/actions/runs/36440431857) |
| Page-owned update settlement | Unobserved | 2.087 s |
| `controllerchange` wait | 299.991 s | 0.102 s |
| Translation warning browser step | 314 s | 15 s |
| Browser `check` job | 7 min 12 s | 2 min 22 s |

The runs tested exact Site heads
`88f64e9c3dcdbae8c4fe408207aeb2a163b35a97` and
`efd544a28dc94774c21dc41ab494a1f494766324`, respectively, with system
Chrome 153. The new run saved its lifecycle JSON and trace in the
`mobile-visual-1079` artifact.

The older run found and installed the new worker in about 2.4 seconds;
`skipWaiting()` settled in milliseconds. Instrumented Service Worker event
promises and browser requests also settled promptly. CDP showed the old worker
stop, restart for a `message` event, and remain running until the new worker
began activating about 300 seconds later. That observation does **not** identify
which browser-side request remained in flight. Chromium defines a default
[five-minute Service Worker request timeout](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/content/browser/service_worker/service_worker_version.h#824),
but the matching duration alone does not prove this specific request hit it;
the evidence does not support a five-minute cache lifetime or a stuck
`waitUntil()` promise.

Same-artifact local comparisons with Chromium 149 narrowed the test race:
waiting for `load` alone still took 299.985 seconds, and adding one second still
took 300.013 seconds. Suppressing the page's freshness query reduced the wait to
0.036 seconds, but that was a diagnostic experiment. Waiting instead for the
page's own `register()` and `update()` promises to settle reduced it to 0.133
seconds while preserving the query and all ten acceptance checks. The committed
checker uses that observable settlement condition; its page-only probe returns
the native API results unchanged and is absent from the published Site artifact.

For a future update delay, compare the exact Pages artifact and browser version,
then record `updatefound`, install, `skipWaiting()`, waiting, activation,
`controllerchange`, old-worker status, event/promise settlement, and page-owned
registration/update timing separately. The checker writes these observations to
`translation-status.json` and a Playwright trace in the `mobile-visual` CI
artifact. Attach the CDP `ServiceWorker` domain to the page target; a
browser-level CDP session may not expose it. Preserve the takeover assertion and
normal page messages in the final check.
