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
