# Repository Treemap

Static web app for visualizing repository directory trees.

## Canonical source

`src/` is the canonical application source. `dist/` is generated and is not tracked.

The app is intentionally framework-light: HTML, CSS, ES modules, and D3 loaded from an exact-version CDN URL. It reads public GitHub repository trees with the GitHub REST API and lets the viewer:

- switch treemap area between descendant file count and descendant byte size;
- choose a relative display depth from the current focused directory;
- zoom into a directory and navigate back up or to the branch root;
- keep visible parent-directory names in a dedicated top header strip;
- render a directory name in every leaf or collapsed-boundary cell, adapting font size and wrapping for small rectangles;
- prefetch GitHub branch commit/tree data with a Service Worker and cache it for 30 minutes.

A relative depth of `1` renders only direct child directories. Deeper descendants are collapsed into their boundary directory while aggregate file-count and byte-size metrics are preserved.

Cell labels use three density levels. Large cells show name plus metrics, medium cells show the name only, and tiny cells retain the name with a minimum 6px font and character-level wrapping rather than becoming blank.

## Cache policy

GitHub API responses are cached by the Service Worker for exactly 30 minutes. Fresh entries are served from Cache Storage. At the TTL boundary an entry is expired and the next read fetches GitHub again. The in-page parsed branch-tree cache uses the same TTL.

## Commands

```sh
npm ci
npm run check
```

`npm run build` copies `src/` to `dist/`. No bundler is required.

## Render

- Build command: `cd apps/repository-treemap && npm ci && npm run check`
- Publish directory: `apps/repository-treemap/dist`
