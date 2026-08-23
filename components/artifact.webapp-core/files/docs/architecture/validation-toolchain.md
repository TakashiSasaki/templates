# Validation toolchain

Validation is layered by authority and dispatched from the resolved Composition component set.

1. `.template-composition/validate_composition.py` validates the Composition lock and managed/generated material integrity.
2. `scripts/validate_contracts.py` validates all registered JSON documents/schemas and Webapp surface/route/state/viewport invariants when `artifact.webapp-core` is selected.
3. `validate_contract_evolution.py` validates the generated registry, version histories, and migration inventory when `lifecycle.contract-evolution` is selected.
4. `validate_implementation_evidence.py` validates artifact-neutral evidence mechanics when `lifecycle.implementation-evidence` is selected.
5. `scripts/validate_webapp_evidence.py` adds Webapp-specific target coverage when `artifact.webapp-core` is selected.
6. release-execution, release-evidence, and release-bundle validation is selected only when those lifecycle components are present in the lock.

`.template-composition/validate.py` is the self-contained consumer entrypoint for these layers. It runs Composition-state validation first, reads `resolved_components` from the validated lock, and dispatches only validators registered for those selected components. The managed validation registry and every invoked validator entrypoint are themselves lock-bound Composition materials. Merely finding a release contract or validator file in the repository does not activate release validation.

Before switching implementation evidence to product mode, `python scripts/scaffold_webapp_evidence.py` emits a deterministic non-canonical worklist for every current Webapp evidence target. It writes only to standard output and does not modify `contracts/implementation-evidence.json`. This separation is intentional: template mode requires an empty canonical evidence document, while product mode requires fully verified records. Fill the generated record skeletons with concrete implementation locators, proof metadata, commands, and release gates before placing them in the canonical product evidence document.

The scaffold and `scripts/validate_webapp_evidence.py` share `scripts/webapp_evidence_targets.py`, so target derivation has one Webapp-specific implementation rather than duplicated generator and validator rules.

The supplied managed GitHub Actions workflow installs the locked validation dependencies and then invokes `python .template-composition/validate.py .`. This keeps CI on the same selected-component-aware path used by consumer validation instead of maintaining a second handwritten validator sequence in workflow YAML.

Product-mode release evidence and release bundles are different: their semantics are intentionally bound to one exact product candidate revision. Ordinary repository validation reports those checks as deferred rather than guessing a revision from file existence or a GitHub event SHA. A product-owned release operation must run the release-evidence and release-bundle validators with `--expected-revision <candidate-sha>` after selecting the exact candidate revision.

The managed validation dependency lock is under `.template-composition/` so it does not select a product runtime or package manager.
