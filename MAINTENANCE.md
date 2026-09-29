# Site maintenance

Read [AGENTS.md](AGENTS.md). Presentation and browser changes belong entirely to Site.
The source tests need no provider checkout, provider revision update or network request:

```sh
python -m unittest discover -s tests -v
node --test tests/*.test.mjs
```

Download one publication and keep it outside the checkout. While editing, preview the
current working tree without making a commit:

```sh
python scripts/fetch_publication.py --output /tmp/templates-publication
python scripts/preview_site.py --bundle /tmp/templates-publication --output /tmp/templates-preview
python -m http.server --directory /tmp/templates-preview/site
```

The preview copies tracked and non-ignored files to a disposable Git snapshot. It does
not alter source, refs or the downloaded publication. Choose a new output path for each
build. Run the relevant browser regression scripts against that artifact for changes to
navigation, search, accessibility, PWA or layout. Final deployment builds use committed
source with exact build provenance; preview SHAs are temporary and never pushed.

For service-worker or PWA translation changes, run the real browser regression before
committing, against the uncommitted preview above:

```sh
python -m pip install -r requirements-build.lock -r requirements-visual.txt
python scripts/check_stale_translation_runtime.py --site-root /tmp/templates-preview/site --bundle /tmp/templates-publication --output /tmp/templates-pwa-evidence/translation-runtime.json
```

This uses installed Google Chrome. Where Chrome is unavailable, install Playwright's
browser with `python -m playwright install chromium` and add `--browser-channel chromium`.
Both run the actual service worker, offline reload, update and translation navigation
checks. The publication must contain stale, current and missing Japanese translation
cases; an absent case fails with an explicit prerequisite error. No pre-commit hook
launches a browser automatically; `run_site_preflight.py` runs unit tests only.

On GitHub, choose **Actions → Manual PWA browser validation → Run workflow**, selecting
`site` or a Site feature branch. An optional `publication_run` selects a retained
successful publication; otherwise the newest available success is used. The workflow
renders that immutable Bundle and runs the same script in Chrome. It runs only on manual
dispatch and has read-only permissions. Download its `pwa-browser-evidence` artifact
for phase durations, service-worker events, logs and a Playwright trace.

The checker waits for the page's own registration/update to settle before its explicit
worker rollout. This preserves the fix for the approximately 300-second controller
change wait. Individual update waits are bounded at 30 seconds and the GitHub browser
step at three minutes; failed runs retain diagnostics instead of waiting indefinitely.

Provider content lives in the Bundle. Site-local documents, CSS, JavaScript and templates
live here. Update generated files through their local generator. The installed reference
Composition/Policy products are examples, not a mandatory external maintenance workflow.

PR preparation uses local skills. Review scope follows the affected behavior; a visual
change does not require an upstream provider review or a publication adoption PR.
