# Web application contract worksheet

Use this worksheet when adapting the scaffold to a concrete product. The machine-readable contracts remain authoritative.

## Surface inventory

For each browser-facing surface, identify its audience, authentication and authorization shape, data classification, stability expectation, diagnostics role, and startup dependencies.

## Route inventory

For each canonical route, record its surface owner, aliases, authentication behavior, deep-link/history behavior, access-failure presentation, supported UI states, document-title requirement, and focus target.

## Visible states

Keep the state vocabulary small and reusable. Every route-scoped state must be owned by at least one route. Global states are top-level presentation states and must not be falsely attached to individual routes.

## Responsive and input behavior

Declare viewport lower bounds independently from input capabilities. Do not infer touch, pointer, or keyboard support from screen width. Preserve zoom/reflow and avoid unintended horizontal scrolling.

## Implementation and release evidence

Template mode deliberately contains no implementation claims. Before switching to product mode, run `python scripts/scaffold_webapp_evidence.py` to obtain the deterministic current Webapp target worklist. The command writes only to standard output and does not modify the canonical evidence document.

Use the worklist to identify concrete implementation boundaries, positive and negative proofs, authoritative commands, and release gates. Then switch `contracts/implementation-evidence.json` to product mode and provide one fully verified record for every Webapp target and registered Webapp contract transition before producing release evidence.

## Product-owned decisions

Document framework, package/dependency workflow, backend/API/persistence, authentication provider, deployment topology, browser support, offline/installability behavior, observability, concrete tests, release approval, and deployment verification in product-owned material rather than fabricating template defaults.
