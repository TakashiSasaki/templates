# Repository Treemap

Static web app for visualizing repository directory trees.

## Canonical source

`src/` is the canonical application source. `dist/` is generated and is not tracked.

The app is intentionally framework-light: HTML, CSS, ES modules, and D3 loaded from an exact-version CDN URL. It reads public GitHub repository trees with the GitHub REST API and lets the viewer:

- switch treemap area between descendant file count and descendant byte size;
- choose a relative display depth from the current focused directory;
- zoom into a directory and navigate back up or to the branch root;
- keep visible parent-directory names in a dedicated top header strip;
- prefetch GitHub branch commit/tree data with a Service Worker and cache it for 30 minutes.

A relative depth of `1` renders only direct child directories. Deeper descendants are collapsed into their boundary directory while aggregate file-count and byte-size metrics are preserved.

## Cache policy

GitHub API responses are cached by the Service Worker for exactly 30 minutes. Fresh entries are served from Cache Storage. At the TTL boundary an entry is expired and the next read fetches GitHub again. The Service Worker also prefetches the configured branches so branch switching can reuse fresh cached commit and recursive-tree responses.

## Commands

```sh
npm ci
npm run check
```

`npm run build` copies `src/` to `dist/`. No bundler is required.

## Render

- Build command: `cd apps/repository-treemap && npm ci && npm run check`
- Publish directory: `apps/repository-treemap/dist`
