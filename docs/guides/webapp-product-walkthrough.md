# Webapp product walkthrough

This worked example shows how a consumer can go from a clean directory to a small implemented Web application while preserving Composition ownership, contract, and validation semantics.

The example product is **Task Ledger**:

- a browser UI can create, list, edit, complete, delete, and filter tasks;
- tasks persist across process restarts;
- an HTTP JSON API is supported independently of the browser;
- a command-line interface supports `list` and `export`;
- product verification is owned by the consumer repository.

The example uses Python and SQLite only to make the product decisions concrete. Composition does **not** recommend or select those technologies. A consumer may choose another runtime, framework, database, API implementation, or test system while following the same workflow.

## 1. Choose recipe and capabilities from supported contracts

Start from the externally supported interfaces, not from how many processes, ports, or libraries the implementation happens to use.

| Requirement | Selection | Reason |
| --- | --- | --- |
| Browser product UI | `webapp` recipe baseline | `artifact.webapp-core` already owns browser surfaces, routes, visible states, viewports, and Web-specific validation. |
| Python process and execution commands | `capability.runtime` | The product has an application runtime whose commands/environment need an explicit decision record. |
| Independent HTTP JSON API | `capability.service` | Non-browser callers may use the API without the browser UI. |
| Maintained `list` / `export` CLI | `capability.cli` | The CLI is a supported caller-visible interface. |
| Separate operational/diagnostic browser interface | not selected | The product has no second standalone browser interface beyond its normal Webapp surface. |
| MCP / MCP Apps | not selected | No MCP contract is required. |
| Composition-managed release bundle | not selected | Deployment/release production is outside this small example. |

A shared HTTP listener does not change this selection. If the browser and independent JSON API use the same server process and port, the API is still an independent service contract. Conversely, a private backend-for-frontend route used only by the browser would not by itself justify `capability.service`.

Create `composition.json`:

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

Recipe dependency closure adds the lifecycle components required by the Webapp baseline. Do not manually duplicate required components in `include` merely to document that closure.

## 2. Inspect, plan, apply, and validate

Using the installed Composition runner:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  inspect
```

For a new directory, expect `absent` or `unmanaged`.

Plan before mutation:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  plan --config /path/to/task-ledger/composition.json
```

Review every file action and conflict. For an empty target, normal actions are `create`; byte-identical pre-existing files may be `adopt-identical`. Any conflict must be resolved before apply.

Apply the same intent:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  apply --config /path/to/task-ledger/composition.json
```

Then validate:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  validate
```

At this point the repository is a **valid Composition scaffold**, not an implemented product. For a Webapp whose implementation evidence is still in `template` mode, selected-component validation explicitly defers the product implementation-evidence check while keeping overall Composition validation valid. Human output therefore distinguishes the two facts rather than treating template validity as a product claim.

Conceptually:

```text
PASSED: composition-state (...)
PASSED: webapp-contracts (...)
PASSED: webapp-implementation-coverage (...)
PASSED: contract-evolution (...)
DEFERRED: implementation-evidence (...)
  Implementation evidence is in TEMPLATE mode; no product implementation claim is active. ...
Composition validation: VALID
```

`VALID` here means that the selected Composition state and template contracts are valid. It does not mean that Task Ledger has been implemented, product-tested, deployed, or made release-ready.

## 3. Establish the editing boundary before implementation

Read `.template-composition/lock.json` before editing generated material.

| Ownership | Task Ledger action |
| --- | --- |
| `seed` | Edit and specialize for the product. |
| `managed` | Do not edit directly; Composition remains authoritative. |
| `generated` | Do not edit directly; Composition regenerates deterministically. |
| not present in the lock | Ordinary consumer content unless another repository-local authority says otherwise. |

Typical product work therefore edits seed documents/contracts such as `README.md`, `TEMPLATE.md`, `RUNTIME.md`, `CLI_INTERFACE.md`, `SERVICE_INTERFACE.md`, and Webapp contract JSON, while product source and tests are added as ordinary consumer files.

Do not edit `.template-composition/lock.json` to make a local change appear valid. Do not copy a managed schema or validator into a product-owned variant merely to bypass Composition validation.

## 4. Replace template assumptions with the actual product contract

Keep only contract items the product really implements. Task Ledger can remain deliberately small.

### Browser contract

A minimal concrete inventory can remain close to the seed shape:

| Contract | Product decision |
| --- | --- |
| surface | `primary`: Task Ledger browser UI, local-product audience, non-diagnostic |
| route | `home` at `/`: canonical task-list/editor route |
| states | `ready` plus only additional visible loading/empty/error states that the implementation actually exposes |
| viewport | retain or revise the baseline responsive lower bound and input/zoom behavior to match tested behavior |

Do not add authentication, administration, role-based authorization, touch support, multiple breakpoints, or diagnostic surfaces merely because a larger application might need them.

### Runtime contract

Concretize `RUNTIME.md` with consumer decisions. For this example:

```text
Implementation ecosystem: CPython 3.11+
Persistence: SQLite
Server command: python -m task_ledger.cli --database task-ledger.db serve --host 127.0.0.1 --port 8080
Distribution: source execution for this example
```

These values are product decisions, not Composition defaults.

### Service contract

Concretize `SERVICE_INTERFACE.md` because the JSON API is independently supported. A small contract could include:

```text
GET    /api/tasks?status=all|open|completed
GET    /api/tasks/{id}
POST   /api/tasks
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
GET    /healthz
```

Specify request validation, result/error semantics, size limits, authentication/exposure decisions, readiness/liveness behavior, restart handling, and the relationship to the browser UI. Sharing the same process/listener with the UI does not remove those service obligations.

### CLI contract

Concretize `CLI_INTERFACE.md` for the maintained commands, for example:

```sh
python -m task_ledger.cli --database task-ledger.db list --status all
python -m task_ledger.cli --database task-ledger.db export
```

Document stdout/stderr, exit status, invalid arguments, persistence target selection, and whether CLI operations have semantics equivalent to corresponding API operations.

## 5. Implement in consumer-owned source files

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

Nothing in Composition requires this layout. The important boundary is that these are consumer-owned implementation and verification files, while Composition-owned managed/generated material remains untouched.

The implementation should satisfy the contracts rather than merely make the validator green. For Task Ledger that means, at minimum, demonstrating:

- create/list/edit/complete/delete behavior;
- open/completed filtering;
- persistence across process restart;
- independent JSON API use;
- CLI `list` and `export`;
- negative input/error cases corresponding to the declared contracts.

## 6. Define one authoritative consumer verification command

Composition does not choose the product test runner. Task Ledger may define:

```sh
./scripts/verify.sh
```

For example, that command can run unit/integration tests and any deterministic product checks required by the repository. Keep it independently runnable: implementation evidence should point to a real consumer command rather than to an informal claim that testing occurred.

Before recording product evidence, run the command and fix failures. Composition validation is not a substitute for this product verification command.

## 7. Generate the current evidence worklist

Do not invent evidence target IDs by hand. The Webapp scaffold includes the read-only deterministic worklist generator:

```sh
python scripts/scaffold_webapp_evidence.py > /tmp/webapp-evidence-worklist.json
```

The command does not mutate `contracts/implementation-evidence.json`. It derives the current Webapp evidence targets from the actual consumer contracts, so adding/removing surfaces, routes, states, or viewports changes the worklist deterministically.

Use the worklist as a checklist for product evidence authoring. For every current target, identify:

- the concrete implementation boundary;
- at least one positive proof;
- at least one negative proof;
- the authoritative command that produces those proofs;
- a release gate that executes the referenced command.

Multiple records may reuse the same authoritative command and release gate when one test suite genuinely proves multiple contract targets. Do not create artificial one-command-per-record duplication.

## 8. Switch implementation evidence to product mode only after proof exists

The initial evidence document is intentionally:

```json
{
  "$schema": "../schemas/implementation-evidence.schema.json",
  "schemaVersion": 1,
  "mode": "template",
  "commands": [],
  "releaseGates": [],
  "records": []
}
```

After `./scripts/verify.sh` exists and the implementation/proofs are real, change it to `product` mode and fill the worklist-derived records.

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

Each record still needs its exact worklist target, verified implementation-boundary locator, verified positive/negative proof locators, expected results, and the selected gate. Do not copy a sample target from this guide because the authoritative target set belongs to the consumer repository.

Now rerun both verification layers:

```sh
./scripts/verify.sh
python .template-composition/validate.py .
```

For a valid product-mode document, `implementation-evidence` is executed rather than deferred. The Composition validator verifies the closed contract/evidence relationships; `./scripts/verify.sh` verifies the product behavior. Both are required for the claim represented by this example.

## 9. Adopt coding-agent Policy explicitly when desired

Policy is a separate authority, not a Composition capability. If Task Ledger will be maintained by coding agents, follow the Policy getting-started workflow after Composition has materialized and transferred its seed files to consumer ownership.

The resulting repository has independent managed states:

```text
Composition initial
  -> consumer-owned seed/product implementation
  -> explicit Policy adoption
  -> Composition validation + Policy validation/check + product verification
```

Do not add a fictitious `capability.policy` to `composition.json`, and do not make Composition own `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`.

## 10. Make ordinary product changes without invoking Composition update

Adding a Task Ledger feature, changing SQLite queries, editing consumer-owned seed contracts, or adding product tests is ordinary repository work. It does not require a Composition `update` merely because the product changed.

After a product change:

1. update the consumer-owned contracts/evidence truthfully;
2. run `./scripts/verify.sh`;
3. run Composition validation;
4. run Policy validation/check if Policy is adopted.

Use Composition lifecycle operations only when the Composition source/intent itself changes.

## 11. Update or upgrade Composition later

When a newer reviewed Composition revision is available, first inspect the repository.

For unchanged intent and no component-version boundary:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  plan --mode update

python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  apply --mode update
```

Review the plan before apply. Consumer-owned seed changes are preserved; clean managed/generated materials may be replaced or removed according to the plan.

If the plan reports `COMPONENT_VERSION_UPGRADE_REQUIRED`, or if Task Ledger intentionally changes recipe/components/parameters, make the boundary explicit:

```sh
python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  plan --mode upgrade --config /path/to/task-ledger/composition.json

python /path/to/agent-skills/composition/scripts/run.py \
  --repository /path/to/task-ledger \
  apply --mode upgrade --config /path/to/task-ledger/composition.json
```

Then rerun product verification and Composition validation. Do not edit lock metadata to turn an update conflict into an apparent success.

## Completion checklist

For this example, the repository is no longer merely a valid scaffold when all of the following are true:

- the selected capabilities match the supported caller-visible interfaces;
- consumer-owned contract seeds describe the implemented product rather than template assumptions;
- product source and tests exist in consumer-owned files;
- the authoritative product verification command passes;
- implementation evidence is in `product` mode with complete worklist coverage and real positive/negative proofs;
- Composition validation passes with `implementation-evidence` executed rather than template-deferred;
- optional Policy state is independently valid if Policy was adopted.

This is intentionally stronger than “Composition validation returned valid immediately after apply.” The initial template-valid state is a safe starting point; the completed product claim belongs to the consumer and must be backed by implementation and evidence.