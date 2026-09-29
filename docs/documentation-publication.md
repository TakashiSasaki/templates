# Documentation build and publication boundary

Policy owns its source documentation and local catalog validation. GitHub Pages
publishing belongs exclusively to the independent `site` authority. Policy's
historically named `.github/workflows/pages.yml` only builds documentation with
read-only repository permissions.

The local catalog parser is `scripts/publication_catalog.py`. There is no Integration
checkout, reviewed parser pin or Site adoption step in Policy CI. Integration
snapshots this branch independently and Site consumes a completed publication.
The reusable `agent-policy` product does not depend on either publishing stage.

For a local documentation build, install `requirements-docs.lock` in a virtual
environment and run `python scripts/run_policy_preflight.py --check docs`.
The normal test and source-discovery commands are documented in `AGENTS.md`.
GitHub Actions uses the same local documentation validation. A successful build
is local/CI evidence; it does not mean the website has been deployed.

English is canonical. Japanese is an optional reference translation. Normal
validation permits stale translations, and the website marks them visibly with
a link to current English. A source edit needs no simultaneous translation edit.
Translation review can be performed later from `translations/README.md`.

Dependency locks identify the local Python environment. Product runtime pins
identify distributed executable versions. Neither is a publication adoption lock.
