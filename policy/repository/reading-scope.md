---
id: webapp-source.read-authoritative-webapp-contracts
severity: mandatory
overridable: true
order: 1020
---
# Read authoritative Webapp contracts for affected domains

Always read `README.md`, `template/TEMPLATE.md`, `template/docs/architecture/responsibility-boundaries.md`, and files directly named by the task.

For a contract-family change, read `template/contracts/manifest.json` and the corresponding architecture, schema, validator, migration, test, and evidence documents below `template/` for that family. Treat those artifact documents as the normative authority for Webapp semantics; repository policy may reference them but must not silently replace them.

Read source-only topology, publication, distribution-boundary, and maintainer-policy documents outside `template/` when the task affects template maintenance or publication rather than the copied Webapp artifact itself.
