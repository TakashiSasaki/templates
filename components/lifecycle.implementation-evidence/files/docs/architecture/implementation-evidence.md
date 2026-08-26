# Implementation evidence lifecycle

`lifecycle.implementation-evidence` provides an artifact-neutral mechanism connecting declared contracts to implementation boundaries, positive/negative proofs, authoritative commands, and release gates.

The generic contract does not know Webapp surfaces, routes, UI states, Skill resources, or any other artifact vocabulary. `contract-item` targets carry a contract ID plus artifact-defined `itemKind` and `itemId`; artifact validators own exact coverage rules.

Template mode is deliberately empty. A concrete product switches to product mode and records verified implementation evidence.

Validation responsibilities are intentionally split rather than duplicated:

- the registered JSON Schema owns document structure and product-mode completeness, including verified implementation-boundary/proof status, required locators, proof kind/command/expected-result fields, and at least one selected release gate per product record;
- `validate_implementation_evidence.py` runs after registered-contract schema validation and owns semantic relationships that JSON Schema cannot express conveniently: unique identities, contract-target and transition existence, command/gate references, proof-command execution by selected gates, and unused command/gate detection;
- artifact validators own artifact-specific target coverage.

A product document that is structurally incomplete must therefore fail registered-contract schema validation before semantic evidence validation runs. The semantic validator must not introduce additional hidden product-field requirements beyond the registered Schema.


## Explicit product requirements

A product may declare explicit requirements in the same canonical document:

```json
{
  "requirements": [
    {
      "id": "browser-severity-filter",
      "description": "Browser UI can filter records by severity.",
      "recordIds": ["browser-severity-filter"]
    }
  ]
}
```

Requirement IDs are stable machine-facing identifiers; their descriptions are intentionally opaque to Composition. Each requirement must reference at least one implementation-evidence record. The existing record rules then require a verified implementation boundary, verified positive and negative proofs, authoritative commands, and a selected release gate. Release production consequently fails closed when a registered requirement has no closed requirement → record → proof → command → gate path.

The requirement ledger is an optional extension for existing product documents so that artifact contracts and their evidence remain independently reusable. Omitting it does not make unregistered natural-language requirements machine-visible; consumers must register every explicit product requirement they want the completion gate to enforce. Template mode must remain empty.
