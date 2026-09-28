# Concept documents and standard properties

This reference summarizes the [pinned specification S1](sources.md#s1), not an
executable schema. Field presence, field meaning, value vocabulary, and consumer
acceptance are separate dimensions. See Q01-Q05 and Q15-Q16 in the
[question register](questions.md).

## Documents, identities, and bundle scope

A concept is a UTF-8 Markdown document with YAML frontmatter and a Markdown
body. In the specified bundle tree, all `.md` files except `index.md` and `log.md`
are concepts. The concept ID is its bundle-relative path with `.md` removed
(section 2); the underlying resource is what that concept describes, not the
same identity. A moved path therefore raises identity questions; a directory
name or a URL should not be silently treated as a stable semantic identifier.
[S1 §§2-4](sources.md#s1)

The minimum required concept field is a nonempty `type`. Its values are open,
not centrally registered; unknown values must be handled gracefully. The
specification recommends descriptive values. A plain heading-only document is
not made conformant by an index link. A known type may have additional meaning:
`Attested Computation` has its own contract. [S1 §§4,10,11](sources.md#s1)

## Standard top-level concept fields

| Family | Property | Meaning and presence rule in the inspected text |
| --- | --- | --- |
| Core | `type` | Always required; short kind name; open vocabulary. |
| Presentation | `title` | Recommended, optional display name; filename fallback allowed. |
| Presentation | `description` | Recommended, optional one-sentence summary for indexes/snippets/previews. |
| Identity | `resource` | Recommended where applicable; URI identifying the underlying asset, absent for abstract concepts without such an asset. |
| Classification | `tags` | Recommended, optional list of short classification strings. |
| Provenance | `sources` | Optional list of source artifacts or scope descriptors. |
| Provenance | `usage_window` | Optional shared observation interval for source usage counts. |
| Trust | `generated` | Optional producer/current-content event; `by` is required when supplied. |
| Trust | `verified` | Optional verification events, each expressed with actor and time; a single mapping must be treated as a one-item list. |
| Lifecycle | `status` | Optional; specified values `draft`, `stable`, `deprecated`; omitted means `stable`. This is not external approval. |
| Lifecycle | `stale_after` | Optional absolute instant; stale when current time is at or past it. |
| Computation | `runtime` | Required for `Attested Computation`; gives execution and parameter-binding context. |
| Computation | `parameters` | Named, typed input declarations for that computation. |
| Computation | `computation` | Optional path to code instead of an inline computation block. |
| Computation | `executor` | Run instructions/code and receipt field declaration. |
| Computation | `attester` | Deterministic receipt-checking code reference. |

The table is drawn from sections 4.1, 5, and 10.2. It does not promote every
example into a required field: the computation section expressly marks
`runtime` required and `computation` optional; section 11 also gives permissive
consumer guidance for optional families. Preserve that wording rather than
inventing a uniformly strict closed schema. [S1](sources.md#s1)

## Nested properties

`sources[]` defines `resource` (required within an entry), `id`, `title`, `author`,
`usage_count`, `last_modified`, and an optional per-source `usage_window`
override. The shared and overridden window have `from` and `to`. A source may
be an identifiable artifact or a non-dereferenceable population/scope descriptor;
not every source value is a fetchable URL. A source `id` can join a body footnote
to its provenance entry. [S1 §5.1](sources.md#s1)

`generated` uses `by` and `at`; `generated.by` is explicitly required within
that family. `verified` accepts a list or a single mapping with `by` and `at`.
`parameters[]` uses `name`, `type`, `required`; this nested `type` describes a
parameter, not a concept kind. `executor` defines `resource` and `receipt`;
`attester` defines `resource`. [S1 §§5.2,10.2](sources.md#s1)

## Time and trust distinctions

| Field | What time it records |
| --- | --- |
| `sources[].last_modified` | Last change to the source material. |
| `generated.at` | Last meaningful change to the concept's current content, not necessarily its first creation. |
| `verified[].at` | Verification event; changing content and re-verifying it are distinct. |
| `usage_window.from` / `.to` | Interval during which source usage was observed. |
| `stale_after` | Freshness deadline, not a measurement of modification time. |

In the pinned revision, timestamp-valued fields use ISO 8601 datetimes with an
explicit UTC offset. `log.md` date headings instead use `YYYY-MM-DD`. Issue #24
questions versioning of a change to these time rules; issue #28 proposes
separating original generation from later revision. Neither proposal changes
this pinned baseline. [S1 §§5,9](sources.md#s1) [D24](sources.md#d24) [D28](sources.md#d28)

The specified actor forms include an agent/tool name and version, `human:` and
`process:` identifiers. Trust tiers are inferred from verification entries;
they are advisory, not access control, proof of authenticity, or executable
permission. `verified` concerns the definition, whereas computation attestation
concerns an individual execution. Runtime receipts/verdicts are not ordinary
bundle-stored concept history in the described model. [S1 §§5,7,10](sources.md#s1)

## Extensions and special non-concept keys

Concept frontmatter allows producer-defined additions. Unknown fields must not
alone cause rejection, and round-trip preservation is recommended. Namespaced
extensions are an optional collision-avoidance technique, not a mandated `x-`
syntax. Reusing a standard key with a different meaning is an interoperability
hazard. [S1 §4.1](sources.md#s1)

`okf_version` is separately defined for the bundle-root index. It is not part of
the above concept-property inventory. Legacy `timestamp` is described as a
fallback in section 13, not the preferred v0.2 field. `revised`, `edited`, a
stored `trust_tier`, a general `updated_at`, and a top-level explicit concept
`id` are not standard concept fields established by the inspected text; an
extension may use them without making them upstream-defined semantics.
[S1 §§2,5,12,13](sources.md#s1) [D28](sources.md#d28)
