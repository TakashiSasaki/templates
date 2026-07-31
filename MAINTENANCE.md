# Documentation site maintenance

This file applies only to the unrelated `site` branch.

## Branch responsibilities

- `main` contains the canonical technical documentation, `docs/publication-catalog.json`, and the minimal Pages dispatcher.
- `site` contains the Zensical configuration, catalog-ID-based navigation manifest, assembly script, styling, and reusable build/deploy workflow.
- Generated Markdown and HTML are temporary build artifacts and must not be committed.

The publication catalog on `main` owns stable document IDs, canonical source paths, optionality, and the single home-page designation. The site manifest owns reader-facing titles, hierarchy, and destination paths. Do not duplicate catalog-owned values in `site-manifest.json`.

## Change process

1. Branch from `site`, not from `main`.
2. Open a pull request whose base branch is `site`.
3. Require the documentation-site build to succeed before merging.
4. Keep canonical prose and publication-catalog changes on `main`.
5. Update `site-manifest.json` when a catalog document ID is added or removed, or when navigation hierarchy, reader-facing title, or destination path changes.
6. Do not update the site manifest for a canonical source rename or optionality change; update the existing catalog entry on `main` while preserving its stable document ID.

A coordinated publication-set change normally merges the `main` catalog change first and the `site` navigation change second. During the interval, Pages assembly fails intentionally because catalog and navigation coverage must be exact.

## Navigation manifest

`site-manifest.json` contains a top-level `navigation` array. Each item is exactly one of the following node types:

- a page with `title`, `document`, and `destination` fields;
- a section with `title` and a non-empty `children` array containing page or nested section nodes.

`document` is a stable ID declared by `docs/publication-catalog.json` on `main`. Page nodes must not contain canonical `source` or `optional` fields.

The assembler enforces these invariants before copying any canonical page:

- page and section fields may not be mixed;
- unsupported fields are rejected;
- every navigation title is non-empty and globally unique;
- every page document ID and destination is globally unique;
- every catalog document ID appears exactly once in navigation;
- unknown document IDs and catalog omissions are rejected;
- destination values are safe relative Markdown paths;
- the first navigation entry references the catalog home document and generates `index.md`;
- an explicitly empty section is invalid;
- a missing source is omitted only when the catalog marks that document optional;
- a section whose children are all omitted optional documents is omitted from generated navigation.

Page order and section order in the manifest are public information architecture. Keep Core Skill and profile-selection material before optional CLI, MCP, Web, and deployment guidance.

## Build and deployment policy

- Pull requests targeting `site` build and upload a Pages artifact but do not deploy it.
- Pushes to `site` validate the current site implementation but do not deploy it.
- The dispatcher on `main` calls the reusable workflow with an exact canonical source commit and explicitly enables deployment.
- The reusable workflow must check out the site implementation from `site`; it must not infer that ref from the caller's `github.sha` or `github.event_name`.

## Dependency updates

`requirements.txt` pins the Zensical version. Update it intentionally, run the strict site build, and review the generated navigation and URLs before merging.

## Local build

Follow the worktree-based instructions in `README.md`. The assembly script reads the canonical files and publication catalog from a separate `main` checkout and writes the temporary project under `.build/`.
