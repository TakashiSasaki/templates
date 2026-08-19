# Composition publication boundary

The `composition` branch owns one provider publication boundary for the reusable composition system. It replaces the former assumption that Skill and Webapp documentation must be published from two independent template authorities.

## Reader-facing boundary

`docs/publication-catalog.json` is a schema-version-3 allowlist. It publishes explanatory Markdown for:

- composition architecture and the deterministic composer;
- the Agent Skill artifact model;
- the Web application artifact model;
- reusable runtime, CLI, MCP, MCP Apps, browser, and service capabilities;
- reusable composition-state, contract-evolution, implementation-evidence, release-evidence, and release-bundle lifecycle contracts; and
- migration material needed to understand why former monolithic Skill/Webapp responsibilities moved to their present authorities.

The publication home is the branch `README.md`. `docs/index.md` is the provider-owned progressive-disclosure root used by guided navigation.

## Machine-readable boundary

Machine-readable source authorities are published as supporting assets rather than rendered documentation. The catalog includes:

- `catalog/catalog.json`;
- both production recipes;
- every top-level composition JSON Schema;
- every production component descriptor;
- Webapp domain contract/schema seeds;
- reusable lifecycle contract/schema seeds; and
- the consumer composition-lock schema.

A machine-readable file is not public merely because it exists in the branch. It must be covered by an explicit asset entry.

`contracts/manifest.json` is deliberately absent from the source publication assets. It is a deterministic **generated consumer material** owned by `lifecycle.contract-evolution`; no canonical source file exists in the composition checkout. The publication instead exposes the component registrations and schemas from which the composer generates the manifest.

## Authority and URL model

The provider identity is `composition`. Skill and Webapp remain distinct artifact semantics inside that provider, not independent source authorities. Site integration may group their documents separately for readers, but it must not reconstruct separate canonical Skill/Webapp source ownership.

This repository is not yet production-facing, so the composition migration does not preserve the former provider URL namespace merely for backward compatibility. Site information architecture is a Site-owned concern and is handled separately from this provider allowlist.

## Glossary ownership

`docs/glossary.yml` is the composition-owned terminology source. It retains `templates-skill-profile` because Policy legitimately relates Policy profiles to Skill profiles, but definitions that depended on the retired copyable-template architecture are not preserved. Generic composition/lifecycle concepts use composition-owned IDs rather than being mislabeled as Webapp-only or Skill-only concepts.

The glossary file is encoded as strict JSON, which is a valid YAML 1.2 subset. This lets composition validate it with the Python standard library while remaining compatible with the Site glossary reader.

## Local validation

Run:

```sh
python scripts/validate_publication.py
```

Validation is fail-closed for unsafe paths, symbolic-link traversal, duplicate IDs/sources/destinations, undeclared reader documentation, missing production descriptors/schemas/recipes, Markdown hidden inside asset trees, malformed glossary records, and obsolete glossary IDs that would reintroduce the retired copyable-template model.

Site PR #270 completed the publication cutover by locking and consuming an exact reviewed Composition revision. Subsequent Composition publication changes require an explicit reviewed Site pin-forward rather than any mutable branch reference.
