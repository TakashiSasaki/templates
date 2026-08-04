# Documentation site

This orphan branch contains the source, reusable artifact-build workflow, and
exclusive deployment workflow for the `TakashiSasaki/templates` GitHub Pages
site.

Canonical technical documentation remains on the `main` branch. The build
workflow checks out both branches and assembles a temporary Zensical project,
but it has no deployment job or Pages write permission. Only
`.github/workflows/deploy-pages.yml`, triggered by a direct push to
`refs/heads/site`, can deploy the generated static files. This rule does not
consult the repository default branch.

## Published metadata

A direct `site` deployment captures the current time in Japan Standard Time
immediately before the Pages artifact is built. The generated footer displays
that value as `Deployment time: YYYY-MM-DD HH:MM:SS JST`. Pull-request and
other build-only artifacts display `Preview build (not deployed)` instead.

Every generated HTML page is normalized to contain exactly one canonical link
whose URL is `https://takashisasaki.github.io/templates/`.

## Local preview

From a clone with both branches available:

```sh
git worktree add ../templates-main main
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/assemble_docs.py \
  --source-root ../templates-main \
  --site-root . \
  --output-root .build
python scripts/prepare_site_metadata.py \
  --config-file .build/zensical.toml \
  --deployment-timestamp "" \
  --canonical-url https://takashisasaki.github.io/templates/
zensical serve --config-file .build/zensical.toml
```

The `.build/` directory is generated and must not be committed.
