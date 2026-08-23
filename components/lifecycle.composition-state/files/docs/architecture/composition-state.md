# Composition state lifecycle

`lifecycle.composition-state` makes a materialized consumer repository independently verifiable without access to the `composition` source checkout.

The composer owns `.template-composition/lock.json`; it is reserved metadata and is never a component material. This lifecycle component supplies the lock schema, a stdlib-only state validator, a managed validation registry, and a selected-component-aware validation runner under `.template-composition/`.

## State validation

`.template-composition/validate_composition.py` checks lock structure, component/file ownership, path portability, symlink boundaries, and material presence. `managed` and `generated` files must still match the SHA-256 recorded by the lock. `seed` files must remain present but may differ after initial materialization because ownership has transferred to the consumer.

Policy-managed metadata is outside Composition ownership. The consumer lock must not claim `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`, including portable case variants. The state validator checks that negative ownership boundary without parsing or validating Policy state itself; unrelated Policy files remain ordinary extra repository content from Composition's perspective.

The state validator does not attempt to re-resolve component dependencies or verify descriptor bytes against a source revision. Those source-aware checks belong to the composer. Its contract is consumer-time integrity of the resolved state already recorded in the lock.

## Selected-component validation

`.template-composition/validate.py` is the canonical self-contained consumer validation entrypoint. It runs state validation first and only trusts the lock and validation registry after that integrity check succeeds. It then derives the active validator set from `resolved_components` in `.template-composition/lock.json`.

`.template-composition/validation-registry.json` maps known component IDs to fixed Python validator entrypoints and fixed argument vectors. The registry itself is Composition-managed and digest-bound by the lock. Before dispatch, the runner also requires every selected validator entrypoint to be declared by the lock as a `managed` material owned by the same selected component. A validator file merely existing in the repository is never enough to activate it.

The runner invokes Python directly without shell parsing, so the same dispatch contract applies on Windows and POSIX systems. Human-readable output is the default; `--format json` emits deterministic machine-readable check results.

Release evidence and release bundles have an additional boundary. Template-mode documents can be validated during ordinary repository validation. Product-mode evidence is bound to an exact product revision and therefore remains deferred to the product-owned exact-candidate release operation; ordinary validation reports that deferral explicitly instead of weakening or pretending to satisfy the revision-bound validator.
