# Maintain templates

This workspace is for maintainers of the source authorities and the deployed website.
If you are building a project with the templates, start at [Use templates](use.md).

## Change the source that owns the behavior

| What you are changing | Source authority |
| --- | --- |
| Records and information models | [Modeling](https://github.com/TakashiSasaki/templates/tree/modeling) |
| Components, recipes and Composer | [Composition](https://github.com/TakashiSasaki/templates/tree/composition) |
| Agent rules and policy tooling | [Policy](https://github.com/TakashiSasaki/templates/tree/policy) |
| Semantic assembly and publication | [Integration](https://github.com/TakashiSasaki/templates/tree/integration) |
| Website structure, appearance and behavior | [Site](https://github.com/TakashiSasaki/templates/tree/site) |

The branches have independent histories. Changes move downstream as publication
artifacts; they do not require coordinated source merges.

## Work locally

- [Maintainer onboarding](maintainer-onboarding.md) identifies the owning branch and checks.
- [Preview the website](../MAINTENANCE.md) uses one downloaded publication while you edit.
- [Publish and recover](../PUBLISHING.md) explains successful artifacts and Pages deployment.
- [Publication operations](publication-automation.md) traces failures to their owning stage.

## Inspect what is running

[Build provenance](/build-provenance.json) records the source revisions used by this
website. [GitHub Actions](https://github.com/TakashiSasaki/templates/actions) shows
publication and deployment runs. A failed new build leaves the current website available.
