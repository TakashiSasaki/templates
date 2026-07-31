# Web application repository template

This orphan branch is the development source for a framework-neutral web-application repository template. Its history is intentionally unrelated to the other branches in `TakashiSasaki/templates`.

The template turns applicable guidance from `TakashiSasaki/agent-policy` into repository structure and executable contracts. The first foundation covers application surfaces, routes, user-visible states, supported viewports, JSON Schemas, validation, tests, and CI. It does not yet choose an application framework, package manager, deployment target, authentication provider, or backend architecture.

## Foundation commands

Validate all machine-readable contracts:

```sh
python scripts/validate_contracts.py
```

Run the standard-library test suite:

```sh
python -m unittest discover -s tests -v
```

The validator requires the development dependency declared in `requirements-dev.txt`.

## Template-development rule

Changes for this template branch must be based on `webapp`, not on `main` or `site`. The histories are unrelated and must not be merged merely to share files.

See `TEMPLATE.md` for scope and customization boundaries, and `docs/provenance/agent-policy-mapping.md` for the relationship to `agent-policy`.
