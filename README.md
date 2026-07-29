# Documentation site

This orphan branch contains only the source and deployment workflow for the
`TakashiSasaki/templates` GitHub Pages site.

Canonical technical documentation remains on the `main` branch. The Pages
workflow checks out both branches, assembles a temporary Zensical project, and
deploys only the generated static files.

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
zensical serve --config-file .build/zensical.toml
```

The `.build/` directory is generated and must not be committed.
