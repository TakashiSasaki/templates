# Website product walkthrough

This is the canonical first-use walkthrough for creating a content-oriented Website with Composition. Use it when the supported browser product is primarily documents/content that people discover, navigate, read, and share. If the product is primarily interactive tasks performed through application state and recoverable UI states, use the [Webapp product walkthrough](webapp-product-walkthrough.md) instead. The [Website or Web application guide](website-webapp-selection.md) explains the boundary.

The example product is **Project Docs**, a small documentation Website with a home page and a guide page. It deliberately has no application surfaces, task state, maintained runtime, or PWA behavior. Those are not prerequisites for Website identity.

## Completion path at a glance

1. **Doctor** — verify the installed Composition runner against the immutable Website-capable revision used by this walkthrough.
2. **Inspect** — confirm the target is unmanaged.
3. **Plan** — resolve the `website` recipe without mutating the repository.
4. **Review** — verify the artifact, transitive foundation, actions, and conflicts.
5. **Apply** — materialize the reviewed Website scaffold.
6. **Validate scaffold** — treat initial `VALID` as a scaffold milestone only.
7. **Define Website contract** — make routes, page structure, document metadata, discovery, and viewport intent truthful for Project Docs.
8. **Define planning evidence** — record stable requirements and required proof kinds before making product claims.
9. **Checkpoint planning** — validate the planning state and execute the machine-projected planning checkpoint action before implementation begins.
10. **Implement content and presentation** — create the consumer-owned HTML/CSS/assets or equivalent implementation, including the declared browser identity asset.
11. **Run product and browser proof** — prove generated/reachable content and the browser-sensitive Website targets with real browser-backed evidence.
12. **Populate and validate product evidence** — connect proof commands and records, switch implementation evidence to `product` only when truthful, and validate against the preserved planning baseline.
13. **Checkpoint product** — execute the machine-projected product checkpoint action and revalidate the closed lifecycle transition.
14. **Optional capabilities** — add PWA/runtime/service/interface/release-bundle behavior only when the product actually supports or needs it.
15. **Evaluate release readiness** — execute the machine-projected `check-release-readiness` action; deferred required browser proof means `not-ready`.

The key boundary is the same as for other Composition artifacts: **scaffold validity is not product completion**. Website product evidence must describe the implemented Website, not merely restate the contract files.

## 0. What this walkthrough will produce

Create Project Docs in a separate consumer repository. Do not clone `TakashiSasaki/templates` merely to use Composition, and do not implement the Website inside the provider repository.

```text
TakashiSasaki/templates
        |
        | provides Composition tooling and Website contracts
        v
your separate project-docs repository
```

The minimal path is:

```text
create repository
  ↓
install Composition + doctor against immutable Website revision
  ↓
composition.json (`website`)
  ↓
inspect → plan → review → apply → validate
  ↓
valid Website scaffold
  ↓
truthful Website contracts + planning evidence
  ↓
validate planning → planning checkpoint
  ↓
consumer-owned Website implementation
  ↓
product/browser proof + product evidence
  ↓
validate product → product checkpoint → validate
  ↓
check-release-readiness → ready | not-ready
```

## 1. Create the consumer repository

```sh
mkdir /absolute/path/to/project-docs
cd /absolute/path/to/project-docs
git init
```

The directory is the product repository. Git is normal product tooling; it is not a Composition runner prerequisite.

## 2. Check prerequisites and install Composition

Normal Composition consumption requires CPython 3.11, 3.12, 3.13, or 3.14. Follow the immutable installer procedure in [Using Composition](../consumer-guide.md#install-and-run-the-composition-skill), installing the skill outside Project Docs.

The currently published skill's stable runtime manifest predates the `website` recipe. This walkthrough therefore selects CI-green immutable Website-capable Composition revision `379073f376ce1de80948abd2e92d5560b573e7e6` explicitly. That revision contains the Website recipe and the complete optional component set described in step 14. The installed runner supports this immutable full-SHA override. Use this same revision for **every** runner invocation in this walkthrough; omitting it would fall back to the older stable runtime-manifest revision rather than to the consumer lock.

Run the read-only doctor against that exact revision:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  doctor
```

`READY` means local bootstrap prerequisites are usable for the selected revision. It is not Composition validation and does not prove later network/package availability. Confirm the doctor output identifies `379073f376ce1de80948abd2e92d5560b573e7e6` as the selected toolchain before proceeding.

## 3. Create `composition.json`

Project Docs is content/document-oriented, so select `website`. Static output does not make this choice; the product identity does. No optional component is required for this example.

Create `/absolute/path/to/project-docs/composition.json`:

```json
{
  "schema_version": 1,
  "recipe": "website",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

The same machine-checked example is stored at `examples/onboarding/project-docs/composition.json`.

Do not directly include `foundation.web`; foundations are transitive artifact dependencies. Do not add `artifact.webapp-core`, `capability.runtime`, or `capability.pwa` merely because a Website uses JavaScript, is generated by a tool, or is deployed through a CDN.

## 4. Inspect, plan, review, and apply

Inspect first:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  inspect
```

A fresh directory should report `state: "unmanaged"`.

Plan with an absolute config path:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  plan --config /absolute/path/to/project-docs/composition.json
```

Initial planning is read-only. Before apply, verify that the resolved closure includes:

- `artifact.website-core`;
- transitive `foundation.web`;
- the Website baseline lifecycle components, including `lifecycle.lifecycle-checkpoints`; and
- **not** `artifact.webapp-core`, `capability.pwa`, or `capability.runtime`.

Review every action and require an empty `conflicts` list. Then apply the same intent with the same exact revision:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  apply --config /absolute/path/to/project-docs/composition.json
```

## 5. Validate the scaffold

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  validate
```

A successful result establishes a valid **Website scaffold**. It does **not** establish that Project Docs exists, that its pages render correctly, that browser evidence exists, or that it is release-ready.

Read `.template-composition/lock.json` before editing material. `seed` files become consumer-owned after materialization; `managed`, `generated`, lock, and transaction material remain provider/Composer-owned according to the lock.

## 6. Understand the Website contract boundary

The Website recipe combines two semantic layers.

Shared `foundation.web` owns product-neutral browser contracts:

- `contracts/browser-identity.json`;
- `contracts/routes.json`;
- `contracts/viewports.json`.

`artifact.website-core` owns Website-specific contracts:

- `contracts/site-structure.json`;
- `contracts/document-metadata.json`;
- `contracts/site-discovery.json`.

Project Docs does **not** need Webapp-private `contracts/application-routes.json`, `contracts/surfaces.json`, or `contracts/ui-states.json`. If you find yourself inventing application surfaces or recoverable task states merely to describe a documentation site, re-check the artifact boundary instead of forcing Webapp semantics into the Website.

## 7. Concretize Project Docs

Use two canonical routes:

```text
home  -> /
guide -> /guide
```

Update the consumer-owned seed contracts together so their cross-file authority remains consistent:

- `routes.json`: add canonical route `guide`, with any intentional aliases and accessibility focus target;
- `site-structure.json`: add page `guide`, bind it to route `guide`, and make `home` its parent;
- `document-metadata.json`: set `siteName` to the actual product name `Project Docs`, provide visible non-blank title/description metadata for both pages, and set truthful indexability;
- `site-discovery.json`: keep robots/sitemap paths distinct, include exactly the indexable pages in the sitemap, and use a concrete HTTPS `canonicalOrigin` before claiming product mode;
- `viewports.json`: retain a baseline breakpoint at `minWidthPx: 0` and add only strictly increasing breakpoints that correspond to supported responsive behavior; and
- `browser-identity.json`: keep the seeded `favicon.svg` declaration only if the implementation will actually materialize that asset; otherwise change the consumer-owned seed contract to the real browser identity you will provide.

The seeded `siteName: "Website"` is a scaffold placeholder, not the product identity. Do not enter product mode while that placeholder still names Project Docs.

Route canonical paths and aliases share one URL namespace. Do not assign the same path to multiple route IDs or collide an alias with another canonical path.

## 8. Define planning evidence before product claims

`contracts/implementation-evidence.json` starts as scaffold/template material. Before treating implementation work as satisfying Website requirements, move to truthful `planning` evidence and preserve stable requirement IDs.

Website evidence targets are derived from the current Website/shared contracts. Browser-sensitive targets include browser identity, Website pages, page metadata, viewports, and input capabilities. Planning requirements for those targets must declare a browser-level positive proof kind such as `end-to-end-test` or `accessibility-test`.

For the exact two-page Project Docs baseline in step 7, replace the scaffold evidence file with this planning payload before step 9:

```json
{
  "$schema": "../schemas/implementation-evidence.schema.json",
  "schemaVersion": 6,
  "mode": "planning",
  "commands": [],
  "releaseGates": [],
  "records": [],
  "requirements": [
    {
      "id": "WEBSITE-BROWSER",
      "description": "Project Docs browser-facing Website behavior requires browser-level positive proof.",
      "targets": [
        {"kind": "contract-item", "contractId": "browser_identity", "itemKind": "proof-family", "itemId": "browser-identity"},
        {"kind": "contract-item", "contractId": "document_metadata", "itemKind": "page-metadata", "itemId": "guide"},
        {"kind": "contract-item", "contractId": "document_metadata", "itemKind": "page-metadata", "itemId": "home"},
        {"kind": "contract-item", "contractId": "site_structure", "itemKind": "page", "itemId": "guide"},
        {"kind": "contract-item", "contractId": "site_structure", "itemKind": "page", "itemId": "home"},
        {"kind": "contract-item", "contractId": "viewports", "itemKind": "input-capability", "itemId": "keyboard"},
        {"kind": "contract-item", "contractId": "viewports", "itemKind": "viewport", "itemId": "base"}
      ],
      "recordIds": [],
      "requiredPositiveProofKinds": ["accessibility-test", "end-to-end-test"]
    },
    {
      "id": "WEBSITE-DISCOVERY",
      "description": "Project Docs discovery resources require inspection against the declared public Website contract.",
      "targets": [
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "canonical-origin"},
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "robots"},
        {"kind": "contract-item", "contractId": "site_discovery", "itemKind": "proof-family", "itemId": "sitemap"}
      ],
      "recordIds": [],
      "requiredPositiveProofKinds": ["inspection"]
    }
  ]
}
```

The same payload is stored at `examples/onboarding/project-docs/implementation-evidence.planning.json` and is regression-checked against the Website evidence schema and the Website validator's derived target inventory for this Project Docs baseline. If you add a page, feed, viewport, or input capability beyond the baseline, do **not** reuse the target list unchanged: update planning requirements so every target derived from the current contracts is covered before validating.

Discovery proof families such as canonical origin, robots, sitemap, and feeds still need evidence, but they are not all intrinsically browser-sensitive. Use proof strength appropriate to the observable requirement rather than labelling every check as browser proof.

If the repository also selects another evidence-producing capability later, Website validation owns only Website/shared targets. PWA, runtime, service, or Web-interface evidence remains owned by that component's validator; do not duplicate it as Website evidence.

## 9. Validate planning and create the mandatory planning checkpoint

`artifact.website-core` requires `lifecycle.implementation-evidence`, which transitively requires `lifecycle.lifecycle-checkpoints`. The checkpoint lifecycle is therefore part of the Website baseline, not a conditional extra in this walkthrough.

After the Website contracts and implementation evidence are in truthful `planning` mode, validate **before product implementation begins**:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  validate
```

A successful planning validation must project the planning checkpoint under `lifecycle.next_actions`. Execute the projected `next_action_command.argv` exactly, replacing only declared caller inputs such as the checkpoint ID and supported Python executable. Do not reconstruct `checkpoint.py` syntax from this guide. Do not start implementation until that planning checkpoint has been created successfully; it is the immutable validated baseline against which product mode is checked.

## 10. Implement the Website in consumer-owned files

Create the actual Project Docs product using the implementation approach you choose. A minimal static implementation that keeps the seeded browser identity might use:

```text
index.html
guide/index.html
favicon.svg
assets/site.css
robots.txt
sitemap.xml
```

The seeded `contracts/browser-identity.json` declares `favicon.svg`. Composition does not materialize that consumer product asset for you. Either create a truthful `favicon.svg` at the declared location and reference it from the Website, or change the consumer-owned browser-identity contract before product evidence claims another identity.

An SSR implementation could produce the same supported Website contract. Composition does not prescribe either rendering strategy.

Implementation must make the declared browser behavior real: page titles/descriptions, navigation, canonical paths, responsive behavior, keyboard use, robots/sitemap relations, and declared browser identity must match the contracts.

## 11. Prove the implemented Website

Run ordinary product checks for generated files, links, robots/sitemap consistency, browser-identity assets, and any build pipeline. Separately run **real browser-backed positive and negative proof** for browser-sensitive Website targets.

Examples of browser proof include:

- load `/` and `/guide` in a real browser and verify the expected document identity and main focus target;
- verify the declared favicon/browser identity is actually reachable and used;
- exercise primary navigation with keyboard input;
- verify representative declared viewport behavior without forbidden horizontal scrolling; and
- test a negative route/path case rather than recording only happy-path screenshots.

Source inspection, successful HTTP fetches, unit tests, or contract declarations alone are **not** browser-backed proof. Do not relabel them as `end-to-end-test`. When the environment cannot run the required browser proof, mark it deferred and keep release readiness `NOT READY`.

## 12. Populate product evidence and validate against planning

Only after the implementation boundaries and real proof commands exist should `contracts/implementation-evidence.json` claim `mode: "product"`.

For each required Website target:

- use exactly one current record for the target;
- link browser-sensitive records from at least one requirement;
- provide positive and negative browser-backed evidence where required;
- reference authoritative commands whose execution capabilities include `browser` for browser-level proof; and
- keep unrelated capability records under their own contract IDs rather than copying them into Website targets.

Then rerun product verification and Composition validation against the same exact revision:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  validate
```

Product-mode validation requires the validated planning checkpoint created in step 9 and verifies that stable requirements and required proof kinds still match that planning baseline.

## 13. Create the mandatory product checkpoint and revalidate

After product-mode validation succeeds, follow the product checkpoint entry in `lifecycle.next_actions`. Execute its `next_action_command.argv` exactly; the lifecycle machinery resolves the latest planning checkpoint binding, so do not reconstruct the parent or command ordering from prose.

After the product checkpoint succeeds, run Composition validation once more:

```sh
python /absolute/path/to/agent-skills/composition/scripts/run.py \
  --repository /absolute/path/to/project-docs \
  --revision 379073f376ce1de80948abd2e92d5560b573e7e6 \
  validate
```

This final validation checks the closed planning-to-product lifecycle state. A product that has merely switched evidence to `product` without the required planning baseline or product checkpoint is not complete for this walkthrough.

## 14. Optional PWA, runtime, service, Web-interface, and release-bundle behavior remains optional

At immutable revision `379073f376ce1de80948abd2e92d5560b573e7e6`, the `website` recipe exposes exactly these optional selections:

- `capability.pwa`;
- `capability.runtime`;
- `capability.service`;
- `capability.web-interface`; and
- `lifecycle.release-bundle`.

If Project Docs later supports installability/offline/update behavior, upgrade the intent to include `capability.pwa`. It remains a Website because PWA is a cross-cutting capability. Network-only offline read policies do not require cached-content proof; cached-content/freshness proof families become active only when the selected PWA route policy actually permits cached content.

If the Website has a maintained server runtime, add `capability.runtime`. If it exposes an independently supported non-browser API, add `capability.service`, which brings its runtime dependency transitively. If it exposes a separately supported browser-facing operational or diagnostic interface, add `capability.web-interface`. Select `lifecycle.release-bundle` only when the repository needs that packaging lifecycle. None of those selections changes `artifact.website-core` into `artifact.webapp-core`, and selecting the release-bundle lifecycle does not itself establish release readiness.

Use `upgrade`, not ordinary `update`, when intentionally changing the selected component intent. After any upgrade, use the same immutable revision consistently for plan/apply/validate and satisfy the added capability's own contracts and evidence requirements.

## 15. Execute release-readiness evaluation

Ordinary `validate` establishes contract/lifecycle validity but does not substitute for the release-readiness decision. After the product checkpoint and final validation succeed, inspect `lifecycle.next_actions`. It must project the `check-release-readiness` implementation-evidence action when release readiness can be evaluated.

Execute that action's complete `next_action_command.argv` exactly. Do not reconstruct the command from prose. The managed action registry identifies the operation as `check-release-readiness` and its structured output conforms to `.template-composition/implementation-evidence-release-readiness.schema.json`.

Treat the structured `release_readiness` field as authoritative:

- `ready` means there are no blocking conditions;
- `not-ready` means at least one blocking condition remains; and
- a provider/action execution failure is an operational failure, not a successful `not-ready` decision.

Required deferred browser proof must therefore produce or contribute to a `not-ready` result; it must never be silently treated as release-ready. Record the structured result with the release evidence for the product.

## 16. Completion criteria

Project Docs is complete for this walkthrough when all of the following are true:

- the recipe remains `website` and the resolved closure contains `artifact.website-core` + transitive `foundation.web` without Webapp-private artifact contracts;
- every `scripts/run.py` invocation used immutable Website-capable revision `379073f376ce1de80948abd2e92d5560b573e7e6` rather than silently falling back to the older published stable toolchain;
- routes, site structure, metadata, discovery, viewport, and browser-identity contracts describe the implemented Website, including `siteName: "Project Docs"` rather than the seeded placeholder;
- the actual pages/content/navigation and any declared browser-identity asset such as `favicon.svg` exist in consumer-owned implementation files;
- a validated planning checkpoint exists from before product implementation and the final product checkpoint closes that transition;
- required product checks and real browser-backed positive/negative evidence have passed;
- implementation evidence truthfully uses `product` mode and browser-sensitive records are requirement-linked;
- Composition validation passes after the product checkpoint;
- the machine-projected `check-release-readiness` action has actually been executed and its structured result recorded; and
- any required deferred proof keeps `release_readiness` at `not-ready` rather than being silently waived.

For deployment/rendering ambiguity, return to [Choose Website or Web application](website-webapp-selection.md): static versus dynamic is not the classifier.
