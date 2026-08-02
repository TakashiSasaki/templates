# Web application repository template

This orphan branch is the development source for a framework-neutral web-application repository template. Its history is intentionally unrelated to the other branches in `TakashiSasaki/templates`.

The template provides repository-level design contracts for browser-facing web applications. The current foundation covers application surfaces, routes, user-visible states, supported viewports, a closed contract manifest, JSON Schemas, validation, tests, and CI. It does not choose an application framework, package manager, deployment target, authentication provider, backend architecture, or coding-agent operating policy.

## Foundation commands

Validate the complete machine-readable contract set:

```sh
python scripts/validate_contracts.py
```

Run the standard-library test suite:

```sh
python -m unittest discover -s tests -v
```

The validator requires the development dependency declared in `requirements-dev.txt`.

`contracts/manifest.json` is the inventory source of truth. Every domain contract and schema must be registered there; unregistered, missing, duplicated, unsafe, or version-mismatched entries fail validation.

## Template-development rule

Changes for this template branch must be based on `webapp`, not on `main` or `site`. The histories are unrelated and must not be merged merely to share files.

See `TEMPLATE.md` for scope and customization boundaries, `docs/architecture/responsibility-boundaries.md` for ownership of template, product, and operational concerns, and `docs/architecture/contract-completeness.md` for the contract inventory and extension criteria.
