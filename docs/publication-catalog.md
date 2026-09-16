# Publication catalog

The `policy` branch publishes a branch-owned allowlist of human-readable
documentation, supporting public assets, and canonical terminology input through
`docs/publication-catalog.json`. The independent Integration authority combines this
catalog with Composition into the versioned Publication Bundle. Site remains on
its historical reviewed inputs until explicitly adopted; it alone owns Pages
rendering and deployment. Skill and Web application remain Composition concepts,
not separate provider branches.

## Ownership

`policy` owns each document's stable local ID, canonical Markdown source path,
optionality, the publication landing document, explicit public asset roots, and
its canonical `docs/glossary.yml` terminology source. The effective
cross-branch document identity is `policy:<document-id>`. Glossary term identity
is independent of document identity and follows the repository-wide stable term
ID contract.

`integration` owns the generic schema-v3 publication protocol, public destinations,
semantic navigation, reviewed provider locks and integrated glossary model. Site
owns portal presentation, rendering, browser runtime and Pages deployment. Policy
consumes the generic protocol from a reviewed full Integration commit SHA; it does
not maintain a second parser, path validator or asset-tree implementation.

`policy` continues to run only its branch-local documentation build and must not
gain a Pages deployment route. The catalog field `home: true` identifies the
landing document for the `policy` section. It does not select the global portal
home.

## Canonical language and translations

English is the canonical language for maintained repository documentation and
for glossary definitions. Every document `source` listed in
`docs/publication-catalog.json` therefore identifies an English canonical
document. A translation is a non-authoritative derivative and must not define
independent requirements or override the English source.

Translations mirror the canonical path below `translations/<language>/`. For
example, the Japanese translation of `docs/overview.md` is
`translations/ja/docs/overview.md`. `translations/manifest.json` records each
canonical/translation relationship and the Git blob identity of the canonical
bytes against which the translation was reviewed. Changing canonical bytes
therefore makes the translation record stale until the translation is reviewed
and the synchronization record is deliberately updated.

Glossary `localized_labels` are not translated definitions. They are lexical
discovery metadata that resolve to the same stable term ID and canonical
English meaning.

Translations are not entries in the publication catalog. The Site publication
layer may expose synchronized derivative routes while preserving the one-way
authority relationship and keeping the English document canonical.

## Schema version

The Integration-owned generic publication protocol accepts only integer schema version
`3`. Legacy publication-catalog schema versions `1` and `2` are retired and fail
closed. Schema version `3` defines the current Markdown document and explicit
asset contracts and additionally permits one canonical glossary declaration:

```json
{
  "schema_version": 3,
  "documents": [
    {
      "id": "overview",
      "source": "docs/overview.md",
      "optional": false,
      "home": true
    }
  ],
  "assets": [
    {
      "source": "docs/assets",
      "destination": "assets",
      "optional": false
    }
  ],
  "glossary": {
    "source": "docs/glossary.yml"
  }
}
```

Each document contains exactly `id`, `source`, `optional`, and `home`. A
required document source must identify an existing regular Markdown file. An
optional document source may be absent, but when present it must also be a
regular Markdown file. Exactly one non-optional document is the publication
landing page.

Each schema-v3 asset contains exactly `source`, `destination`, and `optional`.
Asset destinations are relative to the `policy` namespace in the generated
site. Markdown files are forbidden inside asset roots because every published
Markdown page must be named explicitly in `documents`. Asset roots must not
contain a nested `.git` subtree in any letter case.

The optional schema-v3 `glossary` object contains exactly `source`. When
present, it identifies an existing regular `.yml` file within the provider
source root. It must not traverse a symbolic link and must not overlap an asset
source. Individual glossary terms are not catalog entries; adding a term or a
localized lexical label to an already declared glossary does not require a
catalog change.

All source and destination values are portable relative POSIX paths. They may
not be absolute, contain empty, `.` or `..` components, use backslashes or
colons, enter a `.git` subtree in any letter case, traverse symbolic links, or
escape the declared source root.

## Validation

The canonical generic validator is Site's stdlib-only
`integration/publication_contract.py`. Policy documentation CI consumes the exact
implementation merged by Site PR #313 at full commit SHA
`a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d`. The workflow sparse-checks out
that immutable revision and runs it against the Policy source root; it never
executes a mutable `site` branch tip.

For local reproduction, make a separate checkout of that exact Integration revision
available at a path of your choice, then run:

```sh
INTEGRATION_PUBLICATION_PROTOCOL_ROOT=/path/to/integration-checkout-at-a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d
python -I "$INTEGRATION_PUBLICATION_PROTOCOL_ROOT/integration/publication_contract.py" \
  --source-root . \
  --catalog docs/publication-catalog.json
python scripts/validate_translations.py
```

The generic protocol rejects duplicate JSON members, unsupported fields,
unsafe or symbolic-link paths, duplicate IDs and destinations, invalid home
declarations, missing required sources, any catalog schema version other than
integer `3`, malformed glossary declarations, Markdown smuggling through asset
trees, and glossary/asset source overlap. Those rules are defined and tested by
Site rather than copied into Policy.

Policy-owned tests continue to verify Policy-specific declarations and semantics,
including the expected Policy landing document, glossary declaration,
translation relationships, reader/navigation structure, and documentation build
boundary.

The Site build independently parses and validates the glossary content itself,
including its schema, stable term IDs, localized labels, external authority
metadata, cross-provider term-ID uniqueness, related-term resolution, and exact
provider revision provenance.

The translation validator rejects unsafe or unmirrored translation paths,
translations of non-published canonical documents, missing non-authoritative
notices for Japanese translations, duplicate translation declarations, and
translation records whose recorded canonical Git blob no longer matches the
current English source.

When strict exact catalog coverage prevents the provider catalog and active Site
mapping from merging independently, Policy may prove its catalog candidate
against a reviewed full Site commit that contains the corresponding non-active
Integration-owned staging mapping and explicitly select its build-only staging ID. Site
owns the staging mechanics; Policy only declares its provider catalog entry and
consumes that immutable compatibility boundary. After the Policy catalog change
merges, the dependent Site promotion must advance the Policy source lock and
active mapping so ordinary builds pass without staging.

A publication-set change is complete only after both the `policy` pull request
and the dependent `site` pull request pass. The site source lock must record the
reviewed full commit SHA that contains the catalog change.

<a id="deferred-maintainer-publications"></a>

## Maintainer publications

The following existing English sources are active Policy publication entries.
These are stable **Policy-side document IDs and source identities**; Site still
owns their reader destinations, navigation memberships, and the staged-to-active
integration cutover. `docs/publication-catalog.json` remains the sole Policy
publication allowlist.

<!-- deferred-maintainer-publications -->
| Stable document ID | Canonical Policy source | Semantic role and disposition |
| --- | --- | --- |
| `contributing` | `CONTRIBUTING.md` | Contribution entry point for this provider. Links to canonical operating inputs and validation rather than copying their rules. |
| `maintainer-workflow` | `docs/policy-maintainer-workflow.md` | Provider maintenance and self-hosting explanation. Preserves trusted-base authority and reviewed candidate / separate promotion boundaries. |
| `adr-review-authority-and-github-runtime-boundary` | `docs/adr/0008-review-authority-and-github-runtime-boundary.md` | Existing accepted review trust/provenance and GitHub runtime-boundary decision, with its partial supersession by ADR-0009 visible. No replacement ADR. |
| `adr-review-result-representation-boundary` | `docs/adr/0009-review-result-representation-boundary.md` | Existing accepted representation-boundary decision. Supersedes only the listed ADR-0008 representation requirements and preserves the remaining trust machinery. No duplicate decision. |
<!-- /deferred-maintainer-publications -->

All four correspond to the Policy candidates in the landed Site audience design
at [Site revision af55c7dc0176dd24393b4296b43c8e31d6171a11](https://github.com/TakashiSasaki/templates/tree/af55c7dc0176dd24393b4296b43c8e31d6171a11/docs/architecture/audience).
That frozen inventory records historical exposure; this correspondence neither
rewrites it nor imports Site reader taxonomy into Policy. No missing canonical
source needed to be authored for these four identities.

The repository-local [documentation index (source)](https://github.com/TakashiSasaki/templates/blob/policy/docs/index.md)
links the contribution and workflow entry points. The [ADR index](adr/index.md)
links ADR-0008 and ADR-0009 through their canonical relative document paths. The
three published layer indexes retain their catalog-only link contract.

The four mappings are already active in the reviewed Integration bootstrap
snapshot. Candidate compatibility uses that exact Integration contract without
staging or Site rendering. Future new reader destinations require Integration-owned
candidate staging; provider CI must not weaken catalog closure or carry IA mappings.

Integration chooses reader destinations and semantic navigation. Site owns presentation.
Policy owns these sources, identities, semantic roles and
publication eligibility. No portal labels, theme metadata, or audience fields
belong in the Policy catalog. The four canonical sources currently have no
Japanese reader translations; English remains canonical and available as
fallback. Updated Japanese index text remains a non-authoritative overlay with
synchronized canonical blob hashes; future translations follow the existing
manifest/surface rules when eligible.


Provider candidate compatibility uses reviewed Integration `a30699cf7dc56bf3ef7a1b6fd8f6ffd45cdd426d`. The reusable
Integration qualification workflow selects its reviewed companion provider and
qualifies the exact candidate through deterministic Publication Bundle generation.
A successful candidate is compatibility evidence only; Integration promotion is an
explicit later change. Site adoption and deployment remain separate human decisions.
Draft construction does not acquire this release-bound compatibility evidence;
ready candidates and exact merged provider commits do. Integration owns any new
reader destination or staging mapping required by a provider catalog change.
