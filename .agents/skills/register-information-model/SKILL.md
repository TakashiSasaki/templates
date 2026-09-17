---
name: register-information-model
description: Register or revise an information-model resource while preserving normative ownership, source language, version identity, provenance, rights, and deterministic offline discovery projections.
---

# Register an information model

This is an English, branch-local intake procedure. It applies the Models contract; it is not a replacement for Policy's general orchestration procedures. Paths below are relative to the Models branch root.

## Read before editing

Read `AGENTS.md`, `AUTHORITY.md`, `docs/record-model.md`, `docs/source-policy.md`, and `docs/intake.md`. Inspect `schemas/resource-record-0.1.schema.json` and the relevant current records. Check live branch/head, affected PRs, and the actual independent history before mutation.

## Determine the contribution's owner

An external standard gets an external record, not a local normative owner. A local definition requires an explicit decision-rights statement. A local profile owns its restrictions, not its bases. A local mapping owns its assertions, not either endpoint. An existing Composition/Policy/Integration/Site contract stays with that semantic owner. Browser presentation belongs to Site; a model-specific headless reference implementation may belong here.

Do not force an unrepresentable concept into a misleading record. The 0.1 record format is a constrained administrative profile, not a complete RDF ontology or snapshot/package manager. New canonical languages, non-HTTP identifiers, externally cached bytes, aliases, new collection kinds, and adoption state need an explicit profile extension and tests where unsupported. Do not bypass restrictions by calling an external resource local.

## Record primary-source evidence

Find the publisher's normative source, identify its canonical language, and distinguish identity from an entrypoint. Retain the upstream version/edition label. A document page, machine schema, ontology, print edition, and subset are not automatically equivalent serializations. Use the NDC and PREMIS entries as boundary examples, not as universal templates.

For each source, record exactly what was inspected. Use `metadata-observed` only for a real source inspection and record its observation date and bounded scope. Use `reference-not-verified` with `observedOn: null` otherwise. Page inspection never establishes a byte pin, legal clearance, a current-latest guarantee, or executable conformance.

External content is reference-only in this profile. Check distribution-specific rights, but do not invent a license identifier. `not-assessed` is honest uncertainty, not a permission grant. Do not copy full standards or classification databases as a shortcut.

## Author and connect the record

Create or revise one `records/<id>.json`. Preserve `resourceId` while correcting descriptive metadata unless identity actually changes; increment `recordRevision` for an existing record. Set `recordAuthority: models` independently of `normativeAuthority`. Supply canonical-language title, description, notes, provenance scope, and corresponding source references.

Reuse established predicates only when their real meanings fit. Keep reference, import, profile, restriction, equivalence, SKOS matching, mapping, derivation, supersession, requirement, and membership distinct. Attribute a local assertion explicitly. Bind version-sensitive claims to subject/object editions. Normative claims require inspected evidence and still need semantic review; a green metadata validator is not a proof of profile conformance or mapping correctness.

Add discovery collection membership only when thematically justified. A resource can be found without membership in the initial collection. Membership is not dependency, endorsement, or adoption.

## Validate before requesting CI

Use the supported Python 3.11 environment and installed pinned development dependencies:

```sh
python -m pip install -r requirements-dev.txt
python tools/catalog.py generate
python tools/qualify.py
```

After installation these commands do not retrieve upstream definitions. Review the source diff and generated diff together. The generator must not update observations, clocks, licenses, or upstream bytes. Do not edit `CATALOG.md`, `catalog.json`, or `docs/resources/*.md` by hand.

Add focused positive and negative tests for new invariants. Recheck exact-head CI separately from local results. Report unavailable runtimes and incomplete checks rather than equating them with passes.

## Handoff

Use the repository's stacked-PR workflow, durable PR checkpoints, and one final whole-stack diagnostic review as instructed in `AGENTS.md`. Do not merge or enable Integration/Site adoption without authorization. Include source verification limits, canonical language, rights uncertainty, exact tested head, next safe action, and stop boundary in the handoff.
