---
id: skill-source.preserve-publication-branch-boundaries
severity: mandatory
overridable: false
order: 1050
---
# Preserve publication and unrelated-history boundaries

`skill`, `site`, `policy`, and `webapp` have unrelated histories. Do not merge, rebase, or cherry-pick across them.

The `skill` branch owns its publication catalog and stable document IDs. Public consumer documents resolve below `template/`. The `site` branch consumes reviewed full commit SHAs and owns navigation, assembly, provenance, repository-tree rendering, and deployment.

Keep Pages compatibility build-only from provider branches. GitHub Pages deployment remains suspended from `skill`; restoration belongs to a separate reviewed `site` pull request.
