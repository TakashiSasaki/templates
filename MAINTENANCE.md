# Documentation site maintenance

This file applies only to the unrelated `site` branch.

## Branch responsibilities

- `main` contains the canonical technical documentation and the minimal Pages dispatcher.
- `site` contains the Zensical configuration, page manifest, assembly script, styling, and reusable build/deploy workflow.
- Generated Markdown and HTML are temporary build artifacts and must not be committed.

## Change process

1. Branch from `site`, not from `main`.
2. Open a pull request whose base branch is `site`.
3. Require the documentation-site build to succeed before merging.
4. Keep canonical prose changes on `main`.
5. Update `site-manifest.json` when the published page set, navigation hierarchy, destination path, or canonical source path changes. A rename or move on `main` requires a matching manifest update even when the public page remains otherwise unchanged.

## Navigation manifest

`site-manifest.json` contains a top-level `navigation` array. Each item is exactly one of the following node types:

- a page with `title`, `source`, `destination`, and optional boolean `optional` fields;
- a section with `title` and a non-empty `children` array containing page or nested section nodes.

The assembler enforces these invariants before copying any canonical page:

- page and section fields may not be mixed;
- unsupported fields are rejected;
- every navigation title is non-empty and globally unique;
- every page source and destination is globally unique;
- source and destination values are safe relative paths;
- every destination is a Markdown file;
- the first included navigation entry is a page that generates `index.md`;
- an explicitly empty section is invalid;
- an optional missing page is omitted from its section;
- a section whose children are all omitted optional pages is omitted from generated navigation.

Page order and section order in the manifest are public information architecture. Keep Core Skill and profile-selection material before optional CLI, MCP, Web, and deployment guidance.

## Build and deployment policy

- Pull requests targeting `site` build and upload a Pages artifact but do not deploy it.
- Pushes to `site` validate the current site implementation but do not deploy it.
- The dispatcher on `main` calls the reusable workflow with an exact canonical source commit and explicitly enables deployment.
- The reusable workflow must check out the site implementation from `site`; it must not infer that ref from the caller's `github.sha` or `github.event_name`.

## Dependency updates

`requirements.txt` pins the Zensical version. Update it intentionally, run the strict site build, and review the generated navigation and URLs before merging.

## Local build

Follow the worktree-based instructions in `README.md`. The assembly script reads the canonical files from a separate `main` checkout and writes the temporary project under `.build/`.
