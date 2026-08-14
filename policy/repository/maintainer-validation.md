---
id: webapp-source.run-maintainer-validation
severity: mandatory
overridable: true
order: 1030
---
# Run the Webapp template maintainer validation baseline

Use the isolated Python and pip bootstrap procedure documented in `README.md` before executing repository validators.

For changes that can affect the distribution boundary or repository-owned translation metadata, run both source-only distribution and translation validator entry points from the branch root. For changes that can affect Webapp contracts or validation, run both supported entry points for each applicable canonical validator from `template/`, then run the source-maintainer standard-library test suite. The complete retained baseline includes:

```sh
python scripts/validate_distribution.py
python -m scripts.validate_distribution
python scripts/validate_translations.py
python -m scripts.validate_translations
(cd template && ../.venv/bin/python scripts/validate_contracts.py)
(cd template && ../.venv/bin/python -m scripts.validate_contracts)
(cd template && ../.venv/bin/python scripts/validate_contract_evolution.py)
(cd template && ../.venv/bin/python -m scripts.validate_contract_evolution)
(cd template && ../.venv/bin/python scripts/validate_implementation_evidence.py)
(cd template && ../.venv/bin/python -m scripts.validate_implementation_evidence)
(cd template && ../.venv/bin/python scripts/validate_release_evidence.py)
(cd template && ../.venv/bin/python -m scripts.validate_release_evidence)
(cd template && ../.venv/bin/python scripts/validate_release_bundle.py)
(cd template && ../.venv/bin/python -m scripts.validate_release_bundle)
.venv/bin/python -m unittest discover -s tests -v
```

When validating product-mode release evidence or bundles, supply the exact immutable candidate revision required by the artifact contract. Do not substitute policy-toolchain validation for these repository-owned validators.
