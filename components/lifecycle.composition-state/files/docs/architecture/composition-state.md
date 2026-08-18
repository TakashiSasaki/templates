# Composition state lifecycle

`lifecycle.composition-state` makes a materialized consumer repository independently verifiable without access to the `composition` source checkout.

The composer owns `.template-composition/lock.json`; it is reserved metadata and is never a component material. This lifecycle component instead supplies the lock schema and a stdlib-only consumer validator under `.template-composition/`.

The validator checks lock structure, component/file ownership, path portability, symlink boundaries, and material presence. `managed` and `generated` files must still match the SHA-256 recorded by the lock. `seed` files must remain present but may differ after initial materialization because ownership has transferred to the consumer.

The consumer validator does not attempt to re-resolve component dependencies or verify descriptor bytes against a source revision. Those source-aware checks belong to the composer. Its contract is consumer-time integrity of the resolved state already recorded in the lock.
