# ADR-0004: Integrate the bootstrap trust seed into the policy branch

- Status: Accepted
- Date: 2026-08-01

## Context

Repository onboarding requires a small, independently reviewable trust seed that can select a safe initialization or adoption route without executing a mutable branch tip or granting generic mutation authority.

The bootstrap trust boundary does not require a separate Git history. It requires an independently reviewable manifest, orchestration script, safety constraints, tests, and an immutable full-SHA reference to the executable policy toolchain.

## Decision

Store the bootstrap package at `skills/bootstrap-agent-policy/` in the `policy` branch.

The integrated skill remains an independent trust seed by construction:

- `bootstrap-manifest.yml` pins `TakashiSasaki/templates` at one full Git commit SHA;
- the pinned revision precedes the bootstrap-package promotion state and therefore does not depend recursively on itself;
- only inspection, initialization, adoption preparation/preview, validation, and check routes are declared;
- adoption finalization is deliberately absent from the manifest and orchestration script;
- changes to the pin, routes, skill instructions, orchestration script, installer, or tests are treated as trust-anchor changes requiring explicit review.

The Python package and executable are named `agent-policy`. Product manifests, adoption state, generated workflow templates, and schemas identify the executable repository as `TakashiSasaki/templates`.

## Distribution

A reviewed checkout of `policy` may install the skill using:

```bash
python skills/bootstrap-agent-policy/scripts/install.py <destination>
```

Consumers may obtain only the skill directory through a sparse checkout, but the checkout itself must be pinned to a reviewed full commit SHA. Mutable branch tips are not executable trust references.

## Consequences

- Policy and bootstrap changes share one repository history while retaining separate review boundaries.
- Repository previews and structure verification describe the `policy` tree as the source of the bootstrap package.
- Bootstrap and ordinary managed-repository operation use the same stable toolchain identity while exposing different authorized routes.
- Bootstrap consolidation does not weaken the separate explicit authorization required for adoption finalization.
