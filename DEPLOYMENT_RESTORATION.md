# GitHub Pages deployment restoration

GitHub Pages deployment from the `site` branch is active again after completion of the Skill template artifact restructuring and its separate site integration.

## Reviewed inputs

The live publication inputs are always the immutable full-SHA revisions recorded in `publication-sources.json` for Skill, Policy, and Web application. `deployment-state.json` records the currently integrated Skill revision and must agree with the Skill source lock.

The Skill revision exposes `template/` as the sole copyable Skill artifact. The integrated site publishes both the complete Skill source tree and the copyable `template/` tree, and validates both against the same immutable revision.

The original restoration event used the reviewed Skill revision current at that time. That historical restoration SHA is not a permanent publication lock: later reviewed Skill, Policy, and Webapp changes are published by updating `publication-sources.json` to their newer full merge SHAs and re-running the same site integration boundary.

## Deployment boundary

`.github/workflows/build-pages.yml` remains build-only. It has `contents: read`, creates and validates the complete site artifact, and uploads the Pages artifact. It has no Pages or OIDC write permission and invokes no deployment action.

`.github/workflows/deploy-pages.yml` is the only deployment authority. It runs only for a push to `site` and requires all of the following:

```text
github.repository == TakashiSasaki/templates
github.event_name == push
github.ref == refs/heads/site
```

The workflow captures the deployment timestamp in Asia/Tokyo, invokes the reusable build at the exact pushed site SHA, and grants `pages: write` plus `id-token: write` only to the final deployment job. The `github-pages` environment, `actions/configure-pages`, and `actions/deploy-pages` are confined to that job.

Default-branch status is not used as an authorization condition. A change to the repository default branch cannot authorize deployment from `skill`, `policy`, `webapp`, or another ref.

## Restoration evidence

Deployment was restored only after:

1. the final Skill restructuring PR was merged and its complete validation suite passed;
2. `site` locked the resulting full Skill merge SHA;
3. the integrated build assembled all Skill catalog documents;
4. separate complete-source and copyable-template Skill trees were generated and link-validated;
5. strict static-site generation, provenance recording, and Pages-artifact upload passed while deployment remained suspended; and
6. a separate restoration change reinstated only the bounded site-push deployment authority.

That sequence documents why deployment authority was restored. It does not freeze publication content at the restoration-era source revisions. Current source revisions remain governed by `publication-sources.json` and the full-SHA integration checks.

`deployment-state.json` is the machine-readable active-state record. The unrelated histories of `site`, `skill`, `policy`, and `webapp` remain separate.
