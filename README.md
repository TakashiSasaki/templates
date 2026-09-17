# Models authority

This independent-root branch owns reusable information models explicitly accepted into its scope. It is not the repository-wide owner of schemas, vocabularies, or executable code.

Read [AUTHORITY.md](AUTHORITY.md) and [AGENTS.md](AGENTS.md) before changing this branch.

## Contents

[Browse the discovery catalog](CATALOG.md), or consume the generated [JSON index](catalog.json). The initial collection contains 30 externally governed resources and the separately described local resource-record schema. Individual source records are in `records/`; the [initial collection](collections/initial-standards.json) is for discovery, not normative adoption.

The record model and its limits are documented in [docs/record-model.md](docs/record-model.md). Read [docs/source-policy.md](docs/source-policy.md) before recording or copying external material. Resource documentation under `docs/resources/` is generated from the records in the canonical source language. NDC is Japanese; English-source entries and the authority contract are English.

External standards remain externally owned. This branch includes descriptions and upstream schema/vocabulary references, **not complete copied standards or classification databases**. A source-page review does not prove a distribution's bytes, license, or conformance. Unverified references remain labeled as such. Local administrative JSON Schemas govern the records, not the external specifications. The records are plain JSON and make no claim of DCAT/ADMS/PROF/JSON-LD conformance.

The [intake procedure](docs/intake.md) and [agent skill](.agents/skills/register-information-model/SKILL.md) describe how to extend the collection without changing upstream ownership or language.

## Local validation

Use the available `python3`. Install the selected tooling once:

```sh
python3 -m pip install -r requirements-dev.txt
python3 tools/qualify.py
```

Validation is offline after installation. Edit records, not generated indexes or resource documentation. Regenerate and recheck:

```sh
python3 tools/catalog.py generate
python3 tools/qualify.py
```

The checker validates both administrative schemas, all records and collection references, ownership, edition/distribution references, scoped provenance, local artifact hashes, and byte-for-byte freshness of generated outputs. It is not an external schema validator or an entailment engine.

## Lifecycle boundary

No existing authority history is imported. No Composition, Policy, Integration, or Site contract is transferred here. Integration adoption, Site publication, and deployment are **not enabled** by creating this authority. Model releases and downstream adoption remain separate explicit decisions.
