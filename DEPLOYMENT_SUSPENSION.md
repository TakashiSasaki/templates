# GitHub Pages deployment suspension record

GitHub Pages deployment from the `site` branch was temporarily suspended while the `webapp` branch was restructured into a template-development source tree with a separately copyable application-template distribution.

The suspension is complete. The final reviewed Webapp publication revision is `1671c5b503377b87d157aeaa714bdf7c43797dc9`. It was integrated into `site` by merge commit `552af87fb32e614072ac195e83514e47feaf5c01`. A subsequent reviewed Site change added the dedicated copyable-template tree, producing pre-restoration Site revision `f372805850848fb4fc05205ebb47d27e5e6b45f6`. Build-only Site pushes for these revisions completed source locking, publication assembly, repository-tree generation, bounded previews, strict static-site generation, provenance, link validation, and Pages-artifact creation successfully before deployment authority was restored.

Deployment is active under the following boundary:

1. `.github/workflows/deploy-pages.yml` is triggered only by a push to `refs/heads/site` in `TakashiSasaki/templates`.
2. `.github/workflows/build-pages.yml` remains reusable and build-only; it receives only `contents: read` permission.
3. `pages: write` and `id-token: write` are granted only to the final deployment job.
4. The deployment job runs only after the build job succeeds and targets the `github-pages` environment.
5. `publication-sources.json` continues to lock all provider publications to reviewed lowercase full 40-character commit SHAs.

`deployment-state.json` is the machine-readable source of the current active state and its deployment boundary. The unrelated histories of `site`, `webapp`, `skill`, and `policy` remain separate.
