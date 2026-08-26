# Web application contract worksheet

Use this worksheet when adapting the scaffold to a concrete product. The machine-readable contracts remain authoritative.

The initial Webapp contracts are deliberately minimal seeds: one public browser surface, one root route, one ready state, and one baseline responsive viewport with keyboard support. They do not imply that the product needs authentication, role-based authorization, administration, a status/diagnostic surface, multiple breakpoints, pointer input, or touch input. Add only the surfaces, routes, states, viewports, and input capabilities that the product actually implements, and replace the seed's public-access assumptions when the product handles non-public data or requires authentication.

## Surface inventory

For each browser-facing surface, identify its audience, authentication and authorization shape, data classification, stability expectation, diagnostics role, and surface dependencies.

## Route inventory

For each canonical route, record its surface owner, aliases, authentication behavior, deep-link/history behavior, access-failure behavior and semantic target, supported UI states, document-title requirement, and focus target. For `render-state`, bind the failure to a declared route-scoped access state. For `redirect`, bind it to the semantic destination route; keep concrete URL/query/cookie/session transport product-owned.

Routes schema v3 requires every route to declare a non-blank `accessibility.focusTarget`, so route implementation evidence is browser-sensitive. A route record needs real positive and negative browser-level proof (`end-to-end-test` and/or `accessibility-test`), and every product requirement linked to that route record must declare at least one of those browser-level kinds in `requiredPositiveProofKinds`. Static inspection, HTTP reachability, and process-level integration tests cannot substitute for route-entry focus proof.

## Visible states

Keep the state vocabulary small and reusable. Every route-scoped state must be owned by at least one route. Global states are top-level presentation states and must not be falsely attached to individual routes.

## Responsive and input behavior

Declare viewport lower bounds independently from input capabilities. Do not infer touch, pointer, or keyboard support from screen width. Preserve zoom/reflow and avoid unintended horizontal scrolling.

## Implementation and release evidence

Template mode deliberately contains no implementation claims. Before switching to product mode, run `python scripts/scaffold_webapp_evidence.py` to obtain the deterministic current Webapp target worklist. By default the command writes only to standard output and does not modify the canonical evidence document.

To persist a consumer-owned worklist for editing, use `python scripts/scaffold_webapp_evidence.py --output implementation-evidence-worklist.json`. The output path is resolved from the Webapp repository root, must stay inside that repository, and must name a new file whose parent already exists. The scaffold refuses existing paths and refuses `contracts/implementation-evidence.json`, including equivalent resolved paths, so it cannot silently replace canonical evidence. A failed write removes a newly created partial output.

The generated worklist is still non-canonical and contains TODO placeholders rather than fabricated implementation claims. It projects each current target as `[verified]`, `[missing]`, or `[deferred]` from the canonical document; those labels are a deterministic checklist, not a substitute for validation. Worklist format v2 also exposes `artifactProofRequirements` before any product requirement has been authored. Each entry identifies a browser-sensitive record and states the positive-evidence, negative-evidence, and linked-requirement proof-kind alternatives from which at least one kind is mandatory. Treat these as artifact constraints, not as claims that proof has already run. The v2 projection keeps a browser-sensitive record `[missing]` until both evidence directions contain an allowed kind, keeps a linked requirement `[missing]` until its `requiredPositiveProofKinds` intersects the artifact-mandated set and every linked record contains positive evidence with one of the requirement-declared kinds, and combines record plus requirement status into the top-level `status`. Product mode also exposes `requirementLedgerStatus` and cannot project green while the mandatory requirement ledger is empty; `statusCounts` remains the record count and `requirementStatusCounts` reports requirement-row state separately. Use the worklist to identify concrete implementation boundaries, positive and negative proofs, authoritative commands, and release gates. Capture explicit caller-visible requirements first in `planning` mode with stable IDs, empty `recordIds`, and their required positive proof kinds. Preserve those IDs. Then switch `contracts/implementation-evidence.json` to product mode and provide one fully verified record for every current Webapp target, linking the planned requirements to the records that implement them. Add `contract-transition` evidence only when this consumer actually underwent a registered contract migration; provider history that predates the product is not a fresh-product implementation obligation.

Before claiming the implemented-product milestone, require every projected target to be `[verified]`; treat `[missing]` and `[deferred]` as blockers. Every caller-visible product requirement must have a stable requirement row, linked record IDs, and an appropriate `requiredPositiveProofKinds` declaration. Product verification and Composition validation must pass, and release production additionally requires release-readiness validation with no deferred evidence. The worklist is only a deterministic projection: update the canonical consumer-owned evidence document and rerun validation rather than editing the worklist to make a failing status appear complete. A green worklist is therefore a projection of evidence state, never an independent completion authority.

## Product-owned decisions

Document framework, package/dependency workflow, backend/API/persistence, authentication provider, deployment topology, browser support, offline/installability behavior, observability, concrete tests, release approval, and deployment verification in product-owned material rather than fabricating template defaults.
