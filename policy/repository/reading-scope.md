---
id: webapp-source.read-authoritative-webapp-contracts
severity: mandatory
overridable: true
order: 1020
---
# Read authoritative Webapp contracts for affected domains

Always read `README.md`, `TEMPLATE.md`, `docs/architecture/responsibility-boundaries.md`, and files directly named by the task.

For a contract-family change, read `contracts/manifest.json` and the corresponding architecture, schema, validator, migration, test, and evidence documents for that family. Treat those artifact documents as the normative authority for Webapp semantics; repository policy may reference them but must not silently replace them.
