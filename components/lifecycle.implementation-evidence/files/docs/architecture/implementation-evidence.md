# Implementation evidence lifecycle

`lifecycle.implementation-evidence` provides an artifact-neutral mechanism connecting declared contracts to implementation boundaries, positive/negative proofs, authoritative commands, and release gates.

The generic contract does not know Webapp surfaces, routes, UI states, Skill resources, or any other artifact vocabulary. `contract-item` targets carry a contract ID plus artifact-defined `itemKind` and `itemId`; artifact validators own exact coverage rules.

Template mode is deliberately empty. A concrete product switches to product mode and records verified implementation evidence. Generic validation checks identities/references, contract-target existence, registered transitions, verified evidence fields, command/gate closure, and proof-command execution by selected release gates.
