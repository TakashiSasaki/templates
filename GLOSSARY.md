# Glossary contract

This document defines the canonical terminology contract used by the unrelated `site`, `skill`, `policy`, and `webapp` branch histories in `TakashiSasaki/templates`.

The glossary is a machine-readable semantic contract. It is intentionally separate from any future glossary user interface. Provider branches own canonical terminology, while `site` validates and integrates the provider-owned sources into one deterministic read model.

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

The Site build reads glossary inputs from the same checked-out provider revisions used for the rest of the integrated publication. It produces:

```text
/glossary/index.json
```

Each integrated term records derived provenance including:

- `provider`;
- `source_path`;
- `source_revision` as a full lowercase Git commit SHA.

Terms are emitted in stable ID order. Duplicate term IDs and unresolved `related_terms` fail the build closed. The generated JSON retains localized labels losslessly enough for a future search or user interface to build reverse lookups without changing the canonical glossary schema.

## Adding terminology later

The initial glossary is only a seed, not a closed vocabulary. A later terminology change normally consists of editing the semantic owner's `docs/glossary.yml` and passing provider-local and Site integration validation.

Adding a new term or adding a Japanese label to an existing term does not normally require:

- a glossary schema change;
- a publication-catalog change;
- a Site implementation change;
- a user-interface change.

The Site publication lock is updated through the normal reviewed provider-revision promotion process before the new terminology appears in the integrated publication.

## Out of scope for this contract

This contract does not define the human glossary page, search normalization, fuzzy search, language filters, inline term linking, tooltips, localized explanatory prose, or online authority-link monitoring. Those features may be designed later on top of the stable term IDs and integrated machine-readable model.
