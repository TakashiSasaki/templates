# Generated-repository conformance

The Webapp template must prove that its contracts and validation toolchain remain usable after a repository is generated and product responsibility replaces template responsibility. This document defines the clean-room conformance model exercised by `tests/test_generated_repository_conformance.py`.

The model is framework-neutral. It does not select a product framework, package manager, backend, authentication provider, browser automation library, deployment platform, or production runtime. Its generated product is a deterministic fixture used only to prove that the template can be operationalized coherently.

## Trust and responsibility boundary

The source repository remains a template:

- `contracts/implementation-evidence.json` remains in `mode: template`;
- source contracts remain example declarations;
- no product implementation directory or product release gate is added to the template root; and
- the source checkout is never modified while a conformance fixture is running.

Each test creates a new temporary repository tree, excludes source-control and local-environment residue, and changes only that copy. The generated copy owns its product declarations, implementation locators, proof results, commands, and release gate. Assertions after fixture disposal verify that the source evidence document is still in template mode and that no product directory leaked into the source tree.

## Fixture materialization

The clean-room fixture performs the following deterministic transition:

1. copy the complete template tree to a temporary repository root while excluding `.git`, `.venv`, Python caches, and test caches;
2. replace or explicitly settle the example surface, route, UI-state, and viewport values as declarations for the fixture product `Conformance Workbench`;
3. change the copied implementation-evidence document to `mode: product`;
4. retain the complete target set derived from surfaces, routes, UI states, viewports, input capabilities, and registered post-version-1 transitions;
5. assign every target a verified repository-local implementation locator;
6. assign every target one verified positive proof and one verified negative proof;
7. bind every proof to the authoritative command ID `generated-product-proof`;
8. select the release gate `generated-product-release` for every record; and
9. make that gate execute the proof command used by every record.

The fixture materializes its implementation and proof locations in `product/conformance-targets.json`. These locations are deliberately simple repository-local JSON pointers. They prove locator integrity and responsibility transfer without implying a framework component model.

## Reviewed proof command

The fixture registers one authoritative command:

```text
python product/prove_conformance.py
```

The test harness does not parse or dispatch the command string. It directly invokes the known fixture script with the current test interpreter and a fixed argument vector. The script is generated from reviewed test code, reads only repository-local JSON files, performs no network or deployment action, and verifies all positive and negative target results.

This is a narrow conformance mechanism, not a general command executor. Product repositories remain responsible for executing their own reviewed commands in CI with the runtime and isolation appropriate to the selected toolchain.

## End-to-end validation

From the generated repository root, the positive fixture executes:

1. the reviewed product proof command;
2. `scripts/validate_contracts.py`;
3. `python -m scripts.validate_contracts`;
4. `scripts/validate_contract_evolution.py`;
5. `python -m scripts.validate_contract_evolution`;
6. `scripts/validate_implementation_evidence.py`; and
7. `python -m scripts.validate_implementation_evidence`.

The product proof checks 52 outcomes: positive and negative evidence for each of the 26 current targets. The six validator forms must all succeed against the same copied repository tree.

## Negative conformance coverage

Deliberately broken generated copies must fail with stable diagnostics for:

- template-mode residue after product claims have been materialized;
- a missing evidence target;
- an unverified implementation boundary;
- an unknown proof command;
- an unused command;
- an unused release gate;
- a proof command omitted from the selected release gate; and
- a false reviewed positive or negative proof result.

The first seven cases exercise the shipped implementation-evidence validator against a generated repository. The final case exercises the reviewed product proof script. Together they distinguish contract-reference closure from semantic proof execution.

## Versioning rule

The conformance fixture does not change an accepted contract document structure or semantic obligation. It therefore does not add a contract family, increment a domain schema version, change the manifest bootstrap version, or register a migration. A future change to accepted product evidence structure or required product semantics must follow the normal contract-evolution rules instead of being hidden in this fixture.

## Non-goals

The fixture does not prove that a real application framework renders a page, that a real authorization provider rejects access, or that a deployment platform releases safely. Those are product-owned proofs. The fixture proves that a generated repository can replace template examples with explicit product declarations, close every implementation-evidence reference, execute a reviewed product proof, and pass the complete retained validator surface without relying on template-only state.
