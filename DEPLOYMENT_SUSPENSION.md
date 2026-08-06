# GitHub Pages deployment suspension record

GitHub Pages deployment from the `site` branch was temporarily suspended while the `webapp` branch was restructured into a template-development source tree with a separately copyable application-template distribution.

During the suspension, the existing Pages site remained available. Pushes to `site` continued to exercise source locking, publication assembly, source and copyable-template repository-tree generation, bounded previews, strict static-site generation, provenance, link validation, and Pages-artifact creation, but received no Pages write or OpenID Connect authority and did not invoke `actions/deploy-pages`.

The reopening conditions were completed in order:

1. The `webapp` copyable distribution and its source, distribution, and clean-room product conformance suites were completed.
2. `publication-sources.json` was locked to reviewed Webapp revision `1671c5b503377b87d157aeaa714bdf7c43797dc9`.
3. The integrated site, including the dedicated copyable-template tree, passed build-only validation at site revision `f372805850848fb4fc05205ebb47d27e5e6b45f6`.
4. A separate pull request restored deployment authority only to a push to `refs/heads/site`, retained the reusable build workflow as build-only, and restored Pages and OpenID Connect permissions only on the deployment job.

`deployment-state.json` is the machine-readable current state. The unrelated histories of `site`, `webapp`, `skill`, and `policy` remained separate throughout the transition.
