# Glossary contract

This document defines the canonical terminology contract used by the unrelated `site`, `skill`, `policy`, and `webapp` branch histories in `TakashiSasaki/templates`.

The glossary is a machine-readable semantic contract whose meaning is independent of any particular user interface. Provider branches own canonical terminology, while `site` validates and integrates the provider-owned sources into one deterministic read model. The Site publication also renders a non-authoritative human projection of that same integrated model at `/glossary/`.

## Canonical language and localized labels

English is the canonical language for glossary terms and explanatory prose, consistent with `LANGUAGE.md`.

A glossary entry may carry localized lexical metadata under `localized_labels`. Localized labels are discovery aids only. They do not define or translate the meaning of the concept. In particular, a Japanese preferred term or alias resolves to the same stable term ID as the canonical English term and therefore to the canonical English definition or summary.

`localized_labels` entries may contain only:

- `term`: the preferred label in that language;
- `aliases`: optional alternative labels in that language.

English labels must use the top-level `term` and `aliases`; `localized_labels.en` and `localized_labels.en-*` are invalid.

Language keys use BCP-47-like tags and are serialized with stable casing. Natural-language labels are not globally unique: the same Japanese or English label may identify multiple concepts. Consumers must therefore treat a label lookup as potentially returning multiple term IDs.

## Source and publication declaration

A primary branch may own one canonical glossary at:

```text
docs/glossary.yml
```

A glossary is a publication input only when the provider declares it in publication-catalog schema version 3. For example, a provider whose required home document is `docs/index.md` may declare:

```json
{
  "schema_version": 3,
  "documents": [
    {
      "id": "index",
      "source": "docs/index.md",
      "optional": false,
      "home": true
    }
  ],
  "glossary": {
    "source": "docs/glossary.yml"
  }
}
```

The `glossary` member is optional. If it is present, its `source` is required and must resolve to an existing regular `.yml` file within the provider publication root without traversing symlinks. A declared glossary source must not overlap a declared asset source; the canonical semantic source is not also published as an untyped raw asset.

Individual terms are not listed in the publication catalog. Adding a term therefore does not require a catalog-schema or Site implementation change.

## Glossary schema version 1

A repository-defined term has this shape:

```yaml
schema_version: 1
terms:
  - id: templates-provider-branch
    term: Provider branch
    localized_labels:
      ja:
        term: プロバイダーブランチ
        aliases:
          - 提供ブランチ
    origin: repository
    definition: >-
      A primary branch that owns canonical content consumed by the integrated
      publication system.
```

An externally defined term has this shape:

```yaml
schema_version: 1
terms:
  - id: external-git-branch
    term: Branch
    localized_labels:
      ja:
        term: ブランチ
    origin: external
    summary: >-
      A named line of development represented through Git references.
    authority:
      kind: upstream
      sources:
        - title: Git glossary
          url: https://git-scm.com/docs/gitglossary
```

All entries require `id`, `term`, and `origin`.

Repository-defined entries:

- use a `templates-<slug>` ID;
- require `definition`, which is the canonical repository meaning;
- may optionally include `summary` as a simplified English explanation, but that summary does not replace or weaken the canonical `definition`;
- must not declare `authority`.

Externally defined entries:

- use an `external-<domain>-<slug>` ID;
- require a repository-authored `summary`;
- require `authority`;
- must not declare a repository-authored `definition`.

Optional common metadata includes `aliases`, `localized_labels`, `repository_usage`, and `related_terms`. A term must not list itself in `related_terms`; all related IDs must resolve in the integrated glossary.

### Cross-provider related terms

`related_terms` is federated stable-ID navigation metadata, not a provider-local ownership declaration and not a typed ontology. A provider-local `docs/glossary.yml` may therefore reference a stable term ID canonically owned by another provider. Provider-local glossary files are not required to be closed under `related_terms`.

A cross-provider target must remain defined only by its canonical owner. The referring provider must not copy the target term definition into its own glossary merely to make the reference locally resolvable; doing so would create a duplicate global term ID and violate single-owner terminology semantics.

Provider-local publication-catalog validators continue to validate declaration and path boundaries rather than duplicating the repository-wide glossary semantic parser. The Site integration step resolves every `related_terms` ID against the exact locked provider revisions and fails closed when a target is absent, duplicated, malformed, or self-referential.

Cross-provider relations should remain sparse. A relation is appropriate when it materially helps distinguish easily confused peer concepts or connects a concrete provider concept to a clearly applicable canonical classification. Relations need not be symmetric: peer disambiguation may be reciprocal, while concrete-to-generic classification links normally point from the concrete concept to the generic one so generic taxonomy terms do not become open-ended instance registries.

These directionality and symmetry guidelines are maintainer authoring conventions, not additional parser semantics. The Site integration parser resolves the stable IDs exactly as declared and does not infer, add, remove, reverse, or otherwise normalize relation directionality.

## External authority

External authority is represented as:

```yaml
authority:
  kind: normative
  sources:
    - title: Example specification
      url: https://example.com/specification
      version: optional-version
      locator: optional-section
```

`kind` is one of:

- `normative`: a specification or other normative source;
- `upstream`: official documentation maintained by the technology or product owner;
- `conventional`: a primary or high-quality reference for terminology that has no single normative source.

Authority URLs must be absolute HTTPS URLs without embedded credentials. Site builds validate the URL structure but do not fetch authority URLs, so reproducible publication does not depend on external network availability.

## Ownership and stable identity

A repository-defined concept has one canonical owner. Ownership is derived from the provider branch containing the canonical glossary entry and is not duplicated in authored YAML.

The stable term ID identifies the concept, not its current display label, current owner, current authority URL, or source path. Term IDs are globally unique in the integrated glossary and must not be reassigned to a different concept.

External entries are curated by the provider that stores them, but semantic authority remains external.

## Strict source rules

Glossary YAML is treated as data, not executable configuration. The validator requires UTF-8 and rejects, among other invalid constructs:

- duplicate mapping keys;
- non-string mapping keys;
- YAML anchors and aliases;
- YAML merge keys;
- custom YAML tags;
- disallowed control characters;
- unknown schema fields;
- invalid origin-specific field combinations;
- unsafe glossary paths and symlink traversal.

## Integrated publication

The Site build reads glossary inputs from the same checked-out provider revisions used for the rest of the integrated publication. It produces two stable representations of the same integrated glossary:

```text
/glossary/index.json
/glossary/
```

`/glossary/index.json` is the schema-versioned machine-readable read model. `/glossary/` is a generated human-readable projection of that model. The HTML projection is not a second terminology authority and must not redefine, infer, or independently translate glossary semantics.

Each integrated term records derived provenance including:

- `provider`;
- `source_path`;
- `source_revision` as a full lowercase Git commit SHA.

Terms are emitted in stable ID order. Duplicate term IDs and unresolved `related_terms` fail the build closed. The generated JSON retains localized labels losslessly enough for search or later interactive presentation without changing the canonical glossary schema.

## Human presentation

The Site glossary viewer follows these presentation rules:

- canonical English terms and definitions remain the semantic source shown to readers;
- localized labels such as Japanese preferred terms and aliases are displayed as lexical lookup aids only;
- repository-defined terms are separated from externally defined terms;
- repository-defined terms are grouped by their canonical provider owner;
- externally defined terms retain visible links to their declared external authority;
- each term exposes its stable term ID and immutable provider-source provenance;
- `related_terms` are rendered through stable term-ID links rather than label-based inference;
- all glossary-provided text is escaped before HTML rendering;
- the generated page executes no glossary-supplied JavaScript.

The current viewer is intentionally static. Its existence does not make search normalization, fuzzy matching, filtering, or localization rules part of glossary schema version 1.

## Adding terminology later

The initial glossary is only a seed, not a closed vocabulary. A later terminology change normally consists of editing the semantic owner's `docs/glossary.yml` and passing provider-local and Site integration validation.

Adding a new term or adding a Japanese label to an existing term does not normally require:

- a glossary schema change;
- a publication-catalog change;
- a Site implementation change; or
- a user-interface change.

The Site publication lock is updated through the normal reviewed provider-revision promotion process before the new terminology appears in the integrated publication.

## Out of scope for this contract

This contract does not define search normalization, fuzzy search, language filters, inline term linking outside the glossary page, tooltips, localized explanatory prose, or online authority-link monitoring. Those features may be designed later on top of the stable term IDs and integrated machine-readable model.
