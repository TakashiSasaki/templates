# Audience architecture

This is the Site-owned design contract for two reader journeys: **Use templates**
and **Maintain templates**. It specifies future publication projections; it does
not activate them. The current production manifest and provider catalogs remain
authoritative for what is assembled today.

## Normative inputs

1. [Audience model](audience-model.md): audience meaning, authority boundaries,
   canonical identity, navigation context, and presentation requirements.
2. [Target information architecture](target-information-architecture.md): reader
   destinations and shared-service behavior.
3. [Migration matrix](migration-matrix.json): per-document migration decisions,
   current exposure, publication gaps, and exact audited inputs.
4. [Matrix schema](migration-matrix.schema.json): closed inventory structure.

The implementation roadmap added with the validation layer orders the later
authority-specific work. Roadmap scheduling never overrides these definitions
or a provider's semantic authority. Inconsistencies must be resolved by the
owning authority before implementation, not silently inferred from a path name.

## Reproducible evidence boundary

The inventory audit began **2026-09-13 at 05:49:39 UTC**. Live GitHub branch reads
resolved the following exact commits before edits; the open-PR search and
`GET /repos/TakashiSasaki/templates/pulls?state=open&per_page=100` returned no PRs.
This is an audit observation, not a promise about later branch or PR state.

| Authority | Audited revision |
| --- | --- |
| Site | `27e51190a20cd1603247c60d0ed30632c3b5182f` |
| Composition | `0f0c4012818a3b8646ad89fbca7db22c71ad5dd8` |
| Policy | `5574ea46d2076bb1f5c51d4b0e8c9483a17d8fe2` |

Read source evidence with `git show <revision>:<source>` in a clone containing
these objects, or GitHub's `/blob/<revision>/<source>` URLs. The matrix records
each authority's catalog and the Site manifest, provider lock, and generated-tree
preparation input. At this snapshot both provider publication locks equal the
audited provider heads. No production deployment inspection was performed:
"published" here means the exact repository-declared assembly surface.

That surface contains **115 catalog documents** (Site 7, Composition 74, Policy
34), plus **3 generated Site repository-tree documents**, for **118 canonical
document identities**. Translations and guided pages are projections of these
identities, not additional audience-specific documents. Search, Glossary, Source,
previews, and machine provenance are generated services/supporting assets; their
audience behavior is specified in the target IA rather than counted as new
catalog documents. Source visibility does not equal canonical publication.

The matrix also records selected **future publication candidates**, including
existing uncataloged maintenance material and a missing Composition maintainer
overview. Candidate IDs and paths for unwritten material are proposals owned by
the named authority, not newly assigned provider catalog identities.

## Inventory interpretation

`documents[authority][document-id]` is the unique canonical identity. JSON readers
must reject duplicate object members before schema validation; ordinary last-key
wins parsing is not conformant. `status` distinguishes `published`, `generated`,
and `candidate`. `source` is the exact repository path, or null only for an
unwritten candidate. `current_destination` and `current_navigation` record the
audited exposure, not proposed URL moves. Candidates have no current exposure.

`primary_audience` and `additional_audiences` classify reader tasks.
`proposed_navigation` lists audience and label-path memberships; every declared
audience has a membership. Paths begin with a section of the target IA; their
order chooses the default breadcrumb within that audience. A document is never
copied to implement another membership. The root landing retains primary `use`
for inventory completeness but has an explicit neutral-shell exception in the
model. Both journeys link to it through Start here / Maintainer overview.

`provider_action` is `none`, `clarify`, `publish-existing`, or `author-and-publish`.
It records a requested later action by the semantic owner, never permission for
Site to edit provider prose. For Site rows it is always `none`; `site_action`
distinguishes projection alone, clarification, or future publication work.
`site_projection_sufficient` says whether the audited material already permits
the proposed reader projection without a preceding content/publication change.
`notes` states the task rationale and any required authority decision.

This area is repository architecture, not a work ledger. Current PR heads, CI,
review findings, blockers, and next execution actions belong in the stack-tip
PR's canonical Work ledger comment. Never add a mutable `.work-ledger.json` here.
