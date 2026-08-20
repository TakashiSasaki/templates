# Composition state lifecycle

`lifecycle.composition-state` makes a materialized consumer repository independently verifiable without access to the `composition` source checkout.

The composer owns `.template-composition/lock.json`; it is reserved metadata and is never a component material. This lifecycle component instead supplies the lock schema and a stdlib-only consumer validator under `.template-composition/`.

The validator checks lock structure, component/file ownership, path portability, symlink boundaries, and material presence. `managed` and `generated` files must still match the SHA-256 recorded by the lock. `seed` files must remain present but may differ after initial materialization because ownership has transferred to the consumer.

Policy-managed metadata is outside Composition ownership. The consumer lock must not claim `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`, including portable case variants. The validator checks that negative ownership boundary without parsing or validating Policy state itself; unrelated Policy files remain ordinary extra repository content from Composition's perspective.

The consumer validator does not attempt to re-resolve component dependencies or verify descriptor bytes against a source revision. Those source-aware checks belong to the composer. Its contract is consumer-time integrity of the resolved state already recorded in the lock.
