---
id: webapp-source.run-maintainer-validation
severity: mandatory
overridable: true
order: 1030
---
# Run the Webapp template maintainer validation baseline

Use the isolated Python and pip bootstrap procedure documented in `README.md` before executing repository validators.

For changes that can affect Webapp contracts or validation, run both supported entry points for the applicable validators and run the standard-library test suite. The complete retained baseline includes:

```sh
python scripts/validate_contracts.py
python -m scripts.validate_contracts
python scripts/validate_contract_evolution.py
python -m scripts.validate_contract_evolution
python scripts/validate_implementation_evidence.py
python -m scripts.validate_implementation_evidence
python scripts/validate_release_evidence.py
python -m scripts.validate_release_evidence
python scripts/validate_release_bundle.py
python -m scripts.validate_release_bundle
python -m unittest discover -s tests -v
```

When validating product-mode release evidence or bundles, supply the exact immutable candidate revision required by the artifact contract. Do not substitute policy-toolchain validation for these repository-owned validators.
