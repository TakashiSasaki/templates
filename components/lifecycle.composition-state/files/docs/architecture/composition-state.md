# Composition state lifecycle

`lifecycle.composition-state` makes a materialized consumer repository independently verifiable without access to the `composition` source checkout.

The composer owns `.template-composition/lock.json`; it is reserved metadata and is never a component material. This lifecycle component supplies the lock schema, a stdlib-only state validator, a managed validation registry, and a selected-component-aware validation runner under `.template-composition/`.

## State validation

`.template-composition/validate_composition.py` checks lock structure, component/file ownership, path portability, symlink boundaries, and material presence. `managed` and `generated` files must still match the SHA-256 recorded by the lock. `seed` files must remain present but may differ after initial materialization because ownership has transferred to the consumer.

Policy-managed metadata is outside Composition ownership. The consumer lock must not claim `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`, including portable case variants. The state validator checks that negative ownership boundary without parsing or validating Policy state itself; unrelated Policy files remain ordinary extra repository content from Composition's perspective.

The state validator does not attempt to re-resolve component dependencies or verify descriptor bytes against a source revision. Those source-aware checks belong to the composer. Its contract is consumer-time integrity of the resolved state already recorded by the lock.

## Selected-component validation

`.template-composition/validate.py` is the canonical self-contained consumer validation entrypoint. It runs state validation first with the invoking CPython and only trusts the lock and validation registry after that integrity check succeeds. It then derives the active validator set from `resolved_components` in `.template-composition/lock.json`.

`.template-composition/validation-registry.json` maps known component IDs to fixed Python validator entrypoints and fixed argument vectors. The registry itself is Composition-managed and digest-bound by the lock. Before dispatch, the runner also requires every selected validator entrypoint to be declared by the lock as a `managed` material owned by the same selected component. A validator file merely existing in the repository is never enough to activate it.

The registry also carries the exact Python distribution set required by selected validators. Those requirements are provider-tested to match the reviewed `requirements-runtime.lock`; the materialized repository therefore contains enough information to construct its validator environment without access to the Composition checkout and without requiring the consumer to create a validation virtual environment manually.

### Isolated validation runtime

After state and registry integrity have been established, the runner derives a validation-runtime identity from the exact requirement-set SHA-256, CPython major/minor version, and platform/machine. It reuses only a cache entry whose marker, copied requirement lock, interpreter identity, installed non-bootstrap distribution set, and `pip check` all match that identity. Invalid cache entries are misses rather than trusted state.

On a cold cache, the runner creates a temporary virtual environment, installs every exact requirement with dependency resolution and pip caching disabled, verifies the resulting distribution set, and atomically promotes the completed runtime into the cache. The consumer repository itself is not modified by this process. On a valid warm cache, no package acquisition is required.

The default cache is the platform cache location under `composition/validation-v1`. Controlled or read-only environments may set `COMPOSITION_VALIDATION_CACHE=/path/to/writable/cache`; that one override is sufficient for the materialized validation runtime. User `PIP_*` and `PYTHON*` environment settings are not inherited into the validation runtime. If the cache cannot provide the writes and atomic rename required for safe construction, validation fails with an actionable `COMPOSITION_VALIDATION_CACHE` diagnostic rather than a raw permission traceback.

The selected validators themselves run with the isolated cached interpreter. Dispatch still invokes Python directly without shell parsing, so the same contract applies on Windows and POSIX systems. Human-readable output is the default; `--format json` emits deterministic machine-readable check results.

Release evidence and release bundles have an additional boundary. Template-mode documents can be validated during ordinary repository validation. Product-mode evidence is bound to an exact product revision and therefore remains deferred to the product-owned exact-candidate release operation; ordinary validation reports that deferral explicitly instead of weakening or pretending to satisfy the revision-bound validator.
