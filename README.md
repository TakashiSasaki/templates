# Modeling authority

This independent-root branch owns reusable information models explicitly accepted into its scope. It is not the repository-wide owner of schemas, vocabularies, or executable code.

Read [AUTHORITY.md](AUTHORITY.md) and [AGENTS.md](AGENTS.md) before changing this branch.

## Maintain this authority

Read [AGENTS.md](AGENTS.md) and run its local checks. Modeling changes require
no Integration checkout or Site release. Providers own their publication catalogs;
Integration reads them asynchronously and publishes artifacts consumed by Site.
An added catalog document gets a default route without an adoption or pin-update PR.
Keep authority Git histories independent. Consumer runtime release pins remain separate
from documentation publication. See the [maintainer guide](https://github.com/TakashiSasaki/templates/blob/site/docs/maintainer-onboarding.md).

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

`tools/qualify.py` accepts `--jobs N` as the maximum unittest worker budget,
defaults to `1`, and caps effective workers at the measured limit of `4`.
`--jobs 1` is the serial debugging baseline; use `--expected-head SHA` for an
exact, clean-commit qualification.
Projection, distribution, and progressive-discovery checks remain ordered before
the test stage. Only test modules whose source and exact discovered test IDs match
the reviewed manifest can run in deterministic Python `unittest` shards; new or
changed tests stay in the serial lane. The worker option does not replace Modeling's
discovery or validation authority with a shared cross-language runner. Record the
full Modeling SHA with serial and parallel qualification results.

## Lifecycle boundary

Keep authority histories independent. Source records belong to Modeling; Integration
publishes their catalog asynchronously and Site renders the resulting Bundle. A Modeling
change needs no downstream adoption decision or Site checkout.
