# Using Composition

This guide is for consumers who use Composition to create and maintain a concrete Agent Skill or Web application repository. It covers normal repository operations. The architecture documents explain why the lock, digest, and transaction rules work the way they do, but they are not required to start using the Composer.

For exact CLI options, plan fields, ownership definitions, and diagnostic codes, see the [Composer reference](reference/composer.md).

## Choose the operation

Start from what you want to do:

| Goal | Operation |
| --- | --- |
| Create a repository that is not yet managed by Composition | `initial` |
| Move an existing managed repository to a newer descendant Composition revision without changing its recorded intent | `update` |
| Explicitly change recipe, component selection, parameters, or cross a component-version compatibility boundary | `upgrade` |
| Resume an interrupted `update` or `upgrade` | rerun the matching `apply --mode ...` operation |

`inspect` and `validate` are mode-neutral. Use `inspect` before choosing a mutating operation and `validate` after a successful apply.

## Before you run the Composer

The current consumer entrypoint runs directly from the exact Composition source checkout that you intend to use. The supported runtime prerequisites are:

- Git available on `PATH`;
- CPython 3.11, 3.12, 3.13, or 3.14; and
- the exact distributions in `requirements-runtime.lock`.

The consumer runtime contract is intentionally separate from `requirements-dev.lock`. The development lock may grow to include repository tests, publication validation, or other maintainer-only tooling; consumers should install `requirements-runtime.lock`, not infer runtime requirements from the development environment.

Create an isolated environment and install the reviewed runtime graph with dependency resolution disabled. For example on POSIX:

```sh
python -I -m venv /path/to/composition-runtime
/path/to/composition-runtime/bin/python -I -m pip install \
  --isolated \
  --disable-pip-version-check \
  --no-deps \
  --requirement requirements-runtime.lock
/path/to/composition-runtime/bin/python -I scripts/verify_runtime_environment.py
```

On Windows, use the corresponding `Scripts\python.exe` inside the virtual environment. The verification command rejects unsupported Python versions, missing or additional non-bootstrap distributions, and version mismatches against `requirements-runtime.lock`.

The command examples below use `python` for readability. Run them with the verified runtime interpreter, whether by activating that environment or by invoking its Python executable explicitly.

The Composition checkout must be clean for tracked files. Composer reads its exact source identity from Git rather than treating a mutable branch name as runtime identity. Managed `update` and `upgrade` additionally require the old revision recorded in the consumer lock to be available in local Git history and the target Composition revision to equal or descend from that old revision. A shallow checkout that omits the old revision is therefore insufficient for those operations.

The target repository may be outside the Composition checkout.

Initial composition and a new upgrade require a consumer configuration file. A minimal Skill configuration is:

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

For a Web application, use `"recipe": "webapp"`. Add optional `capability.*` or `lifecycle.*` component IDs through `components.include` only when the selected recipe exposes them. Recipe files under `recipes/` are the source of truth for selectable components.

At the current production revision, components do not define parameter-specific materialization behavior. Keep `parameters` empty unless a selected component explicitly documents a supported parameter contract. Parameter values are still part of normalized consumer intent, so changing them is an explicit `upgrade` boundary.

## Create a new managed repository

First inspect the target:

```sh
python scripts/compose.py inspect --target /path/to/repository
```

For a new target, `absent` or `unmanaged` is expected. If `inspect` reports any managed state, do not fall back to initial composition merely because validation failed: `managed-valid` should use `update` or `upgrade`, `managed-interrupted` should be recovered first, and `managed-invalid` should be diagnosed and repaired before retrying the appropriate managed operation. Initial composition refuses a pre-existing Composition lock.

Plan before applying:

```sh
python scripts/compose.py plan \
  --config composition.json \
  --target /path/to/repository
```

Initial planning is read-only. Review every action and conflict before applying. `create` means Composition will create a new destination. `adopt-identical` means the destination already has exactly the desired bytes and may be adopted without overwriting it. Any conflict prevents apply from proceeding.

Apply the same configuration:

```sh
python scripts/compose.py apply \
  --config composition.json \
  --target /path/to/repository
```

Then validate:

```sh
python scripts/compose.py validate --target /path/to/repository
```

A successful initial apply writes `.template-composition/lock.json` last. The repository is then managed state.

## Use Policy with a Composition repository

Coding-agent Policy is optional and is adopted independently. Composition does not create `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`, does not expose Policy adoption as a `capability.*`, and does not invoke the `agent-policy` CLI.

For a repository that will use both authorities, the normal sequence is:

```text
Composition initial
  -> seed materialization
  -> consumer ownership
  -> optional explicit Policy adoption
  -> independent Policy + Composition managed state
```

This order matters most for the Skill recipe. `artifact.skill-core` materializes `AGENTS.md` as `seed`, so after initial composition its contents are consumer-owned. Explicit Policy adoption may subsequently migrate or replace those instruction bytes. Later Composition `update` / `upgrade` preserves the active seed rather than restoring Composition's original `AGENTS.md` bytes.

Policy-owned metadata is outside Composition ownership. Existing `.agent-policy.yml`, `.agent-policy.lock`, and `.agent-policy/**` are left unchanged when they do not collide with an ordinary Composition material. Composition schemas and consumer validation also reject any component, lock inventory, or transaction that tries to claim those paths.

The reverse ownership transition is not inferred. If a Policy-managed repository already contains a different `AGENTS.md` and you then try Skill initial composition, planning reports a normal destination conflict and apply does not overwrite the file or create a Composition lock. An explicit migration contract would be required to support that reverse transition.

For the complete cross-authority rules, see the Site-owned [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/).

## Check whether a repository is managed

Use:

```sh
python scripts/compose.py inspect --target /path/to/repository
```

The normal states are:

- `absent` — the target path does not exist;
- `unmanaged` — no Composition lock exists;
- `managed-valid` — the lock and current materialized state validate;
- `managed-invalid` — Composition metadata exists but the managed state does not validate;
- `managed-interrupted` — a managed transaction marker is present and recovery is required.

An `invalid` state is used for an invalid target root such as a symbolic link.

Do not decide managed state only from whether a repository contains files that look like template output. `.template-composition/lock.json` and `inspect` are the authoritative indicators.

## Update without changing intent

Use `update` when you want the same normalized intent—same recipe, explicit include/exclude choices, and parameters—to move forward to the current descendant Composition source revision.

Inspect and plan:

```sh
python scripts/compose.py inspect --target /path/to/repository
python scripts/compose.py plan --mode update --target /path/to/repository
```

`update` deliberately does not accept `--config`. Lock schema v2 stores normalized consumer intent, so accepting a replacement configuration during ordinary update would make an intent change indistinguishable from routine source advancement. If you want to change intent, use `upgrade`.

Review the managed file plan. The main classes are:

- `create` — a newly selected destination can be created safely;
- `replace` — an existing clean `managed` or `generated` destination will receive new bytes;
- `remove` — an existing clean `managed` or `generated` destination is no longer selected and will be removed;
- `preserve` — a `seed` file remains consumer-owned and will not be overwritten or deleted;
- `unchanged` — the desired bytes are already the locked bytes;
- `conflict` — apply must not mutate the repository until the conflict is resolved.

If the plan is acceptable:

```sh
python scripts/compose.py apply --mode update --target /path/to/repository
python scripts/compose.py validate --target /path/to/repository
```

A component-version change is not an ordinary update. The update plan reports `COMPONENT_VERSION_UPGRADE_REQUIRED`; cross that boundary explicitly with `upgrade`.

## Upgrade or change intent

Use `upgrade` when you intentionally change the selected compatibility surface, including:

- recipe;
- explicit component include/exclude choices;
- parameters;
- component versions reported as an upgrade boundary.

Create the desired new configuration and plan it explicitly:

```sh
python scripts/compose.py plan \
  --mode upgrade \
  --config composition.json \
  --target /path/to/repository
```

A new upgrade apply requires the same explicit target intent:

```sh
python scripts/compose.py apply \
  --mode upgrade \
  --config composition.json \
  --target /path/to/repository

python scripts/compose.py validate --target /path/to/repository
```

`upgrade` is explicit, but it is not a general merge or ownership-migration engine. A destination that changes component owner or changes between `managed`, `generated`, and `seed` is still refused. Those transitions require an explicit source-side migration design rather than Composer inference.

## Recover an interrupted update or upgrade

If `inspect` returns `managed-interrupted`, do not delete or edit `.template-composition/transaction.json` manually.

The transaction records the operation and exact target Composition source revision. If necessary, read those fields to identify the required recovery context, but treat the file as Composer-owned metadata.

Check out the exact Composition revision recorded by `transaction.json`, then rerun the matching apply operation:

```sh
python scripts/compose.py apply --mode update --target /path/to/repository
```

or:

```sh
python scripts/compose.py apply --mode upgrade --target /path/to/repository
```

Recovery uses the already recorded transaction. In particular, interrupted upgrade recovery must not receive `--config`; the target intent and new lock are already bound by the transaction.

After recovery succeeds:

```sh
python scripts/compose.py validate --target /path/to/repository
```

Recovery is deterministic roll-forward. If a file no longer matches either the recorded old state or an already-applied new state, the Composer stops rather than overwriting unexpected bytes.

## Which files may you edit?

Use the `ownership` field in `.template-composition/lock.json` to decide how a materialized file is owned.

| Ownership | Consumer editing rule |
| --- | --- |
| `managed` | Do not edit locally if you expect update/upgrade to manage the file. Composition remains authoritative. |
| `generated` | Do not edit locally. The bytes are deterministically regenerated from Composition authorities. |
| `seed` | Edit as normal repository content after first materialization. Composition does not overwrite later consumer edits. |

Files not listed in the active lock are ordinary repository content unless another repository-local contract says otherwise. Policy-owned metadata is one explicit example: `.agent-policy.yml`, `.agent-policy.lock`, and `.agent-policy/**` remain outside the Composition lock and are not repair targets for Composer operations.

Do not manually edit Composer-owned metadata such as `.template-composition/lock.json` or `.template-composition/transaction.json` to bypass a conflict.

## What to do when planning reports a conflict

Planning is intentionally fail-closed and read-only. Fix the cause, then rerun `plan` before any `apply`.

Common cases are:

- `LOCAL_MODIFICATION` — a `managed` or `generated` file no longer matches the old lock. Restore the locked bytes if Composition should continue managing it, or stop and redesign ownership/source authority if the local change must remain. The Composer will not merge or overwrite it.
- `COMPONENT_VERSION_UPGRADE_REQUIRED` — use `upgrade` with an explicit configuration representing the desired intent.
- `FILE_OWNER_TRANSITION_UPGRADE_REQUIRED` / `OWNERSHIP_TRANSITION_UPGRADE_REQUIRED` — update has reached an explicit compatibility boundary. Current upgrade also does not infer the migration; an explicit source-side migration design is required.
- `SOURCE_REVISION_NOT_DESCENDANT` — use a Composition revision that is the locked source revision or its descendant.
- `OLD_SOURCE_REVISION_UNAVAILABLE` — make the old locked revision available in the local Composition Git history before retrying.
- `DESTINATION_CONFLICT` — remove or deliberately reconcile the conflicting ordinary repository path; do not rely on Composer overwrite.
- `RECOVERY_REQUIRED` — finish the existing transaction instead of starting a new plan.

See the [Composer reference](reference/composer.md) for exact diagnostic meanings.

## Why plan before apply?

`plan` resolves the exact current Composition source, compares it with the target repository, and exposes all proposed mutations and conflicts without writing the target. Managed `apply` performs its own deterministic planning before writing a transaction marker, but reviewing an explicit plan first is the consumer safety checkpoint: it lets you inspect component changes, file replacements/removals, seed preservation, and conflicts before any filesystem mutation is allowed.

## Deeper design information

Normal consumer operation should not require the architecture documents. Use them when you need the design rationale or are maintaining Composition itself:

- [Composition model](architecture/composition-model.md) — authority, intent, lock, component, and ownership model;
- [Composer MVP](architecture/composer-mvp.md) — deterministic resolver, reconciliation, transaction, digest precondition, and crash-recovery contract;
- [Composition state](../components/lifecycle.composition-state/files/docs/architecture/composition-state.md) — self-contained consumer validation contract.
