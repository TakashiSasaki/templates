# Temporary GitHub Pages deployment suspension

GitHub Pages deployment from the `site` branch is intentionally suspended while the `skill` branch is restructured from a repository-root installable skill into a template-product source repository with a separately copyable profile-aware skill template under `template/`.

The currently deployed Pages site remains available. The suspension prevents subsequent pushes to `site` from replacing it. During the suspension, `.github/workflows/deploy-pages.yml` continues to invoke the reusable build workflow so that source locking, publication assembly, repository-tree generation, bounded previews, strict static-site generation, provenance, link validation, and Pages-artifact creation remain exercised. It grants no `pages: write` or `id-token: write` permission and invokes neither `actions/configure-pages` nor `actions/deploy-pages`.

`deployment-state.json` is the machine-readable source of the suspension state, the currently locked Skill revision, and the reopening conditions.

Deployment may be restored only in a separate pull request based on the then-current `site` branch after all of the following are true:

1. The `skill` branch exposes the canonical copyable profile-aware template at `template/`, preserves the supported profile tags and combinations, and passes its complete validation suite.
2. `publication-sources.json` locks `skill` to the final reviewed lowercase full 40-character merge commit SHA.
3. The integrated site publishes separate complete-source and copyable-template views for Skill and passes build-only validation against that exact revision.
4. The restoring pull request reinstates deployment authority only for a push to `refs/heads/site`, keeps the reusable build workflow build-only, and restores Pages permissions only on the deployment job.

The unrelated histories of `site`, `skill`, `policy`, and `webapp` remain separate throughout the transition.
