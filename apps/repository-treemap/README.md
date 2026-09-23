# Repository Treemap

Static web app for visualizing repository directory trees.

## Canonical source

`src/` is the canonical application source. `dist/` is generated and is not tracked.

The app favors readable hierarchy exploration over mathematically exact rectangle areas. Actual file counts and byte sizes remain available in labels and long-press details, while layout weights are deliberately adjusted for mobile usability.

### Readable layout

- visible child directories are re-normalized to fill 100% of their parent's available treemap area;
- metric values use a monotonic `w^0.8` transform;
- very small siblings receive a bounded soft floor;
- D3 squarify uses ratio `1.2` to prefer compact rectangles;
- displayed Files/Bytes values remain the actual repository aggregates.

### Touch details

Touch/pen long-press uses a 500 ms hold and is cancelled after more than 12 px of pointer movement. The detail sheet shows path, descendant file count, aggregate size, and direct child-directory count. Tapping the backdrop outside the dialog closes it; tapping inside the detail sheet does not.

## Cache policy

GitHub API responses are cached by the Service Worker for exactly 30 minutes. At the TTL boundary an entry expires and the next read fetches GitHub again. The in-page parsed branch-tree cache uses the same TTL.

## Commands

```sh
npm ci
npm run check
```

`npm run build` copies `src/` to `dist/`.

## Render

- Build command: `cd apps/repository-treemap && npm ci && npm run check`
- Publish directory: `apps/repository-treemap/dist`
