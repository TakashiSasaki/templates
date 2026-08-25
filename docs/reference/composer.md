# Composer reference

This reference describes the consumer-facing contract of `scripts/compose.py`. For task-oriented instructions, start with [Using Composition](../consumer-guide.md). For design rationale, see [Composer MVP](../architecture/composer-mvp.md) and the [Composition model](../architecture/composition-model.md).

Normal consumers reach this contract through the installed `skills/composition/` runner. The runner owns immutable source acquisition, isolated runtime construction, and target injection; it does not redefine lifecycle modes, plans, lock/transaction semantics, ownership, diagnostics, or Composer exit behavior. In direct source-checkout examples below, `--target /repo` is explicit. Through the runner, the equivalent target is supplied once as `--repository /repo`, and a second `--target` is rejected.

## Public lifecycle

The public lifecycle is:

```text
inspect -> plan -> apply -> validate
```

`inspect` and `validate` are mode-neutral. `plan` and `apply` use one of three modes: `initial`, `update`, or `upgrade`.

## Command and option matrix

| Command | Mode | `--target` | `--config` | `--format` | Purpose |
| --- | --- | --- | --- | --- | --- |
| `inspect` | none | required | not accepted | `json` (default) / `human` | classify target state without mutation |
| `plan` | `initial` or omitted | required | required | `json` (default) / `human` | plan first materialization |
| `apply` | `initial` or omitted | required | required | `json` (default) / `human` | perform first materialization |
| `plan` | `update` | required | forbidden | `json` (default) / `human` | preserve lock-v2 intent and reconcile to current descendant source |
| `apply` | `update` | required | forbidden | `json` (default) / `human` | apply or recover managed update |
| `plan` | `upgrade` | required | required | `json` (default) / `human` | plan explicit intent/compatibility-boundary change |
| `apply` | `upgrade` | required | required for a new upgrade; forbidden during recovery | `json` (default) / `human` | start or recover explicit upgrade |
| `validate` | none | required | not accepted | `json` (default) / `human` | validate current consumer state |

Initial mode is the default. These forms are equivalent:

```sh
python scripts/compose.py plan --config composition.json --target /repo
python scripts/compose.py plan --mode initial --config composition.json --target /repo
```

The dispatcher accepts `--mode` and `--format` before or after the command, but examples and documentation use command-first form.

## Output formats

`--format json` is the default public output contract. Omitting `--format` is equivalent to explicit `--format json`: existing invocations keep the same machine-readable JSON field shapes, structured diagnostic codes, and lifecycle exit behavior.

`--format human` is an opt-in presentation for a person operating the Composer directly in a terminal. It renders concise state, conflict/action summaries, ownership guidance, remediation, and next actions from the same structured lifecycle payload used by JSON output. It does not invoke a different planner, apply path, validator, state transition, or remediation semantics.

Human output is not a parsing or automation contract. Automation must continue to use the default JSON output or explicit `--format json` and consume structured fields and diagnostic `code` values rather than matching human prose. Exit status semantics are format-independent: the same lifecycle result has the same exit code whether rendered as JSON or human text.

Examples:

```sh
python scripts/compose.py inspect --target /repo --format human
python scripts/compose.py plan --config composition.json --target /repo --format human
```

Through the installed runner, `--format` is forwarded as a Composer option:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /repo \
  inspect --format human
```

## CLI discovery

The public entrypoint exposes the complete lifecycle and mode/config rules without requiring consumers to know which internal adapter handles a command:

```sh
python scripts/compose.py --help
```

The top-level help lists `inspect -> plan -> apply -> validate`, the `initial` / `update` / `upgrade` modes, the `--config` requirements for each mode, interrupted-upgrade recovery behavior, output-format selection, and representative commands. This help path is read-only and does not load Composition source state or inspect a consumer repository.

Internal modules such as `composer_update_plan.py`, `composer_apply.py`, `composer_managed.py`, and `composer_transaction.py` are implementation layers, not alternate public entrypoints. Consumer automation and documentation should invoke `scripts/compose.py` directly only when operating from an exact reviewed source checkout; normal installed-skill operation delegates to that same entrypoint.

## Runner binding

The installed runner syntax is:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /repo \
  COMMAND [COMPOSER OPTIONS]
```

The runner selects only a full lowercase 40-character source revision in `TakashiSasaki/templates`. Its stable default comes from `skills/composition/runtime-manifest.json`; an explicit `--revision <full-sha>` may override that default. When `.template-composition/transaction.json` exists, its exact source revision is authoritative for recovery and overrides the stable default. A conflicting explicit revision is rejected.

After selecting the revision, the runner reuses or builds two independently validated persistent cache layers. The source cache is keyed by exact revision and must remain detached at that SHA, point at the canonical remote, be byte-clean with LF-preserving checkout settings, and retain traversable ancestor history. The runtime cache is keyed by repository, revision, runtime-lock SHA-256, CPython major/minor, and platform/machine; a hit is accepted only after marker/digest/identity checks, `pip check`, and the selected source revision's runtime verifier. On a miss, the runner fetches the exact source or builds the exact `requirements-runtime.lock` environment with dependency resolution disabled and atomically installs the new cache entry. A valid cache hit requires no network acquisition. `COMPOSITION_RUNTIME_CACHE` may override the platform-default cache root for controlled environments. The runner adds `--target /repo` itself and refuses any forwarded `--target` option. Cache layout and reuse are performance details and do not redefine Composer semantics.

## Source checkout requirements

The Composer runs from the Composition source checkout. Source authorities consumed by composition must be regular Git-tracked files under one exact clean revision.

For managed `update` and `upgrade`:

- the old revision recorded in the consumer lock must be available in local Composition Git history;
- the target source revision must equal or descend from the old revision;
- recovery requires the exact target revision recorded in `.template-composition/transaction.json`.

The canonical source identity is the Composition authority in `TakashiSasaki/templates`. The installed runner acquires or reuses a detached exact-SHA checkout with the selected revision's ancestor history and validates that history before reuse, so these checks remain Composer-owned rather than being weakened by the wrapper.

## `inspect`

Syntax:

```sh
python scripts/compose.py inspect --target /repo
```

Possible `state` values are:

| State | Meaning |
| --- | --- |
| `absent` | target path does not exist |
| `unmanaged` | target exists without a Composition lock |
| `managed-valid` | lock and materialized state validate |
| `managed-invalid` | Composition metadata exists but consumer validation fails |
| `managed-interrupted` | `.template-composition/transaction.json` exists and recovery is required |
| `invalid` | target root itself is invalid, for example a symbolic link |

`inspect` treats transaction-marker presence as sufficient to classify interrupted managed state. It does not trust or branch on transaction contents before recovery. The runner separately validates only enough transaction metadata to choose the exact recovery source revision before launching the Composer; the Composer remains authoritative for recovery-state validation.

## Consumer configuration

Configuration schema version 1 has four required fields:

```json
{
  "schema_version": 1,
  "recipe": "skill",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

`recipe` selects a production recipe. `components.include` and `components.exclude` may name exposed `capability.*` or `lifecycle.*` components. Include/exclude sets must be disjoint; required components cannot be excluded; selected dependency closure cannot contain an excluded component.

`parameters` is an object keyed by selected `artifact.*`, `capability.*`, or `lifecycle.*` component IDs. The schema permits component-local object values. At this production revision, materialization does not consume parameter values and production components do not declare parameter-specific material behavior. Parameter objects are nevertheless normalized into lock-v2 intent, so changing them requires explicit `upgrade`.

## Lock schema v2

`.template-composition/lock.json` is Composer-owned resolved state. It records:

- exact source repository and revision;
- normalized intent: recipe, sorted include/exclude choices, and normalized parameters;
- exact recipe digest;
- digest of the most recently supplied configuration bytes;
- resolved component IDs, component versions, and descriptor digests;
- every active material destination, owner component, ownership mode, and materialized digest.

Consumers may read the lock to understand state and ownership, but should not edit it manually.

## Initial planning

Syntax:

```sh
python scripts/compose.py plan --config composition.json --target /repo
```

The initial plan payload has `schema_version: 2` and `operation: "initial"`. Important fields include `source`, `intent`, `resolved_components`, `actions`, `conflicts`, and `lock_preview`.

Initial action values are:

| Action | Meaning |
| --- | --- |
| `create` | destination is absent and may be created |
| `adopt-identical` | an existing regular file already has exactly the desired bytes |

Initial conflicts are reported separately. Different existing bytes, portable case collisions, file/directory collisions, symbolic links, unsafe paths, existing Composer-managed metadata, and invalid component/configuration resolution prevent apply.

Initial composition never overwrites different existing bytes.

## Managed update planning

Syntax:

```sh
python scripts/compose.py plan --mode update --target /repo
```

The managed update plan has `schema_version: 1` and `operation: "update"`. It reconstructs configuration from lock-v2 normalized intent; a new `--config` is rejected as `UPDATE_CONFIG_NOT_ALLOWED`.

The payload contains:

- `from_revision` / `to_revision`;
- unchanged normalized `intent`;
- recipe digest transition information;
- component `added`, `removed`, `changed`, and `unchanged` groups;
- file action buckets;
- structured top-level `conflicts`;
- `lock_preview`.

Managed file action buckets are:

| Bucket | Meaning |
| --- | --- |
| `create` | new active material may be created at an absent safe destination |
| `replace` | clean `managed` or `generated` material changes bytes and may be replaced |
| `remove` | clean `managed` or `generated` material leaves the active composition and may be deleted |
| `preserve` | `seed` remains consumer-owned and is left unchanged; removed seed also remains as an ordinary extra file |
| `unchanged` | active `managed`/`generated` material already has the desired digest |
| `conflict` | transition is unsafe or unsupported and apply must not mutate |

A component version change is a conflict in update and reports `COMPONENT_VERSION_UPGRADE_REQUIRED`.

## Explicit upgrade planning

Syntax:

```sh
python scripts/compose.py plan --mode upgrade --config composition.json --target /repo
```

Upgrade accepts explicit new intent. The plan includes `intent.from` and `intent.to`, configuration digest transition, recipe transition, component transition, the same managed file action buckets, conflicts, and a new lock preview.

Component version changes are accepted as explicit `component-version` compatibility boundaries during upgrade. Descriptor-byte change without a component-version change remains invalid and reports `COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION`.

File-owner and ownership-mode changes are not automatically migrated. Update may identify these as `*_UPGRADE_REQUIRED`; the public message explicitly warns that current upgrade still does not infer that migration. Explicit upgrade reports the corresponding `*_NOT_SUPPORTED` conflict rather than inferring a migration.

## Apply behavior

`apply` performs deterministic planning again before mutation. A conflicting plan returns without creating a managed transaction.

Initial apply creates only absent destinations, adopts only byte-identical existing files, writes the lock last, then performs consumer validation.

Managed update/upgrade writes `.template-composition/transaction.json` before the first managed-state mutation. Only `create`, `replace`, and `remove` become transaction actions. `preserve` and `unchanged` do not mutate files.

For `replace` and `remove`, current bytes must still match the old lock digest. Retry accepts an already-applied new state. Any third state reports a precondition error rather than being overwritten.

The new lock is installed after file actions, consumer state is validated while the transaction marker still exists, and the marker is removed last.

## Ownership modes

| Ownership | Authority after initial materialization | Update/upgrade behavior |
| --- | --- | --- |
| `managed` | Composition source material remains authoritative | may replace/remove only when current bytes equal old lock digest |
| `generated` | deterministic Composition generator remains authoritative | recomputed and may replace/remove only when current bytes equal old lock digest |
| `seed` | ownership transfers to the consumer | never overwritten or deleted by update/upgrade after first materialization |

A seed file that remains active keeps its original provenance digest in the next lock even if consumer bytes differ. A removed seed disappears from the new lock but remains in the repository as ordinary consumer-owned content.

## Recovery

A managed transaction is durable roll-forward state. `inspect` reports `managed-interrupted` while the marker exists.

Recovery requirements are:

1. use the exact Composition source revision recorded by `transaction.source.revision`;
2. rerun the matching apply mode recorded by `transaction.operation`;
3. do not edit or delete the marker manually;
4. for interrupted upgrade, omit `--config` because target intent and new lock are already recorded.

Examples:

```sh
python scripts/compose.py apply --mode update --target /repo
python scripts/compose.py apply --mode upgrade --target /repo
```

Through the installed runner, the equivalent commands omit source checkout management and `--target`; the runner reads the transaction's exact source revision and supplies the target from `--repository`.

A transaction for the other operation reports `RECOVERY_OPERATION_MISMATCH`. A different source checkout reports `RECOVERY_SOURCE_MISMATCH`.

## Consumer-facing managed lifecycle diagnostics

The following codes are especially relevant to normal consumer operation. The public `scripts/compose.py` entrypoint preserves the structured diagnostic `code` and adds remediation to known managed-lifecycle `message` fields at presentation time. The underlying planner/transaction code and fail-closed decisions are unchanged. Automation should key on `code` and structured fields rather than matching the prose of `message`.

| Code | Meaning | Consumer action |
| --- | --- | --- |
| `INITIAL_MODE_REQUIRES_UNMANAGED_TARGET` | initial mode found an existing Composition lock | use `update` to preserve intent or `upgrade` to change intent/boundary |
| `MANAGED_LOCK_REQUIRED` | update/upgrade was requested without managed state | run `inspect`; use initial mode only if the target is unmanaged and no lock exists |
| `UPDATE_CONFIG_NOT_ALLOWED` | `--config` was supplied to update | remove `--config`; use upgrade for intentional recipe/component/parameter/boundary changes |
| `UPGRADE_CONFIG_REQUIRED` | new upgrade planning/apply lacks explicit target intent | supply `--config`; only interrupted upgrade recovery omits it |
| `RECOVERY_CONFIG_NOT_ALLOWED` | `--config` was supplied while recovering upgrade | remove `--config`; rerun `apply --mode upgrade` at the exact recorded source revision |
| `RECOVERY_REQUIRED` | an unfinished managed transaction exists | recover the recorded operation at its exact source revision before planning another one; do not delete the marker |
| `RECOVERY_OPERATION_MISMATCH` | requested recovery mode differs from transaction operation | rerun `apply` with the operation recorded in the transaction |
| `RECOVERY_SOURCE_MISMATCH` | source checkout is not the exact revision recorded by the transaction | check out the recorded revision and retry the matching apply; upgrade recovery omits `--config` |
| `OLD_SOURCE_REVISION_UNAVAILABLE` | old lock revision is absent from local Composition history | make that revision available locally before retrying; do not bypass ancestry validation |
| `SOURCE_REVISION_NOT_DESCENDANT` | target Composition revision is not old revision or its descendant | use the locked revision or a descendant/equal source revision |
| `COMPONENT_VERSION_UPGRADE_REQUIRED` | update encounters a component version change | plan an explicit upgrade with desired intent and `--config` |
| `COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION` | descriptor bytes changed without version change | source-side invariant is broken; do not bypass it in the consumer |
| `LOCAL_MODIFICATION` | managed/generated current bytes differ from old lock | restore locked bytes or redesign source/ownership; Composer will not merge, overwrite, or delete the unexpected local state |
| `OLD_STATE_INVALID` | locked material is missing, non-regular, or under an unsafe path | repair the target state before retrying; Composer will not overwrite an unexpected state to repair it |
| `DESTINATION_CONFLICT` | newly selected destination conflicts with existing repository structure | deliberately reconcile the ordinary repository path, then rerun `plan` |
| `FILE_OWNER_TRANSITION_UPGRADE_REQUIRED` | update detects a component-owner change at one destination | update cannot cross it automatically, and current upgrade does not infer the migration; design a source-side migration |
| `OWNERSHIP_TRANSITION_UPGRADE_REQUIRED` | update detects ownership-mode change | update cannot cross it automatically, and current upgrade does not infer the migration; design a source-side migration |
| `FILE_OWNER_TRANSITION_NOT_SUPPORTED` | explicit upgrade still requires owner migration | provide an explicit source-side migration design; do not edit lock metadata or retry unchanged |
| `OWNERSHIP_TRANSITION_NOT_SUPPORTED` | explicit upgrade still requires ownership migration | provide an explicit source-side migration design; do not edit lock metadata or retry unchanged |
| `PRECONDITION_CHANGED` | bytes or metadata changed after the transaction/plan precondition was established | inspect the unexpected change; preserve any transaction marker and do not force an overwrite |

Other codes may describe invalid source authorities, malformed schemas/configuration, unsafe paths, unsupported generated handlers, or I/O failures. They are source/contract failures rather than normal lifecycle choices.

## Exit status

Except for explicit help output, standard output uses the selected public output format. With omitted `--format` or explicit `--format json`, normal results and Composer errors remain machine-readable JSON. With `--format human`, those same lifecycle payloads are rendered as human-facing text. Output format does not alter the status code:

- `0` — requested operation, validation, or explicit help succeeded;
- `2` — invalid state, conflict, argument-level Composer error, or managed-operation failure;
- `3` — initial apply materialized files but its immediate post-apply consumer validation failed; the Composer attempts to remove the just-written lock so the repository is not reported as successfully managed.

Argparse usage errors follow Python `argparse` behavior. Runner-local acquisition or selection failures also return `2` but are written as runner errors to standard error before the Composer is invoked.

## Consumer validator

Every artifact includes `lifecycle.composition-state`, which materializes a stdlib-only state validator, a managed validation registry, and a selected-component validation runner under `.template-composition/`.

The source-side `compose.py validate` command first runs the source-authority Composition-state validator, then invokes the consumer's canonical `.template-composition/validate.py` entrypoint. That runner reads `resolved_components` only after state validation succeeds and dispatches only validators registered for those selected components.

Consumer validation checks lock shape/semantics, materialized repository state, and selected-component validation. `managed` and `generated` bytes must equal the lock digest. Active `seed` files must remain present but may differ from their provenance digest. Product-mode release evidence and bundles remain exact-candidate checks and are reported as deferred by ordinary repository validation.

Consumer validation does not re-resolve the source component graph or verify source descriptor bytes; those checks remain source-side Composer responsibilities.
