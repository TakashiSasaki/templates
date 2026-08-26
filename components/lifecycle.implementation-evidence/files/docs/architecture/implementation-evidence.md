# Implementation evidence lifecycle

`lifecycle.implementation-evidence` provides an artifact-neutral mechanism connecting explicit product requirements to artifact-defined contract targets, implementation boundaries, positive/negative proofs, authoritative commands, and release gates.

The generic contract does not know Webapp surfaces, routes, UI states, Skill resources, or any other artifact vocabulary. `contract-item` targets carry a contract ID plus artifact-defined `itemKind` and `itemId`; artifact validators own exact coverage rules.

## Requirement ownership

Product-mode `requirements` are the machine-readable entry point for explicit consumer intent. Each requirement has a stable ID and description, and every evidence record names one or more `requirementIds`.

The lifecycle validator deliberately does **not** interpret natural-language descriptions. Its responsibility is graph closure: every declared requirement must reach at least one evidence record, and that record must already satisfy the existing verified boundary → proof → command → release-gate constraints.

Two ownership designs were considered:

1. a separate product-requirements contract plus cross-contract references; and
2. requirements inside `implementation-evidence`.

The second is authoritative because requirement completeness is meaningful specifically at the implementation-evidence/release boundary. A separate contract would duplicate lifecycle ownership and create an additional evolution surface without adding artifact semantics.

Template mode is deliberately empty. A concrete product switches to product mode, declares explicit requirements, and records verified implementation evidence.

## Validation responsibilities

Validation responsibilities are intentionally split rather than duplicated:

- the registered JSON Schema owns document structure and product-mode completeness, including explicit requirements, per-record requirement references, verified implementation-boundary/proof status, required locators, proof kind/command/expected-result fields, and at least one selected release gate per product record;
- `validate_implementation_evidence.py` runs after registered-contract schema validation and owns semantic relationships that JSON Schema cannot express conveniently: unique identities, known requirement references, orphan-requirement rejection, contract-target and transition existence, command/gate references, proof-command execution by selected gates, and unused command/gate detection;
- artifact validators own artifact-specific target coverage and proof-strength rules.

A product document that is structurally incomplete must therefore fail registered-contract schema validation before semantic evidence validation runs. The semantic validator must not introduce additional hidden product-field requirements beyond the registered Schema.

This lifecycle establishes traceability, not semantic understanding. A human or agent still has to enumerate the real product requirements and map each one to evidence that genuinely proves it.
