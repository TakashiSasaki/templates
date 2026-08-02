# Validation toolchain boundary

The Webapp branch carries a small Python toolchain only to validate the repository-local contracts, schemas, and regression tests. This toolchain is part of template maintenance; it is not a framework, product runtime, package-manager choice, deployment target, or coding-agent policy for repositories generated from the template.

## Reproducible validation baseline

The branch-maintainer CI baseline is:

- Ubuntu 24.04;
- CPython 3.12.13;
- immutable commit pins for the checkout and Python-setup actions;
- exact direct dependencies in `requirements-dev.txt`;
- the complete exact dependency graph in `requirements-dev.lock`.

CI installs only `requirements-dev.lock`, runs `python -m pip check`, exercises both public validator entry points, and then runs the complete unit-test suite.

The lock provides version-level reproducibility. It does not claim byte-for-byte artifact reproducibility because wheel and source-distribution hashes are not recorded. Adding hash enforcement is a separate trust-boundary change.

## Local verification

Create an isolated environment and install the locked graph:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check --requirement requirements-dev.lock
python -m pip check
```

Run both supported validator forms and the tests:

```sh
python scripts/validate_contracts.py
python -m scripts.validate_contracts
python -m unittest discover -s tests -v
```

A different local Python may be useful for compatibility investigation, but CI is authoritative for the selected baseline.

## Dependency update procedure

A dependency update must be an intentional reviewed change that:

1. changes the exact direct pin in `requirements-dev.txt` when required;
2. resolves and records the complete graph for CPython 3.12.13 on Ubuntu 24.04 in `requirements-dev.lock`;
3. updates the reproducibility regression expectations;
4. verifies installation and `pip check` in a fresh environment;
5. runs the standalone validator, module validator, and complete unit-test suite;
6. records any baseline, compatibility, or diagnostic changes in the pull request.

Do not update the lock incidentally with contract, schema, documentation, or fixture work.

## Product-repository boundary

A repository generated from this template still selects its own implementation runtime, framework, package manager, build commands, browser matrix, and deployment mechanism. It may retain this validator toolchain, replace it with an equivalent verified integration, or isolate it from the product runtime. Such a change must preserve the contract-validation semantics and public diagnostics relied on by that repository.
