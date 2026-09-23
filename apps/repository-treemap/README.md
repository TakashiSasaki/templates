# Repository Treemap

Static web-app skeleton for visualizing repository directory trees.

## Canonical source

`src/` is the canonical application source. `dist/` is generated and is not tracked.

The app is intentionally framework-light: HTML, CSS, ES modules, and D3 loaded from an exact-version CDN URL. The current skeleton reads public GitHub repository trees with the GitHub REST API and lets the viewer switch treemap area between descendant file count and descendant byte size.

## Layout

- `src/` — canonical browser source
- `scripts/` — build and validation logic
- `tests/` — pure-data tests
- `dist/` — generated publish directory

## Commands

```sh
npm ci
npm run check
```

`npm run build` copies `src/` to `dist/`. No bundler is required.

## Render

Use the repository branch containing this directory with:

- Build command: `cd apps/repository-treemap && npm ci && npm run check`
- Publish directory: `apps/repository-treemap/dist`

The generated output remains reproducible from tracked source and the pinned CDN dependency in `src/js/main.js`.
