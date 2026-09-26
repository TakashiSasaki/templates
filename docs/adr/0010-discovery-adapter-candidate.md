# Repository-local discovery adapter, candidate version 2

Status: proposed, Stage A only. Policy owns this contract, schemas and generic
validator. The selected self-host Policy revision, effective adapter and lock
remain unchanged. This candidate is an object of validation, not operating
instructions for its author. No publication or deployment authority is added.

## Meaning before structure

Root navigation is always `index.md`. Operational indexes have no front matter.
They explain location, responsibilities and non-responsibilities, adjacent
areas, authoritative definitions and next steps. Prose and ordinary Markdown
are allowed; headings are not a machine-readable ownership vocabulary.
Contracts, descriptors and domain inventories retain semantic authority. This
is not an OKF bundle declaration and introduces no concept metadata.

The expected set is the union of typed bootstrap `entries`, inventory source
files, explicitly selected local members, projection sources/members, generated
indexes and delegation entries, minus justified global exclusions. It is built
before reading indexes. Files, directory entries and indexes are distinct:
`dir/` reaches the directory and its operational `dir/index.md` when present;
an index also reaches its containing directory. Neither implies all descendants.
Only reached operational indexes contribute navigation edges. An existing file
or foreign reference with the same spelling never proves local membership.

`entries` holds a few bootstrap anchors (for example README, AUTHORITY and AGENTS)
and independently required indexes; it is not a second domain catalog. Inventory
inputs themselves are required discoverable files. Missing, malformed or stale
inputs are errors, including unused/nonlocal input data. Optional adapter fields
are absent when unused; present empty collections are invalid. No schema defaults
are applied. Processing is parse, structure, semantics, graph/freshness, then
explicit generated mutation. Duplicate keys are parse failures.

## Bounded selectors and domain projections

Compare two mechanisms against real data:

- A selector is a nonempty array of object keys with `*` only for array expansion.
  It selects string leaves, with explicit `local`, `external` or `deployment`
  namespace and local kind. Missing keys, nonarrays at `*`, and nonstring leaves
  fail. Empty arrays are valid inventories with zero members. There is no query
  expression, recursion, interpolation, filter, arbitrary hook or network fetch.
- A domain-produced projection has typed local members and SHA-256 bindings for
  an exact, adapter-declared nonempty source closure. Generic validation checks
  closure equality and source bytes. The domain's formal generator/freshness check
  must also prove the output corresponds to those inputs; digests alone cannot
  prove derivation. The adapter cannot execute that generator.

Use selectors for publication document `source` fields, Policy rule inventories
and mixed Site references; use a projection when IDs require domain resolution.
Composition's own Composer resolves component/recipe IDs. Policy must not copy
that rule. Stage A may obtain fixture members by calling immutable domain code;
a supported, checked projection producer is a Stage B prerequisite. External
references are canonical foreign paths or HTTPS/HTTP URLs; deployment references
are absolute URL paths or HTTPS/HTTP URLs. Neither becomes a filesystem target.
Input source, member, generated output and deployed location remain separate.

## Four independent scope decisions

`exclude` removes an entire local subtree from discovery, with a reason.
`omit_from` removes members from one index's coverage obligation, with a reason;
it never removes global root obligations. A direct link to an omitted member in
that index is rejected, so a reader index can stay publication-closed.
`delegate` suppresses scanning for operational indexes strictly within a subtree
while retaining a typed required entry and a reason. It does not remove explicitly
selected members; domain source inventories still define their obligation.
Deep direct links need no declaration. There is no requirement to mirror physical
directories. Useful nested indexes coexist with ancestor shortcuts. Explicit
index entries require those particular boundaries independently of existing files.
Contradictions (required/excluded, omitted/root, active/retired, duplicate target
with incompatible kinds, hidden required index) are errors, not precedence rules.
Fixture and distribution directories may be delegated or globally excluded without
rewriting their same-named test input indexes.

## Navigation and generation

Navigation recognizes visible inline Markdown links in paragraphs, headings,
lists and tables. HTML comments, fenced/indented code, inline code and blockquotes
are not navigation. Reference-style links, HTML links and autolinks do not establish
coverage. Root-relative repository links are invalid. Relative links may use `..`
within the repository. Fragments are checked against visible ATX/setext headings
and explicit HTML anchors, with exact fragment matching. Directory fragments apply
to the directory's index and fail if none exists. No front matter is permitted at
root or nested indexes, and a level-one title is required.

`generated` declares output index, title, section and explicit file/directory
member scopes; it selects from the expected set, never invents membership.
`retire` is explicit and reasoned. Generation delegates to the existing marker,
Git tracking/dirty, snapshot, containment, symlink, no-clobber, rollback and
residual-reporting engine. Authored navigation is never automatically rewritten.
Dry-run does not modify the checkout. Repeated successful apply is a no-op.

## Old field disposition

| Old field | Decision and operational replacement |
| --- | --- |
| schema_version | Require exactly 2; explicit candidate launcher rejects old input |
| root_index | Remove; fixed root `index.md` |
| authoritative_inventories | Redesign as typed, explicit `inventories` or `projections` |
| expected_documents | Replace with small typed `entries`; domain membership stays in inventories |
| inventory_path_namespaces | Replace inventory-wide choice with per-selector namespace |
| authored_boundaries | Required indexes become typed index entries; no directory-count heuristic |
| explicit_exclusions | Reasoned `exclude`; no automatic generated/closed exclusions |
| exclusion_reasons | Consolidate with each exclusion |
| authored_index_exclusions | Reasoned `omit_from`; root coverage unchanged |
| closed_inventories | Replace scan decision with `delegate` plus mandatory entry |
| curated_shortcuts | Remove; direct navigation needs no declaration |
| intentional_no_indexes | Remove; absence of index is allowed without suppressing documents |
| generated_indexes | Strict `generated` records; existing safe mutation engine |
| remove_generated_indexes | Reasoned `retire`; root cannot retire |
| publication_system | Remove; owned by publication qualification, unused by discovery |
| surface_boundaries | Remove; explanations belong in indexes/domain contracts |
| inventory_scope_reason | Remove; contract rationale belongs in documentation |

## Distribution, launch and transition

Canonical Draft 2020-12 schemas reside in `schemas/`; the Skill renderer embeds
those exact bytes for portable distribution, as it does the Policy selection
schema. Source execution reads the same canonical files. Missing schema is an
error. Adapter-selected schema URLs/plugins are forbidden. The candidate uses an
explicit `--candidate-v2` launch gate. Isolated qualification may render a
version-2-default package with `render_skill(..., discovery_contract_version=2)`;
its ordinary CLI then requires v2, including from existing qualification callers.
This is an explicit package-construction choice, never inferred from adapter input.
Default rendering remains version 1 during Stage A. The supported legacy launch rejects version
2/unknown versions; candidate launch rejects missing/old/unknown versions.
Historical independently installed binaries cannot be retroactively repaired:
Stage B must replace runtime, adapter and generated lock in one qualified change.
The old path is transitional to permit current formal CI without adopting the
candidate; remove it after the coordinated transition, not as a permanent alias.

P1 establishes structural examples only. P2 supplies runtime/CLI/distribution;
P3 binds real consumer previews and migration prerequisites. Qualification must
check selected state, validation and result, not exit code alone. Structure alone
does not prove existence, namespace ownership, freshness, safety or coverage.

The [consumer migration design](../discovery-adapter-migration.md) records the
fixed-input audit, prospective domain work and qualification scope. The edited
shared rule is proposed source; the active pinned AGENTS and v1 rule still govern
the implementation work. Its old small grammar rejects new boundary paragraphs,
which is reported as D3 rather than hidden by a skip or an adoption switch.
