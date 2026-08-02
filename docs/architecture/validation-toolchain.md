# Validation toolchain boundary

The Webapp branch carries a small Python toolchain only to validate the repository-local contracts, schemas, and regression tests. This toolchain is part of template maintenance; it is not a framework, product runtime, package-manager choice, deployment target, or coding-agent policy for repositories generated from the template.

## Reproducible validation baseline

The branch-maintainer CI baseline is:

- Ubuntu 24.04;
- CPython 3.12.13;
- immutable commit pins for the checkout and Python-setup actions;
- a fresh virtual environment without system site packages;
- arbitrary exact direct dependencies in `requirements-dev.txt`;
- the complete arbitrary exact dependency graph in `requirements-dev.lock`.

Dependency entries use the requirement operator `===`, not PEP 440 version matching with `==`. A public-version specifier such as `name==1.2.3` can also match a candidate carrying an unrequested local label such as `1.2.3+corp`; `name===1.2.3` requires the candidate version string to match exactly. A local build may be selected only when its full local version is intentionally recorded in the reviewed input and lock.

CI creates a fresh `.venv`, installs only the entries enumerated in `requirements-dev.lock` with dependency resolution disabled, then uses that virtual environment for `pip check`, both public validator entry points, and the complete unit-test suite. The clean environment is required because `pip check` validates the currently installed graph; a dependency already present in the setup interpreter could otherwise conceal an entry omitted from the lock. Disabling dependency resolution is also required so an omitted transitive or conditional dependency is not silently retrieved from the package index.

The lock provides exact version-string reproducibility for the selected index configuration. It does not claim byte-for-byte artifact reproducibility or index-origin reproducibility because wheel and source-distribution hashes and source URLs are not recorded. Adding hash enforcement or repository-origin enforcement is a separate trust-boundary change.

## Local verification

Create an isolated environment and install exactly the locked graph:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check --no-deps --requirement requirements-dev.lock
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

1. changes the arbitrary exact direct pin in `requirements-dev.txt` when required;
2. resolves and records the complete arbitrary-exact graph for CPython 3.12.13 on Ubuntu 24.04 in `requirements-dev.lock`;
3. updates the reproducibility regression expectations;
4. creates a fresh virtual environment without system site packages, installs the lock with dependency resolution disabled, and runs `pip check` there;
5. runs the standalone validator, module validator, and complete unit-test suite from that environment;
6. records any baseline, compatibility, or diagnostic changes in the pull request.

Do not update the lock incidentally with contract, schema, documentation, or fixture work.

## Product-repository boundary

A repository generated from this template still selects its own implementation runtime, framework, package manager, build commands, browser matrix, and deployment mechanism. It may retain this validator toolchain, replace it with an equivalent verified integration, or isolate it from the product runtime. Such a change must preserve the contract-validation semantics and public diagnostics relied on by that repository.
