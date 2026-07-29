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
5. Update `site-manifest.json` when the published page set, navigation, destination path, or canonical source path changes. A rename or move on `main` requires a matching manifest update even when the public page remains otherwise unchanged.

## Build and deployment policy

- Pull requests targeting `site` build and upload a Pages artifact but do not deploy it.
- Pushes to `site` validate the current site implementation but do not deploy it.
- The dispatcher on `main` calls the reusable workflow with an exact canonical source commit and explicitly enables deployment.
- The reusable workflow must check out the site implementation from `site`; it must not infer that ref from the caller's `github.sha` or `github.event_name`.

## Dependency updates

`requirements.txt` pins the Zensical version. Update it intentionally, run the strict site build, and review the generated navigation and URLs before merging.

## Local build

Follow the worktree-based instructions in `README.md`. The assembly script reads the canonical files from a separate `main` checkout and writes the temporary project under `.build/`.
