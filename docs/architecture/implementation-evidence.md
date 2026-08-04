# Implementation evidence

The implementation-evidence contract connects framework-neutral product declarations to repository-local implementation, tests, authoritative commands, and release gates. It does not select a framework, test runner, package manager, runtime, or deployment platform.

## Contract family

`contracts/implementation-evidence.json` is registered as contract family `implementation_evidence` with stable migration slug `implementation-evidence`.

Version 1 covers:

- every declared application surface;
- every canonical route;
- every UI state;
- every viewport;
- every declared input capability; and
- every manifest, active-contract, or retired-contract transition after version 1.

One evidence record owns exactly one target. Missing, duplicate, or unknown targets fail validation.

## Template and product modes

The template ships in `mode: template`.

Template mode is an honest requirement inventory. It records which implementation boundary, positive evidence, negative evidence, and release integration a generated repository must supply. It must not claim concrete source locations, commands, verified results, or release gates.

A generated repository changes the document to `mode: product` only after it has selected its toolchain and can provide real repository-local evidence.

Product mode requires:

- a verified implementation boundary with a concrete repository locator;
- at least one verified positive proof for every target;
- verified negative proofs for security-sensitive, failure-sensitive, and breaking-transition targets;
- an authoritative command for every proof;
- at least one selected release gate for every evidence record; and
- release gates that actually execute every command used by the record's proofs.

The validator rejects unused gates, unused commands, unknown references, and proof commands that are not executed by a selected gate.

## Evidence records

Each record contains:

- a stable record ID;
- one typed target;
- one implementation-boundary declaration;
- positive evidence;
- negative evidence; and
- release-gate references.

A verified implementation boundary uses `locator` to identify a repository-owned component, module, adapter, server boundary, route owner, application shell, migration runner, or equivalent implementation authority. The locator is not required to be a filesystem path, but it must be concrete, reviewable, and stable enough for maintainers to find the responsible implementation.

Each verified proof records:

- `kind`;
- `locator`;
- the authoritative `commandId`;
- the expected observable result; and
- a description of the behavior proved.

A test file alone is not sufficient evidence when the record does not state what result establishes the contract.

## Target types

### Surface

Surface evidence identifies the rendering boundary, audience handling, trusted authentication and authorization enforcement, data-classification behavior, startup dependencies, and diagnostic exposure.

Authenticated or non-public surfaces require negative evidence in product mode.

### Route

Route evidence identifies navigation and presentation ownership, canonical and alias behavior, deep-link handling, browser history intent, authentication return, access-failure behavior, document title, focus target, and declared UI-state rendering.

Routes with required authentication or an applicable access failure require negative evidence. Client-side route names and directory layout are never accepted as trusted authorization evidence.

### UI state

UI-state evidence identifies the route-level or global owner and proves rendering, focus, announcement, and recovery behavior.

Degraded, error, connectivity, and access states require negative evidence so the repository proves that invalid ownership or missing failure preconditions do not render the state incorrectly.

### Viewport and input capability

Viewport evidence proves the declared lower-bound layout behavior, reflow, zoom, orientation independence, and horizontal-scrolling policy.

Input-capability evidence is independent of viewport width. A product must prove that a declared interaction mode can complete applicable workflows without an undeclared mandatory secondary input.

### Contract transition

Transition evidence covers every history entry after version 1, including the manifest bootstrap and retired families.

A breaking transition requires negative evidence for incomplete migration, incompatible consumers, unsafe sequencing, failed rollback, or equivalent release-blocking conditions. The transition record does not replace the deterministic migration document; it connects that document to real product implementation and release evidence.

## Commands and release gates

`commands` assigns stable IDs to authoritative repository commands. The command text is product-owned and may invoke any selected test runner or validation toolchain.

`releaseGates` groups command IDs into checks that block publication or deployment. A record may select more than one gate, but every proof command must be executed by at least one selected gate.

A command that can be run locally but is not part of a release gate is useful diagnostic tooling, not release evidence.

## Validation boundary

`scripts/validate_implementation_evidence.py` validates both standalone and module entry points.

It proves:

- complete target coverage;
- target and identifier uniqueness;
- cross-contract target validity;
- complete transition coverage;
- template-versus-product mode rules;
- command and release-gate reference integrity;
- required negative-evidence coverage; and
- closure between proof commands and selected release gates.

It does not execute product commands, inspect test semantics, determine whether an implementation locator is truthful, or prove that a test result is sufficient. CI executes the declared product commands, and reviewers verify evidence quality.

## Evolution

This family starts at version 1 and therefore has no migration artifact.

Later changes to required target coverage, proof fields, product-mode obligations, negative-evidence rules, or release-gate semantics change accepted documents or implementation obligations and require a version increment under `contract-evolution.md`.
