# Validation toolchain

Validation is layered by authority.

1. `scripts/validate_contracts.py` validates all registered JSON documents/schemas and Webapp surface/route/state/viewport invariants.
2. `validate_contract_evolution.py` validates the generated registry, version histories, and migration inventory.
3. `validate_implementation_evidence.py` validates artifact-neutral evidence mechanics.
4. `scripts/validate_webapp_evidence.py` adds Webapp-specific target coverage in product mode.
5. release-evidence and release-bundle validators close exact-revision execution and handoff semantics.

The supplied managed GitHub Actions workflow runs layers 1–4 for both template and product repositories. While the release documents remain in template mode, it also runs their lifecycle validators and therefore preserves the complete template-mode validation sequence.

Product-mode release evidence and release bundles are different: their semantics are intentionally bound to one exact product candidate revision. The managed repository-validation workflow does not infer that revision from a GitHub event SHA. A product-owned release operation must run the release-evidence and release-bundle validators with `--expected-revision <candidate-sha>` after selecting the exact candidate revision.

The managed validation dependency lock is under `.template-composition/` so it does not select a product runtime or package manager.
