# Using Composition

This guide is for consumers who use Composition to create and maintain a concrete Agent Skill or Web application repository. Normal consumers use the installed Composition skill runner; the Composer remains the semantic authority underneath that runner.

In this guide, maintainers of a concrete Skill or Web application repository are consumers. **Composition authority maintainer** refers only to someone changing or maintaining the `composition` authority itself in `TakashiSasaki/templates`.

For exact Composer options, plan fields, ownership definitions, and diagnostic codes, see the [Composer reference](reference/composer.md).

## Choose the operation

Start from what you want to do:

| Goal | Operation |
| --- | --- |
| Create a repository that is not yet managed by Composition | `initial` |
| Move an existing managed repository to a newer descendant Composition revision without changing its recorded intent | `update` |
| Explicitly change recipe, component selection, parameters, or cross a component-version compatibility boundary | `upgrade` |
| Resume an interrupted `update` or `upgrade` | rerun the matching `apply --mode ...` operation |

`inspect` and `validate` are mode-neutral. Use `inspect` before choosing a mutating operation and `validate` after a successful apply.

## Install and run the Composition skill

The supported normal-consumer prerequisite is CPython 3.11, 3.12, 3.13, or 3.14. Git is not required for normal Composition consumption. You do not clone `TakashiSasaki/templates`, `composition`, `site`, or `policy` before using the templates. The installed runner acquires the selected immutable Composition revision over HTTPS and uses Python's standard library for source bootstrap.

Cold execution also requires network access to GitHub for the selected full-SHA source archive and, when a matching Python runtime is not already cached, access to the configured Python package source. Managed `update` / `upgrade` additionally requires GitHub's compare API to establish old-to-new revision ancestry. Those network dependencies fail closed; the runner does not substitute a mutable branch or guess ancestry.

If you are running in a sandbox, container, CI worker, or other environment whose default user cache is not writable, choose writable cache roots before the first runner invocation. The runner and materialized validator support separate cache overrides:

```sh
export COMPOSITION_RUNTIME_CACHE=/path/to/writable/composition-runtime-cache
export COMPOSITION_VALIDATION_CACHE=/path/to/writable/composition-validation-cache
```

Use environment-appropriate paths and keep these caches outside the product repository. `COMPOSITION_RUNTIME_CACHE` contains validated Python runtime state only; normal Composition source snapshots are disposable and are not stored there. An unwritable default cache is an environment problem, not a reason to change Composition ownership or execute a mutable source revision.

Normal consumers install the published Composition skill through the immutable stdlib-only bootstrap script. The installer URL is pinned to the reviewed installer commit rather than to a branch or tag, and the downloaded bytes must match the published installer SHA-256 before they are written or executed:

```sh
python -I -c '
import hashlib
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

url = "https://raw.githubusercontent.com/TakashiSasaki/templates/677dc68fe35fc285638b46685950d31e3a3d3c2f/scripts/install_composition_skill.py"
expected = "134fae0e01d1ee1d560f5f2c0284dc56e241626fd4d89a426a68fa41d7e93e34"
data = urllib.request.urlopen(url, timeout=30).read()
actual = hashlib.sha256(data).hexdigest()
if actual != expected:
    raise SystemExit(f"installer SHA-256 mismatch: expected {expected}, got {actual}")
print(f"Verified Composition installer SHA-256: {actual}")
with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as handle:
    handle.write(data)
    installer = pathlib.Path(handle.name)
try:
    subprocess.run([sys.executable, "-I", str(installer), *sys.argv[1:]], check=True)
finally:
    installer.unlink(missing_ok=True)
' /path/to/agent-skills/composition
```

A digest mismatch exits before installer bytes are written or an installer process is launched. The printed digest is useful audit evidence. If that destination already contains this Composition skill, append `--replace`. Replacement is refused when the existing directory is not identified by `SKILL.md` as the `composition` skill.

The published installer identity, installed skill source identity, and stable Composition toolchain identity are separate immutable full SHAs. The installer at `677dc68fe35fc285638b46685950d31e3a3d3c2f` installs skill source `69af2ed811875f95838bf978ee09365554405664`; that skill's runtime manifest selects stable Composition toolchain revision `16d3eb411729a79549dbaaf6dab1d05207f83415`. The installer bytes are additionally pinned by SHA-256 `134fae0e01d1ee1d560f5f2c0284dc56e241626fd4d89a426a68fa41d7e93e34`. These identities are recorded in `release/composition-installer.json` and verified from repository history by Composition CI. Do not substitute the mutable `composition` branch or a tag into the installer URL, and do not replace the verified bootstrap with direct execution of downloaded bytes.

The normal command shape is:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  COMMAND [COMPOSER OPTIONS]
```

After installation, use the read-only doctor before first acquisition when you need to diagnose local bootstrap prerequisites or runtime-cache behavior:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  doctor
```

Use `doctor --format json` for machine-readable diagnostics. Doctor checks the selected immutable revision, supported CPython, and persistent runtime-cache write/atomic-rename capability. It reports Git as `not-required` for normal consumer execution and source acquisition as `ephemeral`. It does not contact GitHub or package indexes and does not acquire source/runtime state. A `READY` result is therefore a local bootstrap diagnosis, not Composition validation and not a guarantee that later cold acquisition will have network/package availability.

For example, inspect the repository with:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

The runner owns the Composer target. Do not also pass `--target`; use runner `--repository`.

### Install from a reviewed checkout

Composition authority maintainers may instead install the skill from an exact reviewed Composition checkout:

```sh
python skills/composition/scripts/install.py /path/to/agent-skills/composition
```

This is an advanced source-maintenance path, not the normal consumer installation route. The checkout itself must be an exact reviewed revision rather than a mutable branch identity. Git is an expected maintainer prerequisite for this reviewed-checkout path. Use `--replace` only for an existing installation already identified as the Composition skill.

### Immutable source snapshots and runtime reuse

The installed skill does not execute a mutable `composition` branch or tag and does not create a persistent templates checkout.

`runtime-manifest.json` records the normal full-SHA Composition source revision and the SHA-256 of that revision's `requirements-runtime.lock`. On each Composer invocation the runner:

1. chooses an immutable full SHA;
2. downloads `https://codeload.github.com/TakashiSasaki/templates/tar.gz/<full-sha>` with Python's standard library;
3. rejects unsafe archive paths, symbolic/hard links, duplicate or portable-colliding paths, unsupported member types, and configured archive limits;
4. extracts the revision into an OS temporary directory, records a SHA-256 inventory of every regular file, and supplies repository/revision/inventory metadata to the Composer;
5. requires every Composer authority file to remain inside that acquired snapshot, be present in the inventory, and retain its acquired digest;
6. verifies the stable runtime-lock digest when the stable manifest revision is selected;
7. derives a persistent runtime-cache identity from repository, revision, lock SHA-256, CPython major/minor version, and platform/machine;
8. reuses a runtime only after validating its marker, cached lock digest, Python/platform identity, `pip check`, and the source revision's runtime verifier; otherwise it builds and atomically installs a new isolated runtime from the exact lock with dependency resolution disabled; and
9. invokes that revision's `scripts/compose.py`, then removes the temporary source snapshot/context on normal completion or a handled failure.

An advanced `--revision <full-sha>` may select another exact Composition revision that supports the current immutable snapshot execution contract. Mutable names are rejected.

If `.template-composition/transaction.json` exists, managed recovery is stricter: the transaction's exact source revision overrides the stable manifest pin. A conflicting `--revision` is rejected rather than silently changing the recovery context. Malformed transaction metadata also fails closed.

There is deliberately no persistent source-cache hit. Each normal `inspect`, `plan`, `apply`, or runner `validate` invocation reacquires the selected immutable source archive. The named `COMPOSITION_RUNTIME_CACHE` remains persistent because rebuilding the same validated Python environment is an avoidable performance cost. Consequently a warm runtime does not make normal Composer execution fully offline: GitHub source-archive availability is still required. `doctor` and `provenance` remain network-free.

Materialized validation is self-contained. Normal consumers run runner `validate` without manually creating a validation virtual environment. On a cold materialized validation, the validator may construct an isolated validation runtime in the platform cache and perform package acquisition for the exact reviewed validation requirement set. A valid warm validation cache is reused without package acquisition. Validation cache state lives outside the product repository and does not modify the product repository. Its identity includes the exact requirement-set SHA-256, CPython major/minor version, and platform/machine. The default platform cache uses a `composition/validation-v1` namespace; controlled or read-only environments and tests may set `COMPOSITION_VALIDATION_CACHE=/path/to/writable/cache` to select a writable cache root.

Cache layout and reuse are performance details. They do not change revision selection, recovery, Composer arguments, lock/transaction semantics, source identity, or material ownership.

### Managed revision ancestry without a consumer Git checkout

Managed `update` and `upgrade` must prove that the new selected source revision is the old lock revision or its descendant. Snapshot-backed normal-consumer execution performs this check through GitHub's compare API using the two immutable full SHAs. `ahead` and `identical` transitions are accepted; `behind` and `diverged` transitions are rejected. Unknown commits, HTTP/network failures, rate limiting, malformed responses, and unsupported statuses fail closed rather than permitting an unverified transition.

This network check verifies revision ancestry; it does not turn a branch name into authority. The lock and runner continue to use full commit SHAs only.

### Direct source-checkout execution

Composition authority maintainers may still execute `scripts/compose.py` directly from an exact clean Composition checkout. That path uses the consumer runtime contract in `requirements-runtime.lock` established independently of the runner. The Git-backed source context verifies the reviewed checkout revision, tracked authority files, dirty state, and managed ancestry from local Git history. Normal consumers should prefer the installed skill because it owns immutable source selection, snapshot validation, and runtime setup without requiring a templates clone.

## Consumer configuration

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

For Web applications, select capabilities from the caller-visible contract you intend to support rather than from process or listener topology alone. The `webapp` recipe already provides the browser-application artifact contract; do not add a capability merely because implementation code happens to share a process or port.

| Product requirement | Composition selection |
| --- | --- |
| Browser application surfaces, routes, visible states, and responsive behavior | `webapp` recipe baseline (`artifact.webapp-core`) |
| A separately maintained browser-facing operational, diagnostic, demonstration, or explicitly contracted Web interface | add `capability.web-interface` |
| A backend-for-frontend or JSON endpoint used only as an implementation detail of the browser interface, with no supported independent caller contract | do not add `capability.service` solely for that endpoint |
| An HTTP/JSON or other non-browser API that callers may use independently of the browser | add `capability.service` |
| Browser interface and independently supported API share one process, listener, or reverse proxy | add both applicable capabilities; shared topology does not merge their contracts |
| A maintained command-line interface | add `capability.cli` |

`capability.service` means an independently reachable non-browser service contract. `capability.web-interface` owns its browser-facing routing, interaction, security, health, and failure behavior. A shared listener is therefore not evidence that only one capability exists, and a private BFF route is not by itself evidence that an independent service contract exists.

At the current production revision, components do not define parameter-specific materialization behavior. Keep `parameters` empty unless a selected component explicitly documents a supported parameter contract. Parameter values are still part of normalized consumer intent, so changing them is an explicit `upgrade` boundary.

## Create a new managed repository

First inspect the target:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

For a new target, `absent` or `unmanaged` is expected. If `inspect` reports any managed state, do not fall back to initial composition merely because validation failed: `managed-valid` should use `update` or `upgrade`, `managed-interrupted` should be recovered first, and `managed-invalid` should be diagnosed and repaired before retrying the appropriate managed operation. Initial composition refuses a pre-existing Composition lock.

Plan before applying:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --config composition.json
```

A relative `--config` path is resolved from the process current working directory where you invoke the runner, not from `--repository`. If the configuration file is stored in the target repository but you invoke the runner from somewhere else, use an absolute path (or change to the intended directory first). For example:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --config /path/to/repository/composition.json
```

The same path rule applies to every initial or new-upgrade command that accepts `--config`.

Initial planning is read-only. Review every action and conflict before applying. `create` means Composition will create a new destination. `adopt-identical` means the destination already has exactly the desired bytes and may be adopted without overwriting it. Any conflict prevents apply from proceeding.

Apply the same configuration:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --config composition.json
```

Then validate:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

A successful initial apply writes `.template-composition/lock.json` last. The lock records the exact Composition source revision used by the runner.

### After initial apply: turn the scaffold into a product

Initial validation proves that the resolved Composition state and selected template contracts are internally valid. For a Webapp, baseline implementation evidence deliberately starts in `template` mode with no product implementation claims. A successful validation in that state must not be interpreted as proof that the application has been implemented, tested, deployed, or made release-ready.

Use this sequence after initial materialization:

1. Read `.template-composition/lock.json` and preserve the ownership boundary: edit `seed` and ordinary consumer files; do not hand-edit `managed`, `generated`, lock, or transaction material.
2. Replace the seed assumptions with the product's actual contract. For a Webapp, concretize surfaces, routes, UI states, viewports, and every selected capability worksheet that applies to the product.
3. Implement the product in consumer-owned source files. Composition intentionally does not choose the framework, persistence layer, API design, authentication provider, deployment platform, or product-specific test implementation.
4. For a Webapp, run `python scripts/scaffold_webapp_evidence.py` to render the deterministic current evidence-target worklist. The command is read-only and writes the worklist to standard output.
5. Before product coding, switch `contracts/implementation-evidence.json` from `template` to `planning` and capture the stable caller-visible requirement IDs, descriptions, empty `recordIds`, and `requiredPositiveProofKinds`. Preserve those IDs. After implementation boundaries and real proof definitions exist, connect the records/commands/gates and switch from `planning` to `product`.
6. Run the product's own verification commands and Composition `validate`. Composition validation and product verification are complementary: neither substitutes for the other.
7. If the repository also uses coding-agent Policy, adopt it explicitly after Composition has transferred seed ownership. Policy may then guide the remaining implementation and verification work without becoming a Composition capability.

For Webapps, `TEMPLATE.md` is the generated product worksheet and contains the detailed contract-customization and implementation-evidence guidance. The scaffold command does not rewrite the canonical evidence document automatically; the consumer remains responsible for truthful evidence claims.

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

The reverse ownership transition is not inferred. If a Policy-managed repository already contains a different `AGENTS.md` and you then try Skill initial composition, planning reports a normal destination conflict and apply does not overwrite the file or create a Composition lock.

For the complete cross-authority rules, see the Site-owned [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/).

## Check whether a repository is managed

Use:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
```

The normal states are:

- `absent` — the target path does not exist;
- `unmanaged` — no Composition lock exists;
- `managed-valid` — the lock and current materialized state validate;
- `managed-invalid` — Composition metadata exists but the managed state does not validate;
- `managed-interrupted` — a managed transaction marker is present and recovery is required.

An `invalid` state is used for an invalid target root such as a symbolic link. Do not decide managed state only from whether a repository contains files that look like template output. `.template-composition/lock.json` and `inspect` are the authoritative indicators.

## Update without changing intent

Use `update` when you want the same normalized intent—same recipe, explicit include/exclude choices, and parameters—to move forward to the runner's selected descendant Composition revision.

Inspect and plan:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  inspect
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --mode update
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
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode update
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

A component-version change is not an ordinary update. The update plan reports `COMPONENT_VERSION_UPGRADE_REQUIRED`; cross that boundary explicitly with `upgrade`.

## Upgrade or change intent

Use `upgrade` when you intentionally change the selected compatibility surface, including recipe, explicit component include/exclude choices, parameters, or component versions reported as an upgrade boundary.

Plan the desired new configuration explicitly:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  plan --mode upgrade --config composition.json
```

Then apply the same target intent and validate:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode upgrade --config composition.json
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
```

`upgrade` is explicit, but it is not a general merge or ownership-migration engine. A destination that changes component owner or changes between `managed`, `generated`, and `seed` is still refused. Those transitions require an explicit source-side migration design rather than Composer inference.

## Recover an interrupted update or upgrade

If `inspect` returns `managed-interrupted`, do not delete or edit `.template-composition/transaction.json` manually.

The installed runner reads the transaction before acquiring source. It selects the exact transaction source revision automatically and refuses a conflicting explicit revision.

Rerun the matching operation:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode update
```

or:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  apply --mode upgrade
```

Interrupted upgrade recovery must not receive `--config`; the target intent and new lock are already bound by the transaction.

After recovery succeeds:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/repository \
  validate
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

- `LOCAL_MODIFICATION` — a `managed` or `generated` file no longer matches the old lock. Restore the locked bytes if Composition should continue managing it, or stop and redesign ownership/source authority if the local change must remain.
- `COMPONENT_VERSION_UPGRADE_REQUIRED` — use `upgrade` with an explicit configuration representing the desired intent.
- `FILE_OWNER_TRANSITION_UPGRADE_REQUIRED` / `OWNERSHIP_TRANSITION_UPGRADE_REQUIRED` — current upgrade does not infer that migration; an explicit source-side migration design is required.
- `SOURCE_REVISION_NOT_DESCENDANT` — use a Composition revision that is the locked source revision or its descendant.
- `OLD_SOURCE_REVISION_UNAVAILABLE` — GitHub could not resolve the old locked full SHA in the canonical repository history; verify the recorded source identity/revision and retry when the canonical history is available.
- `SOURCE_TRANSITION_UNAVAILABLE` — archive-backed managed execution could not establish ancestry because the GitHub compare response was unavailable, rate-limited, malformed, or otherwise unusable. Retry rather than bypassing the check.
- `DESTINATION_CONFLICT` — remove or deliberately reconcile the conflicting ordinary repository path; do not rely on Composer overwrite.
- `RECOVERY_REQUIRED` — finish the existing transaction instead of starting a new plan.

See the [Composer reference](reference/composer.md) for exact diagnostic meanings.

## Why plan before apply?

`plan` resolves the exact selected Composition source, compares it with the target repository, and exposes all proposed mutations and conflicts without writing the target. Managed `apply` performs its own deterministic planning before writing a transaction marker, but reviewing an explicit plan first is the consumer safety checkpoint.

## Deeper design information

Normal consumer operation should not require the architecture documents. Use them when you need the design rationale or are maintaining the Composition authority itself:

- [Composition model](architecture/composition-model.md) — authority, intent, lock, component, and ownership model;
- [Composer MVP](architecture/composer-mvp.md) — deterministic resolver, reconciliation, transaction, digest precondition, and crash-recovery contract;
- [Composition state](../components/lifecycle.composition-state/files/docs/architecture/composition-state.md) — self-contained consumer validation contract.
