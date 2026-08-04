# Documentation site maintenance

This file applies only to the unrelated `site` branch.

## Branch responsibilities

- `main` contains the canonical technical documentation and `docs/publication-catalog.json`. It does not own or initiate Pages deployment.
- `site` contains the Zensical configuration, catalog-ID-based navigation manifest, assembly script, styling, reusable build-only workflow, and the only Pages deployment workflow.
- `webapp` and `policy` are unrelated histories and must not contain a Pages deployment route.
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

## Generated link integrity

The artifact-build workflow validates links after Zensical has generated the final HTML. This intentionally checks renderer output rather than trying to reproduce Markdown link and heading rules independently.

`scripts/validate_site_links.py` reads `project.site_url` from the generated Zensical configuration, scans every generated HTML page, and validates:

- relative links and same-origin absolute links that remain inside the configured site path;
- directory-style page URLs and explicit `index.html` aliases;
- links to generated non-HTML assets;
- fragment identifiers against actual generated `id` or legacy anchor `name` values;
- percent-encoded paths and fragments after URL decoding;
- locally authored relative or root-relative links that escape the configured site path.

External origins, non-HTTP schemes, same-origin URLs outside the configured project path, and browser text fragments are outside the generated artifact and are not checked. A local link must resolve to a file in the Pages artifact, and a fragment is valid only on an HTML target containing the referenced identifier.

When a canonical heading, destination, or relative link changes on `main`, compatibility workflows may pass an exact source commit to the reusable build-only workflow. Broken page and anchor references therefore fail validation before a later direct `site` push can deploy.

## Build provenance

Every uploaded Pages artifact contains `/build-provenance.json`. The deterministic schema records:

- `schema_version`, currently the integer `1`;
- `repository`, currently `TakashiSasaki/templates`;
- `site_commit`, the full commit SHA actually checked out into `site-source`;
- `canonical_source_commit`, the full commit SHA actually checked out into `canonical-source`.

The build workflow derives both commits from the checkout worktrees after the static build, then writes the provenance file before generated-link validation and artifact upload. Commit values must be lowercase, full-length 40-character SHAs; branch names, tags, and abbreviated SHAs are not accepted.

The file deliberately excludes timestamps, workflow run IDs, and mutable refs. Identical source commits therefore produce identical provenance content. The provenance file identifies build inputs but is not a cryptographic signature or an attestation of the artifact contents.

## Published deployment metadata

The deployment workflow captures a timestamp with `TZ=Asia/Tokyo` before invoking the reusable build. The accepted format is exactly `YYYY-MM-DD HH:MM:SS JST`. `scripts/prepare_site_metadata.py` rejects any other value and writes a Zensical `project.copyright` notice so every deployed page footer displays `Deployment time: <timestamp>`.

Build-only invocations do not claim a deployment. An empty timestamp produces the stable footer text `Preview build (not deployed)`.

The timestamp intentionally belongs to generated HTML rather than `/build-provenance.json`. The provenance file remains deterministic, while a deployment artifact is intentionally time-specific.

`project.site_url` must remain `https://takashisasaki.github.io/templates/`. After Zensical builds the site, `scripts/finalize_site_metadata.py` normalizes the canonical `<link>` in every generated HTML file to that public root URL. It inserts the link when Zensical omits it, including on `404.html`, and rejects duplicate canonical links.

## Build and deployment policy

`.github/workflows/build-pages.yml` is build-only. It may be invoked for pull requests targeting `site` or through `workflow_call`. It has `contents: read`, uploads a generated artifact, and contains no deployment job, `pages: write`, `id-token: write`, Pages environment, `actions/configure-pages`, or `actions/deploy-pages` step.

The legacy `deploy` workflow-call input is accepted temporarily so an older caller cannot regain deployment merely by passing `deploy: true`. The value is ignored. Removing this compatibility input is safe after all callers stop supplying it.

`.github/workflows/deploy-pages.yml` is the sole deployment authority. It has only this trigger:

```yaml
on:
  push:
    branches:
      - site
```

The deployment job additionally requires all of the following:

```text
github.repository == TakashiSasaki/templates
github.event_name == push
github.ref == refs/heads/site
```

The condition does not inspect `github.event.repository.default_branch`. Changing the repository default branch therefore cannot authorize a deployment from `main`, `webapp`, `policy`, or another ref.

The deployment workflow captures the JST timestamp, then calls the local build-only workflow for the exact pushed `site` commit and the current canonical `main` source. Only after that build succeeds does the deployment job receive `pages: write` and `id-token: write`. The deployment workflow has no `workflow_call`, `workflow_dispatch`, or pull-request trigger, so another branch workflow cannot invoke it as a reusable deployment service.

Expected behavior:

| Event | Build artifact | Footer metadata | Pages deployment |
|---|---:|---|---:|
| pull request targeting `site` | yes | preview | no |
| push to `site` | yes | JST deployment timestamp | yes |
| `workflow_call` from `main` | yes | preview unless explicitly supplied | no |
| workflow on `webapp` or `policy` | branch-local only | not applicable | no |
| push to any other branch | no site deployment workflow | not applicable | no |

## Dependency updates

`requirements.txt` pins the Zensical version. Update it intentionally, run the strict site build, and review the generated navigation and URLs before merging.

## Local build

Follow the worktree-based instructions in `README.md`. The assembly script reads the canonical files and publication catalog from a separate `main` checkout and writes the temporary project under `.build/`.
