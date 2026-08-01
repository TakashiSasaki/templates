# ADR-0004: Integrate the bootstrap trust seed into the policy branch

- Status: Accepted
- Date: 2026-08-01
- Supersedes: ADR-0001

## Context

The former `TakashiSasaki/agent-policy` repository distributed `bootstrap-agent-policy` from an orphan branch unrelated to its policy compiler branch. That layout made the branch root directly cloneable as a skill, but it also created a second long-lived history, duplicated repository-level automation assumptions, and complicated migration to `TakashiSasaki/templates:policy`.

The bootstrap trust boundary does not require a separate Git history. It requires an independently reviewable manifest, orchestration script, safety constraints, tests, and an immutable full-SHA reference to the executable policy toolchain.

## Decision

Store the bootstrap package at `skills/bootstrap-agent-policy/` in the `policy` branch.

The integrated skill remains an independent trust seed by construction:

- `bootstrap-manifest.yml` pins `TakashiSasaki/templates` at one full Git commit SHA;
- the pinned revision precedes the bootstrap-package commit and therefore does not depend recursively on itself;
- only inspection, initialization, adoption preparation/preview, validation, and check routes are declared;
- adoption finalization is deliberately absent from the manifest and orchestration script;
- changes to the pin, routes, skill instructions, orchestration script, installer, or tests are treated as trust-anchor changes requiring explicit review.

The Python package and executable retain the compatibility name `agent-policy`. Product manifests, adoption state, generated workflow templates, and schemas identify the executable repository as `TakashiSasaki/templates`.

## Distribution

A reviewed checkout of `policy` may install the skill using:

```bash
python skills/bootstrap-agent-policy/scripts/install.py <destination>
```

Consumers may obtain only the skill directory through a sparse checkout, but the checkout itself must be pinned to a reviewed full commit SHA. Mutable branch tips are not executable trust references.

## Consequences

- The former orphan bootstrap branch is no longer the active development or distribution source.
- Policy and bootstrap changes share one repository history while retaining separate review boundaries.
- Repository previews and structure verification need only describe the `policy` tree.
- The old repository and branch remain addressable during consumer migration because historical pins and links may still depend on them.
- Bootstrap consolidation does not itself migrate existing consumers or authorize archival of the former repository.
