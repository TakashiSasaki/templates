# Repository Treemap

Static web app for visualizing repository directory trees.

## Canonical source

`src/` is the canonical application source. `dist/` is generated and is not tracked.

The app favors readable hierarchy exploration over mathematically exact rectangle areas. Actual file counts and byte sizes remain available in labels and long-press details, while layout weights are deliberately adjusted for mobile usability.

### Readable layout

- visible child directories are re-normalized to fill 100% of their parent's available treemap area, so direct files that are not themselves rendered do not leave large visual gaps;
- metric values use a monotonic `w^0.8` transform, preserving order while compressing extreme size ratios;
- very small siblings receive a bounded soft floor (up to roughly 2% before final re-normalization);
- D3 squarify uses ratio `1.2` to prefer more compact rectangles;
- these adjustments affect layout only; displayed Files/Bytes values remain the actual repository aggregates.

The app also supports relative display depth, persistent parent header labels, adaptive labels down to 6px, touch/pen long-press details, and a 30-minute Service Worker cache for GitHub branch/tree data.

Touch long-press uses a 500 ms hold and is cancelled after more than 12 px of pointer movement so normal page scrolling remains available. A successful long-press suppresses the following click, preventing accidental zoom.

## Cache policy

GitHub API responses are cached by the Service Worker for exactly 30 minutes. At the TTL boundary an entry expires and the next read fetches GitHub again. The in-page parsed branch-tree cache uses the same TTL.

## Commands

```sh
npm ci
npm run check
```

`npm run build` copies `src/` to `dist/`. No bundler is required.

## Render

- Build command: `cd apps/repository-treemap && npm ci && npm run check`
- Publish directory: `apps/repository-treemap/dist`
