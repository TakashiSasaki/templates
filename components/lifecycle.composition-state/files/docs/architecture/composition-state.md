# Composition state lifecycle

`lifecycle.composition-state` makes a materialized consumer repository independently verifiable without access to the `composition` source checkout.

The composer owns `.template-composition/lock.json`; it is reserved metadata and is never a component material. This lifecycle component supplies the lock schema, a stdlib-only state validator, a managed validation registry, a selected-component-aware validation runner, and the provider-owned executable action dispatcher under `.template-composition/`.

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

## Provider-owned executable action dispatch

`.template-composition/run_action.py` is the provider-owned boundary between public machine actions and internal validator/writer invocation details. Public action registries may expose a stable dispatcher argv without forcing a consumer to discover internal Python module paths, import behavior, validator flags, checkpoint phase options, or provider working-directory conventions. The dispatcher invokes provider code with its own `sys.executable`, passes fixed internal argv, and sets the materialized repository root as the provider subprocess working directory.

The outer public argv remains an argument vector, never a shell string. `{python}` is a caller input whose exact meaning is one executable path for a CPython interpreter satisfying Composition's advertised runtime requirements. It occupies one token only. Public action schemas fix the complete argv with JSON Schema `const`; interpreter flags are therefore part of the provider contract by their explicit absence. A consumer resolves only declared caller inputs and provider bindings, then executes from the materialized repository root without adding, deleting, reordering, or augmenting tokens. In particular, a consumer must not inject `-I` or another Python option merely because the dispatcher itself is a Python file.

Structured action output is provider-owned as well. Release-readiness actions advertise their result schema in the registry and emit the same path as `$schema`; checkpoint actions emit a mandatory `$schema` referring to their managed result schema. A provider execution failure is distinct from a successful semantic action result such as release `not-ready`.

## Lifecycle next-action projection

The self-contained validation entrypoint emits a nested `lifecycle` projection in its `--format json` result. The projection is derived from the existing Composition validation checks and the consumer-owned `contracts/implementation-evidence.json` mode; it is not a second lifecycle authority.

- `lifecycle_stage: scaffold-valid` means Composition is valid, but `template` or `planning` evidence is not an implemented-product milestone.
- `lifecycle_stage: implemented-product` requires `product` evidence mode and successful ordinary validation.
- `release_readiness: not-evaluated` means the ordinary validator has not run the revision-bound release-readiness operation.
- `release_readiness: not-ready` is emitted when a selected validator is deferred; deferred browser proof must never be presented as release-ready.
- `next_actions` is a deterministic ordered list. When `lifecycle.lifecycle-checkpoints` is selected, the projection respects its already-validated checkpoint ledger instead of skipping across that authority boundary.

With lifecycle checkpoints selected, planning evidence without a current planning checkpoint exposes only `create-planning-checkpoint`; product implementation is not an allowed next action until that checkpoint exists. This applies both to the initial implementation and to a later specification change whose latest checkpoint is still the previous product milestone. After product evidence validates, a missing product checkpoint exposes only `create-product-checkpoint`; release-readiness checking is not offered until that checkpoint exists. If the checkpoint component is not selected, the pre-existing non-checkpoint lifecycle projection is preserved.

When one of those checkpoint transitions is the immediate next action, schema version 2 may also include `next_action_command`. That object contains the canonical argument vector from the checkpoint component's managed `.template-composition/lifecycle-checkpoint-actions.json` registry. The projection does not reconstruct checkpoint writer CLI syntax. It resolves only provider-owned bindings such as the exact latest planning checkpoint ID; caller-owned placeholders such as `{python}` and `{checkpoint_id}` remain explicit in `caller_inputs`. The projected argv therefore still carries the exact dispatcher tokens declared by the provider registry. A malformed or unreadable selected action registry fails closed to `composition-invalid` with `checkpoint-command-registry-invalid`.

For implemented product evidence, `check-release-readiness` is also executable without prose lookup. When `lifecycle.implementation-evidence` is selected, the projection reads its managed `.template-composition/implementation-evidence-actions.json` registry, preserves caller inputs such as `{python}`, and projects the provider-declared result schema alongside argv. The projection does not own or reconstruct the internal release-readiness validator command. A missing or malformed applicable registry fails closed with `release-readiness-command-registry-invalid`; consumers without that provider do not receive its command.

The projection reads only the latest phase and, when required to bind the product command, the latest checkpoint ID from the checkpoint ledger after selected-component validation has succeeded. Checkpoint ordering, hashes, snapshots, command definitions, and historical proof semantics remain owned by `lifecycle.lifecycle-checkpoints`; this projection does not reimplement them. An unexpected checkpoint ledger shape fails closed to `composition-invalid` rather than inventing a lifecycle transition.

The projection schema is materialized at `.template-composition/lifecycle-next-actions.schema.json` and is validated by Composition tests. Existing validator checks and their fail-closed behavior remain authoritative.
