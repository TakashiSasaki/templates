# Documentation publication maintenance

The `skill` branch owns the canonical public-document set and canonical terminology input declared in `docs/publication-catalog.json`. The unrelated `site` branch consumes that catalog together with the catalogs from other publication branches when assembling the GitHub Pages portal.

## Responsibility boundary

`skill` owns:

- stable document IDs within the `skill` publication namespace;
- canonical repository-relative Markdown source paths;
- whether a source may be absent in a reduced publication checkout;
- the single document that serves as the `skill` publication landing page;
- the canonical `docs/glossary.yml` terminology source when declared; and
- the distinction between the complete source repository and the copyable `template/` artifact.

`site` owns:

- the combined portal home page;
- navigation hierarchy and ordering across publications;
- reader-facing navigation titles;
- generated destination paths;
- full-SHA source locking;
- publication assembly, integrated glossary generation, repository-tree rendering, provenance, link validation, and deployment; and
- the dedicated copyable-template tree page.

The catalog field `home: true` identifies the landing document for the Skill publication. It does not select the home page of the combined Pages site.

Do not define a second independent Skill document or terminology source list on `site`. Site-specific configuration may arrange catalog documents and integrate declared glossary entries but must not silently add, omit, or reinterpret provider-owned canonical inputs.

## Canonical source boundary

The source-product overview is root `README.md`. Consumer-facing contracts and guidance resolve below `template/`, including `template/SKILL.md`, runtime and interface contracts, profile guidance, and architecture material intended for a concrete Skill developer.

The publication catalog, `docs/glossary.yml`, source architecture records, maintainer documentation, fixtures, validators, and workflows are maintainer-owned source material and are not part of the copyable template. `distribution-manifest.json` records this boundary explicitly.

Stable document IDs are preserved when a canonical source path moves. For example, moving `SKILL.md` to `template/SKILL.md` changes the source path but does not change the cross-publication identity `skill:skill-contract`.

## Catalog schema

The provider validator accepts catalog schema versions `1` and `3`. Version `1` is the legacy document-only form. Version `3` retains the same document contract and may additionally declare one canonical glossary source:

```json
{
  "schema_version": 3,
  "documents": [
    {
      "id": "overview",
      "source": "README.md",
      "optional": false,
      "home": true
    }
  ],
  "glossary": {
    "source": "docs/glossary.yml"
  }
}
```

Each document object has exactly:

- `id`: a unique lowercase kebab-case identifier that remains stable across source renames;
- `source`: a unique safe relative POSIX path to an existing regular Markdown file under the source checkout;
- `optional`: whether an assembler may skip the document when the source is absent from a reduced publication tree;
- `home`: whether the document is the Skill publication landing page; exactly one non-optional document is the landing page.

The effective cross-publication document identity is `skill:<document-id>`. Another publication may use the same local document ID without creating a collision.

In schema version `3`, `glossary` is optional and, when present, contains exactly `source`. The source must be a safe relative `.yml` path to an existing regular file within the reviewed Skill checkout and must not traverse a symbolic link. Individual terms are maintained inside that YAML file and are not enumerated in the publication catalog.

English remains canonical for glossary definitions. Localized lexical labels such as Japanese preferred terms or aliases are discovery metadata only and resolve to the same stable term ID and English meaning.

Catalog and glossary-source paths must not be absolute, traverse `.` or `..`, contain backslashes, enter a `.git` component, traverse symbolic links, or escape the reviewed source checkout.

## Glossary validation boundary

The branch-local catalog validator validates the catalog declaration and glossary source path. It deliberately does not duplicate the repository-wide glossary semantic parser from `site`.

A Skill pull request that changes `docs/**` runs the build-only Site compatibility workflow using the current `site` implementation. That workflow is the canonical semantic validator for `docs/glossary.yml`: it validates glossary schema version, term-ID namespaces, origin-specific fields, localized labels, related-term resolution, external authority metadata, cross-provider uniqueness, and exact revision provenance. This division avoids maintaining a second glossary semantics implementation on the Skill branch while still making glossary semantic validation mandatory for provider changes.

## Change process

When a public canonical document or glossary term is added, removed, or moved:

1. update the canonical provider source and, when the publication boundary changes, `docs/publication-catalog.json` in the same `skill` pull request;
2. preserve existing document IDs and glossary term IDs across source or label changes unless the underlying concept itself changes;
3. run Skill catalog validation and the build-only `site` compatibility workflow against the proposed Skill revision;
4. merge the reviewed Skill pull request and record its full merge commit SHA;
5. create a separate pull request on unrelated `site` history;
6. update `publication-sources.json` to the reviewed Skill full SHA;
7. update site navigation only when document identities or intended placement require it;
8. generate both the complete Skill source tree and the dedicated `template/` copyable tree;
9. require strict site tests, assembly, glossary integration, build, provenance, and link validation to pass; and
10. merge the coordinated Site update only after the locked provider revision is validated.

Because `skill` and `site` have unrelated histories, do not merge, rebase, or cherry-pick between them. Record dependency, reviewed SHA, and merge order in both pull-request bodies.

## Repository-tree publication

The integrated site must expose two distinct Skill views:

- the complete `skill` source tree, including maintainer infrastructure; and
- the copyable `template/` tree, rooted at the exact locked Skill revision.

The copyable page must identify `template/` as the copyable root, preserve source links at the locked full SHA, and exclude source-only fixtures, glossary data, or workflows by selecting the tracked subtree rather than filtering a rendered complete tree.

Inline file previews belong to the complete source-tree publication unless the site explicitly defines a separate bounded preview contract for the copyable page. The copyable page must not imply that source-only fixtures or workflows are copied into a Skill.

## Validation

Run on `skill` with Python 3.12 available as `python3.12`:

```sh
python3.12 .github/scripts/test_publication_catalog.py
python3.12 .github/scripts/test_publication_schema_version.py
python3.12 .github/scripts/test_publication_catalog_root_resolution.py
python3.12 .github/scripts/validate_publication_catalog.py
python3.12 .github/scripts/test_restructure_completion.py
```

All branch-local publication and restructuring checks above are Python-only. A Skill pull request that changes `README.md`, `docs/**`, `template/**`, or `.github/workflows/pages.yml` also runs the build-only Site compatibility workflow. Publication work is not complete until both provider-local validation and the corresponding locked-revision Site integration pass.
