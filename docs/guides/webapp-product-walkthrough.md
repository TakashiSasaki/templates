# Webapp product walkthrough

This is the canonical first-use walkthrough for creating a Web application with Composition. Follow it from top to bottom if you are new to this repository; you do not need to read the Composition architecture first.

The example product is **Task Ledger**. It will eventually provide a browser UI for creating, listing, editing, completing, deleting, and filtering tasks, persistent storage, an independently supported HTTP JSON API, and a small `list` / `export` CLI.

Composition supplies contracts, managed validation material, and a deterministic lifecycle. It does not choose the product framework, database, API implementation, deployment platform, or product test system. Python and SQLite appear later only as concrete Task Ledger product decisions.

## 0. What this walkthrough will produce

You will create a **separate product repository** named `task-ledger`. Do not clone `TakashiSasaki/templates` and start implementing Task Ledger inside it. The normal relationship is:

```text
TakashiSasaki/templates
        |
        | provides the Composition tooling and contracts
        v
your separate task-ledger product repository
```

By the first milestone you will have:

```text
a separate product repository
        ↓
Composition installed outside that repository
        ↓
composition.json
        ↓
inspect → plan → review → apply → validate
        ↓
a valid Composition scaffold
        ↓
a clear editing boundary and product-development starting point
```

That first `VALID` scaffold is intentionally **not** a claim that the Web application has been implemented or product-tested. The later sections take the same repository through real product code, product verification, implementation evidence, optional Policy adoption, and normal Composition maintenance.

Command examples below use POSIX shell syntax and absolute placeholder paths such as `/absolute/path/to/task-ledger`. On another shell or operating system, use the equivalent directory-creation commands, but keep the shown Python runner argument semantics. In particular, use absolute paths for the canonical first-use `--repository` and `--config` values so their resolution is unambiguous.

## 1. Create the separate product repository

Choose a normal development location that is **not inside your checkout of `TakashiSasaki/templates`**.

**Run**

```sh
mkdir /absolute/path/to/task-ledger
cd /absolute/path/to/task-ledger
git init
```

**Expected**

- `/absolute/path/to/task-ledger` exists as its own Git repository.
- It does not yet contain `.template-composition/lock.json`.

**Repository change**

Yes. This creates the product repository itself. No Composition material has been added yet.

**What this means**

Task Ledger is the consumer repository. `TakashiSasaki/templates` remains the provider of Composition and Policy authorities; it is not the application repository you are about to implement.

**Next**

Check the two prerequisites used by the Composition runner.

## 2. Check prerequisites

The supported runner prerequisites are Git on `PATH` and CPython 3.11, 3.12, 3.13, or 3.14.

**Run**

```sh
git --version
python --version
```

**Expected**

- Git reports a version and exits successfully.
- Python reports 3.11 through 3.14.

**Repository change**

None.

**What this means**

The local machine can run the supported immutable Composition installer and runner. In a sandbox or CI environment whose normal user cache is not writable, set `COMPOSITION_RUNTIME_CACHE` and `COMPOSITION_VALIDATION_CACHE` to writable directories outside the product repository before the first runner invocation; the full cache guidance is in [Using Composition](../consumer-guide.md#install-and-run-the-composition-skill).

**Next**

Install the published Composition skill outside Task Ledger.

## 3. Install Composition

Normal consumers install the Composition skill through the reviewed immutable installer. Pick an installation directory outside the product repository; this walkthrough uses `/absolute/path/to/agent-skills/composition`.

**Run**

```sh
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/452cef1960612353b9ea206447b97a022ac1c2d7/scripts/install_composition_skill.py', timeout=30).read())" /absolute/path/to/agent-skills/composition
```

If that destination already contains an installed Composition skill, use the documented `--replace` path in [Using Composition](../consumer-guide.md#install-and-run-the-composition-skill) rather than deleting or overwriting an arbitrary directory.

**Expected**

`/absolute/path/to/agent-skills/composition/scripts/run.py` exists as the installed repository-facing runner.

**Repository change**

None in Task Ledger. The skill is installed at the separate destination you selected. Later runner and validator cache creation also occurs outside the product repository.

**What this means**

You now have the normal consumer entry point. The full-SHA installer URL is intentional: Composition uses reviewed immutable source identities rather than a mutable branch or tag. You do not need to understand the installer/skill/toolchain SHA roles before continuing; see [Using Composition](../consumer-guide.md#immutable-source-runtime-selection-and-cache-reuse) when you need that trust detail.

**Next**

Create Task Ledger's Composition intent file in the product repository.

## 4. Create `composition.json`

Task Ledger deliberately supports three caller-visible concerns beyond the Webapp baseline:

| Requirement | Selection | Why |
| --- | --- | --- |
| Browser product UI | `webapp` recipe baseline | The Webapp artifact already defines browser surfaces, routes, visible states, viewports, and Web-specific validation. |
| Python process and execution commands | `capability.runtime` | The product has a maintained application runtime. |
| Independent HTTP JSON API | `capability.service` | Non-browser callers may use the API without the browser UI. |
| Maintained `list` / `export` CLI | `capability.cli` | The CLI is a supported caller-visible interface. |

A shared process or port does not merge those caller-visible contracts. Conversely, do not select capabilities merely because implementation code happens to use a process, route, or library internally.

Create `/absolute/path/to/task-ledger/composition.json` with exactly this initial intent:

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": [
      "capability.cli",
      "capability.runtime",
      "capability.service"
    ],
    "exclude": []
  },
  "parameters": {}
}
```

The same machine-checked example is stored in `examples/onboarding/task-ledger/composition.json` in the Composition authority. Recipe dependency closure adds required lifecycle components; do not duplicate those required components in `include` merely to document the closure.

**Expected**

`composition.json` is present at the root of the Task Ledger product repository.

**Repository change**

Yes. `composition.json` is consumer intent that you created. Composition has still not materialized any scaffold files.

**What this means**

You have stated what kind of artifact and externally supported capabilities you want. You have not yet asked Composition to mutate the repository.

**Next**

Inspect the target state.

## 5. Inspect the repository

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  inspect
```

**Expected**

Because you just created the directory and no Composition lock exists, the JSON output contains:

```json
{
  "state": "unmanaged"
}
```

The real output also includes the absolute `target`. If you had run `inspect` before creating the directory, `absent` would also be a normal new-target state.

**Repository change**

None. `inspect` is read-only.

**What this means**

Composition does not currently manage this repository. That is the expected first-use state.

If you instead see `managed-valid`, `managed-invalid`, or `managed-interrupted`, stop treating this as a fresh initial composition. Use the state-specific workflow in [Using Composition](../consumer-guide.md#check-whether-a-repository-is-managed); an interrupted repository must be recovered rather than re-initialized.

**Next**

Plan the initial materialization using the configuration you just created.

## 6. Plan the initial materialization

For the canonical example, use an **absolute** `--config` path.

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --config /absolute/path/to/task-ledger/composition.json
```

**Expected**

The JSON plan contains:

- `operation: "initial"`;
- the normalized `intent`;
- the resolved components;
- an `actions` list, normally dominated by `create` for a fresh repository;
- a `conflicts` list, which should be empty before you proceed; and
- a `lock_preview` showing the state that would be recorded.

A byte-identical pre-existing destination may be reported as `adopt-identical` rather than `create`.

**Repository change**

None. Initial planning is read-only. It does not create the lock or scaffold.

**What this means**

You are looking at the complete deterministic mutation proposal before allowing it to run.

`--config` has an important path rule: a relative path is resolved from the **process current working directory**, not from `--repository`. The absolute path above deliberately avoids requiring you to infer that relationship. The same rule applies to a new `upgrade` that accepts `--config`.

**Next**

Review the plan. Do not jump directly from configuration authoring to `apply`.

## 7. Review the plan

Check the `actions` and `conflicts` fields from the previous command.

Proceed when:

- the target is `/absolute/path/to/task-ledger`;
- the recipe and component intent are the ones you selected;
- every action is understood (`create` or an intentional `adopt-identical` on a fresh target); and
- `conflicts` is empty.

If a conflict exists, resolve why the destination already contains different bytes before applying. Do not rename or delete Composition metadata to make the conflict disappear.

**Repository change**

None. Reviewing a plan is a human decision point, not a mutation step.

**What this means**

`plan` is the fail-closed safety boundary between intent and mutation.

**Next**

Apply exactly the reviewed intent.

## 8. Apply the scaffold

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --config /absolute/path/to/task-ledger/composition.json
```

**Expected**

The JSON result reports `status: "applied"`, `operation: "initial"`, created/adopted destinations, and `lock: ".template-composition/lock.json"`.

**Repository change**

Yes. This is the first Composition command in the walkthrough that materializes the scaffold. Composition writes `.template-composition/lock.json` last, after the planned files have been installed and source-state validation succeeds.

**What this means**

Task Ledger is now a Composition-managed consumer repository. Ownership for each materialized file is recorded in the lock.

**Next**

Validate the scaffold before starting product implementation.

## 9. Validate the scaffold

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  validate
```

**Expected**

The public JSON result has `status: "valid"`. Selected-component checks include the Webapp and lifecycle validators required by the resolved component set. Because implementation evidence starts in `template` mode, the implementation-evidence check is deferred rather than asserted as a product claim.

**Repository change**

No product-repository content is intentionally changed by validation. A cold validation may create or reuse an isolated cache outside the repository.

**What this means**

> **Composition validation: VALID** means the resolved Composition state and template contracts are valid. It does **not** mean that Task Ledger is implemented, product-tested, deployed, or release-ready.

This distinction is the boundary between a safe scaffold and a finished product.

**Next**

Inspect ownership before editing anything generated by Composition.

## 10. Inspect the generated tree and editing boundary

Read `.template-composition/lock.json`. Do not edit the lock itself. It records each materialized file's component owner, ownership mode, and materialized digest.

For this Task Ledger configuration, concrete examples are:

| File | Ownership | What you should do |
| --- | --- | --- |
| `README.md` | `seed` | **Edit it.** Replace scaffold wording with Task Ledger-specific documentation. |
| `TEMPLATE.md` | `seed` | **Edit it.** Specialize the Webapp product contract. |
| `RUNTIME.md` | `seed` | **Edit it.** Record the actual Task Ledger runtime decisions. |
| `CLI_INTERFACE.md` | `seed` | **Edit it.** Define the supported `list` / `export` behavior. |
| `SERVICE_INTERFACE.md` | `seed` | **Edit it.** Define the independently supported JSON API. |
| `contracts/routes.json`, `contracts/surfaces.json`, `contracts/ui-states.json`, `contracts/viewports.json` | `seed` | **Edit them.** Make the browser contracts truthful for Task Ledger. |
| `contracts/implementation-evidence.json` | `seed` | **Edit later, after real proofs exist.** It initially remains in `template` mode. |
| `contracts/manifest.json` | `generated` | **Do not hand-edit it.** Composition regenerates it deterministically. |
| `schemas/*.schema.json` | `managed` | **Do not hand-edit them.** They remain Composition-owned. |
| `.github/workflows/validate-webapp.yml` | `managed` | **Do not hand-edit it.** It is Composition-owned validation wiring. |
| `scripts/validate_contracts.py`, `scripts/scaffold_webapp_evidence.py` and other scaffold validators | `managed` | **Do not hand-edit them.** Use them as provided. |
| `.template-composition/validate.py` and other `.template-composition` validator material | `managed` | **Do not hand-edit them.** |
| `.template-composition/lock.json` | Composer state | **Do not hand-edit it.** Lifecycle operations own it. |
| new files such as `task_ledger/server.py` or `tests/test_task_ledger.py` | ordinary consumer content | **Create and edit them normally.** They are product implementation, not Composition-owned material. |

The generic rule is: `seed` transfers to consumer ownership after initial materialization; `managed` and `generated` remain Composition-owned; a path absent from the lock is ordinary consumer content unless another repository-local authority says otherwise.

Do not copy a managed schema or validator into a product-owned variant merely to bypass validation.

**Next**

Turn the editable seeds into truthful Task Ledger contracts, then implement the product in ordinary consumer files.

## 11. Replace template assumptions with the actual product contract

Keep only contract items the product really implements.

### Browser contract

A small Task Ledger inventory can use:

| Contract | Product decision |
| --- | --- |
| surface | `primary`: Task Ledger browser UI, local-product audience, non-diagnostic |
| route | `home` at `/`: canonical task-list/editor route |
| states | `ready` plus only the loading/empty/error states actually visible in the implementation |
| viewport | retain or revise the responsive lower bound and input/zoom behavior to match tested behavior |

Do not add authentication, administration, role-based authorization, touch support, multiple breakpoints, or diagnostic surfaces merely because a larger application might need them.

### Runtime contract

Concretize `RUNTIME.md` with consumer decisions. For this example:

```text
Implementation ecosystem: CPython 3.11+
Persistence: SQLite
Server command: python -m task_ledger.cli --database task-ledger.db serve --host 127.0.0.1 --port 8080
Distribution: source execution for this example
```

These are product decisions, not Composition defaults.

### Service contract

Concretize `SERVICE_INTERFACE.md` because the JSON API is independently supported. A small contract can include:

```text
GET    /api/tasks?status=all|open|completed
GET    /api/tasks/{id}
POST   /api/tasks
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
GET    /healthz
```

Specify request validation, result/error semantics, size limits, authentication/exposure decisions, readiness/liveness behavior, restart handling, and the relationship to the browser UI. Sharing one process/listener with the UI does not remove those service obligations.

### CLI contract

Concretize `CLI_INTERFACE.md`, for example:

```sh
python -m task_ledger.cli --database task-ledger.db list --status all
python -m task_ledger.cli --database task-ledger.db export
```

Document stdout/stderr, exit status, invalid arguments, persistence-target selection, and whether CLI operations have semantics equivalent to corresponding API operations.

## 12. Implement in consumer-owned source files

A possible product tree is:

```text
task-ledger/
├── task_ledger/
│   ├── cli.py
│   ├── server.py
│   ├── store.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── tests/
│   └── test_task_ledger.py
└── scripts/
    └── verify.sh
```

Composition does not require this layout. These are ordinary consumer-owned implementation and verification files; managed/generated Composition material remains untouched.

The implementation should satisfy the contracts rather than merely make the validator green. At minimum demonstrate create/list/edit/complete/delete behavior, open/completed filtering, persistence across restart, independent JSON API use, CLI `list` / `export`, and negative input/error cases corresponding to declared contracts.

## 13. Define and run authoritative product verification

Composition does not choose the product test runner. Task Ledger may define one independently runnable command:

**Run**

```sh
./scripts/verify.sh
```

**Expected**

The consumer-owned unit/integration/product checks pass and the command exits successfully.

**Repository change**

The command itself should not rewrite Composition-owned material. Adding `scripts/verify.sh` and product tests beforehand is normal consumer development.

**What this means**

You now have product-behavior evidence that is separate from Composition's structural/contract validation.

**Next**

Derive the exact evidence targets from the current contracts rather than inventing target IDs.

## 14. Generate the current evidence worklist

The Webapp scaffold includes a read-only deterministic generator.

**Run**

```sh
python scripts/scaffold_webapp_evidence.py > /tmp/webapp-evidence-worklist.json
```

**Expected**

A JSON worklist is written to the selected output file. `contracts/implementation-evidence.json` is unchanged.

**Repository change**

None from the generator itself. The redirected worklist above is outside the repository.

**What this means**

The target set comes from the actual current surface, route, state, and viewport contracts. If those contracts change, regenerate the worklist.

**Next**

For every current target, identify the implementation boundary, at least one positive proof, at least one negative proof, the authoritative command that produces those proofs, and a release gate that executes the referenced command.

Multiple records may reuse one command/gate when one suite genuinely proves multiple targets; do not manufacture one command per record.

## 15. Switch implementation evidence to product mode only after proof exists

The initial `contracts/implementation-evidence.json` is intentionally in `template` mode with no product implementation claim. Change it to `product` mode only after the implementation, `./scripts/verify.sh`, and referenced proof locations really exist.

A command and gate can look like:

```json
{
  "commands": [
    {
      "id": "verify-product",
      "command": "./scripts/verify.sh",
      "purpose": "Run Task Ledger product verification."
    }
  ],
  "releaseGates": [
    {
      "id": "product-verification",
      "purpose": "Require the authoritative product verification command.",
      "commandIds": ["verify-product"]
    }
  ]
}
```

Each record still needs its exact worklist target, verified implementation-boundary locator, verified positive/negative proof locators, expected results, and selected gate. Do not copy a sample target from this guide; the authoritative target set belongs to the consumer repository.

Now run both verification layers.

**Run**

```sh
./scripts/verify.sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  validate
```

**Expected**

- the product verification command passes; and
- Composition validation returns `status: "valid"` with implementation evidence executed rather than template-deferred.

**What this means**

Task Ledger now has both a product-behavior claim backed by consumer tests and a valid closed Composition contract/evidence relationship. This is the point at which “valid scaffold” and “implemented, product-tested application” have both been satisfied rather than confused.

## 16. Optionally adopt coding-agent Policy

Policy is a **separate authority**, not a Composition capability. Do not add a fictitious `capability.policy` to `composition.json`.

If coding agents will maintain Task Ledger, follow the Policy getting-started workflow after Composition has materialized its seeds and transferred those seeds to consumer ownership:

```text
Composition initial
  → consumer-owned seed/product implementation
  → explicit Policy adoption
  → Composition validation + Policy validation/check + product verification
```

Composition does not own `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`. Use the published [Policy getting-started guide](https://templates.moukaeritai.work/policy/getting-started/) for the Policy-owned adoption commands rather than copying those semantics into this Composition tutorial.

## 17. Make ordinary product changes normally

Adding a Task Ledger feature, changing SQLite queries, editing consumer-owned seed contracts, or adding product tests is ordinary repository work. It does not require a Composition `update` merely because the product changed.

After a product change:

1. update consumer-owned contracts/evidence truthfully;
2. run `./scripts/verify.sh`;
3. run Composition `validate`;
4. run Policy validation/check as well if Policy is adopted.

Use Composition lifecycle operations only when the Composition source/intent itself changes.

## 18. Update or upgrade Composition later

When the installed runner selects a newer reviewed Composition revision, inspect first.

For unchanged intent and no compatibility-boundary change:

**Run**

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  inspect
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --mode update
```

Review the read-only plan. If acceptable:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --mode update
```

Consumer-owned seed changes are preserved; clean managed/generated material may be replaced or removed according to the reviewed plan.

If the plan reports `COMPONENT_VERSION_UPGRADE_REQUIRED`, or if Task Ledger intentionally changes recipe/components/parameters, make that boundary explicit:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  plan --mode upgrade --config /absolute/path/to/task-ledger/composition.json

python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/task-ledger \
  apply --mode upgrade --config /absolute/path/to/task-ledger/composition.json
```

Then rerun product verification and Composition validation. Do not edit lock metadata to turn an update/upgrade conflict into apparent success.

## Completion checklist

At the **first-use scaffold milestone**, you have succeeded when:

- Task Ledger is a separate product repository;
- the Composition skill is installed outside it;
- `composition.json` states the intended Webapp/capability selection;
- `inspect → plan → review → apply → validate` was followed in order;
- the plan was understood as read-only before mutation;
- Composition validation is valid; and
- you can identify concrete files that are editable seeds, Composition-owned managed/generated material, and ordinary product code.

The **implemented-product milestone** is stronger. It additionally requires:

- consumer-owned contracts describe the real product rather than template assumptions;
- product source and tests exist;
- the authoritative product verification command passes;
- implementation evidence is in `product` mode with complete current-target coverage and real positive/negative proofs;
- Composition validation passes with implementation evidence executed rather than template-deferred; and
- optional Policy state is independently valid if Policy was adopted.

If you reached the first milestone, you no longer need to infer what to do next: edit the consumer-owned Task Ledger contracts, add ordinary product source/tests, and proceed through Sections 11–15. Architecture, exact ownership rules, managed recovery, and immutable-source details remain available in [Using Composition](../consumer-guide.md) and the [Composer reference](../reference/composer.md) when you need them.
