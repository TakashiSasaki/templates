# Documentation publication

The `policy` branch builds this documentation through `.github/workflows/pages.yml`. GitHub Pages artifact upload and deployment are retained in the workflow but intentionally disabled.

## Current workflow boundary

Both pull requests targeting `policy` and pushes to `policy` use the branch-maintainer baseline of Ubuntu 24.04 and CPython 3.12.13. Before the first Python invocation, the build neutralizes externally supplied interpreter-startup and pip behavior inputs. It then clears and recreates an isolated virtual environment, installs only the complete arbitrary-exact documentation lock with dependency resolution disabled and pip isolated from unlisted environment inputs, verifies the installed distribution set and dependency graph, regenerates repository previews and documentation assets, verifies the documented tree, and runs the strict MkDocs build.

The Pages artifact-upload step and deployment job remain present for later use, but both are protected by a hard-coded false condition. Therefore no current `policy` event uploads a Pages artifact or deploys a site. Pull-request and push builds receive only `contents: read` unless the disabled deployment job is explicitly enabled by a reviewed change.

The workflow does not fetch `main`, `site`, `webapp`, the former orphan bootstrap branch, or the former `TakashiSasaki/agent-policy` repository. The repository default branch is `main`, while this workflow intentionally exists only in the unrelated `policy` history. GitHub manual dispatch requires the workflow file to exist on the default branch, so this workflow deliberately omits `workflow_dispatch`.

All third-party actions are pinned to full commit SHAs. The checkout and Python setup actions use the same reviewed Node 24 revisions as Policy CI. `requirements-docs.txt` records the direct documentation dependencies with arbitrary exact equality (`===`), while `requirements-docs.lock` records the complete arbitrary-exact dependency graph resolved for CPython 3.12.13 on `ubuntu-24.04`. The workflow installs only from the lock file with `--isolated --no-deps`, then `scripts/verify_docs_environment.py` rejects any missing, unexpected, or version-mismatched distribution except the virtual environment's bootstrap `pip`. `pip check` runs before documentation generation. Dependency updates require a reviewed re-resolution, synchronized input and lock changes, verifier regression updates, and a successful strict build.

The documentation lock fixes exact version strings, not wheel or source-distribution bytes and not package-index origin. Artifact hashes and explicit repository-origin enforcement would be separate trust-boundary changes. The documentation environment remains a branch-maintainer toolchain and does not choose a runtime, package manager, or deployment platform for repositories that consume the policy toolkit.

## Deployment enablement boundary

Do not enable Pages deployment as an incidental documentation or policy change. Enabling publication requires a dedicated reviewed change that:

1. removes the hard-coded false condition from both the Pages artifact-upload step and the deployment job while retaining the `policy` branch and non-pull-request guards;
2. confirms the repository Pages source and environment settings;
3. determines whether `agent-policy.moukaeritai.work` should be moved from the former repository;
4. runs and verifies the enabled deployment before describing publication as complete.

Until that change is approved and merged, Pages settings and custom-domain migration are deliberately deferred.

## Build verification

The currently enabled documentation build is successful only when all of the following pass:

- immutable checkout and Python-setup action revisions;
- Ubuntu 24.04 and CPython 3.12.13 selection;
- interpreter-startup and pip-input neutralization before setup and installation;
- cleared isolated virtual-environment creation;
- installation from the complete arbitrary-exact dependency lock with `--isolated --no-deps`;
- exact installed-distribution-set verification;
- `pip check`;
- repository preview generation;
- documented-tree verification;
- documentation asset generation;
- build metadata generation;
- `.venv/bin/python -m mkdocs build --strict --clean`;
- regression tests confirming both deployment guards remain disabled.

A successful MkDocs build does not mean that documentation has been published. Publication remains incomplete while artifact upload and deployment are disabled.
