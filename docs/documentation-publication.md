# Documentation publication

The `policy` branch publishes this documentation through `.github/workflows/pages.yml`.

## Workflow boundary

The workflow has two distinct modes:

- pull requests targeting `policy` install the pinned documentation dependencies, regenerate repository previews and documentation assets, verify the documented tree, and run `mkdocs build --strict --clean`;
- pushes to `policy` perform the same build, upload the `site/` directory as a GitHub Pages artifact, and deploy it through the `github-pages` environment.

Pull-request runs receive only `contents: read`. The `pages: write` and `id-token: write` permissions exist only on the deployment job, which is additionally guarded by the `policy` branch ref. The workflow does not fetch `main`, `site`, `webapp`, the former orphan bootstrap branch, or the former `TakashiSasaki/agent-policy` repository.

The repository default branch is `main`, while this workflow intentionally exists only in the unrelated `policy` history. GitHub manual dispatch requires the workflow file to exist on the default branch, so this workflow deliberately omits `workflow_dispatch`. A publication retry uses GitHub Actions' rerun command on an existing `policy` push run, or a reviewed follow-up commit to `policy`.

All third-party actions are pinned to full commit SHAs. Documentation dependencies are pinned in `requirements-docs.txt`.

## Repository settings cutover

After the publication workflow is merged, a repository administrator must complete the GitHub Pages settings cutover:

1. Open the Pages settings for `TakashiSasaki/templates`.
2. Set **Build and deployment → Source** to **GitHub Actions**.
3. Release `agent-policy.moukaeritai.work` from the former repository if it is still registered there.
4. Configure `agent-policy.moukaeritai.work` as the custom domain for `TakashiSasaki/templates` and retain HTTPS enforcement.
5. If the merge-triggered deployment ran before the settings cutover, rerun that existing **Policy documentation** workflow run after the cutover. Alternatively, merge a reviewed follow-up commit into `policy` to create a new push-triggered deployment.

The former repository must remain available during this cutover. Removing a custom-domain association is not the same operation as deleting or archiving that repository.

## Verification

A successful cutover requires all of the following:

- the workflow build and deploy jobs both succeed for a `policy` commit;
- the deployment environment URL resolves to the intended documentation site;
- `/build-info.json` reports `TakashiSasaki/templates` as the repository and the deployed `policy` commit as `commit`;
- repository preview links identify `TakashiSasaki/templates` and the immutable deployed commit;
- the former repository is no longer the active Pages deployment source for the custom domain.

Do not mark documentation migration complete merely because the MkDocs build succeeds. Publication is complete only after the Pages settings, custom domain, deployment, and public endpoint have been verified together.
