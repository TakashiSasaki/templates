# Repository Treemap agent instructions

These instructions apply to `apps/repository-treemap/` and all descendants, in addition to the repository-level `AGENTS.md`.

## Deployment policy

- The current deployment platform for this web app is **Render Static Site**.
- Keep the Git repository as the source of truth. `src/` is canonical source; `dist/` is generated and must not become an authored source surface.
- Do not move this app to another hosting/deployment provider, replace Render, or create a competing canonical deployment without explicit user authorization.
- The current public deployment URL is recorded in this directory's `README.md`. If the public URL changes, update that README in the same logical change.
- Do not assume Render branch, auto-deploy, service identity, or current deployed commit from stale conversation context. Before a deployment operation, inspect the live Render service configuration and bind the operation to the intended Git revision.
- The expected Render build contract is:
  - build command: `cd apps/repository-treemap && npm ci && npm run check`
  - publish directory: `apps/repository-treemap/dist`
- Before reporting a source change as deploy-qualified, run `npm ci && npm run check` from this app directory or establish equivalent exact-head evidence from Render.
- If a task requires an externally visible deployment, verify that Render deployed the intended exact Git head and report the resulting deploy state separately from repository-local and GitHub CI evidence.

## Maintenance notes

- Preserve the 30-minute GitHub-data cache policy unless the task explicitly changes it.
- Preserve the distinction between actual Files/Bytes aggregates and readability-adjusted treemap layout weights.
- Preserve touch behavior: tap/click for zoom, long-press for details, and backdrop tap to dismiss the detail dialog.
- Preserve browser-local preference behavior unless explicitly changed: remember the last selected branch and a separate Relative depth value per branch using the versioned localStorage preference contract.
- Keep explanatory prose in the About view rather than above the treemap so the default mobile Treemap view remains visualization-first and can fit within the initial viewport with minimal page scrolling.
- Preserve latest-selection-wins behavior for asynchronous branch loads; stale GitHub responses must never replace the currently selected branch, and a failed branch load must not become the persisted initial branch.

- Preserve the README view as a rendering of this directory's canonical `README.md`, not a separately authored HTML copy. The build must copy that root README into `dist/`.
- Keep Markdown rendering dependencies exact-version pinned from CDN and sanitize parser output before assigning it to `innerHTML`.
- Preserve the compact top-bar control cluster: view tabs on the left, branch dropdown followed by fullscreen pictogram and close pictogram on the right. Keep the fullscreen control accessible via dynamic aria-label/title and preserve the close-button fallback behavior.

- Preserve branch persistence and latest-selection-wins semantics when changing the branch selector presentation; the dropdown is presentation only, not a change to branch-loading state rules.

- On mobile, keep Depth, Files/Bytes, Up, and Root grouped as one floating treemap toolbar so they do not consume normal-flow vertical space. Visible labels should be pictograms; retain accessible names/tooltips and the current numeric Depth value.

- Do not duplicate the selected branch name in the treemap breadcrumb. The branch dropdown is the branch identity surface; the breadcrumb is hidden at root and, below root, contains directory path segments only.

- Preserve reciprocal navigation to the Site landing page through the top-bar home pictogram. The canonical return URL is `https://templates.moukaeritai.work/`; keep an accessible label/title when changing its presentation.
