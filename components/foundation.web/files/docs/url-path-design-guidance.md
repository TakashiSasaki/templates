# Web URL and path design guidance

## Status and authority

This document is Composition-owned advisory guidance for designing browser-facing
Web URLs and route paths. It is intended to improve readability, persistence,
operational predictability, and user understanding without narrowing the set of
valid route contracts.

Normative route conformance remains defined by `contracts/routes.json`,
`schemas/routes.schema.json`, the registered `routes` contract version, and the
applicable Composition validators. A route may depart from this guidance without
becoming invalid solely because of that departure. Validators and schemas do not
enforce the preferences in this document unless a rule is separately introduced
into the normative route contract through its normal contract-evolution process.

This distinction follows the repository-wide authority model published by Site:
guidance expresses preferred design choices, while conformance requirements stay
with the owning provider's normative contract.

## Scope

This guidance applies to public browser-facing route paths shared by Website and
Web application artifacts through `foundation.web`. It does not define
application state, authorization behavior, API protocol design, deployment
routing internals, or product-specific resource models.

The route contract represents the canonical path portion of a Web URL. Query and
fragment components have different roles and are not part of the `path` field in
the shared routes contract.

## Current normative representation boundary

The current `routes` contract at schema version 4 accepts `/` or an absolute
non-root path composed of slash-delimited ASCII letters, digits, `.`, `_`, `~`,
and `-`, while excluding path segments that are exactly `.` or `..`. Non-root
paths may end in a segment or a single trailing slash. Routes v5 preserves that choice as part of canonical identity; `/reports` and `/reports/` are distinct paths, not implicit aliases. Query syntax, fragment
syntax, percent escapes, and literal non-ASCII characters are outside the current
`path` representation.

Those facts are conformance rules from the registered schema, not preferences
created by this document. A product that needs a broader path representation,
such as literal internationalized segments or repeated separators, needs an explicit route-contract evolution rather than a guidance
exception.

## Design preferences

### Prefer stable public identifiers

Prefer paths based on durable user or domain concepts rather than implementation
structure. A public identifier is easier to preserve when it does not expose the
current framework, source-file extension, template directory, internal service,
or deployment topology.

For example, prefer a durable path such as `/account/settings` over a path whose
shape is coupled to a particular implementation such as
`/pages/AccountSettings.php`.

When a canonical path changes for a legitimate product reason, preserve known
old locations through aliases or deployment redirects when the selected runtime
supports that behavior. The shared routes contract records route aliases; the
runtime or deployment capability remains responsible for implementing the
corresponding redirect or equivalent behavior.

### Prefer readable and predictable segments

Prefer lowercase path segments where that choice is compatible with the product's
identifiers. Lowercase reduces avoidable case variation across case-sensitive and
case-insensitive tooling, but uppercase ASCII characters remain valid under the
current shared route schema.

For multi-word Latin-script segments, prefer hyphens when a separator improves
readability. For example, `/account-settings` is generally clearer than
`/account_settings` or `/AccountSettings`. This is a style preference, not a
route-validity rule.

Keep segments concise enough to scan while retaining enough meaning that readers
can recognize the destination. Do not compress public terminology merely to make
paths shorter.

### Use hierarchy only when it carries durable meaning

Use nested path segments when the hierarchy expresses a stable relationship that
helps readers understand the resource or task. Avoid deep nesting that merely
repeats implementation ownership, controller structure, or menu hierarchy.

A path such as `/projects/42/activity` can communicate a durable relationship.
Additional levels such as `/frontend/pages/projects/controllers/42/activity`
usually expose implementation topology instead of public information
architecture.

### Distinguish path identity, query variation, and fragments

Prefer the path for page or resource identity. Consider query parameters for
optional filtering, sorting, view selection, pagination, search input, or other
variations that do not need a distinct canonical route identity.

Use fragments for an in-document anchor or client-local location when the server
route identity remains the same. Do not copy query or fragment syntax into the
shared route `path` field; the current route schema intentionally models only the
path component.

### Avoid implementation details in public paths

Avoid exposing file extensions, framework directories, generated build paths,
internal service names, or other replaceable implementation details unless they
are intentionally part of the product's durable public identifier.

A path ending in `.html` or `.php` can still satisfy the shared route schema. The
reason to avoid such a suffix by default is persistence and implementation
independence, not conformance.

### Add locale or version prefixes only when they are real identity dimensions

Consider a locale or version segment when it identifies a deliberately distinct
public representation that the product expects to preserve. Avoid adding
`/v1/`, locale prefixes, or similar namespaces only as speculative preparation
for future needs.

If versioning or localization has product-specific behavioral consequences, keep
those semantics in the applicable product or capability authority rather than
expanding the shared route contract merely for naming style.

### Keep sensitive and transient state out of path names

Avoid encoding credentials, secrets, session identifiers, authorization context,
or other sensitive transient state into public paths. URLs commonly appear in
browser history, logs, analytics, screenshots, copied links, and referrer data.

Product-specific security and authorization rules remain outside this guidance
and belong to the authority that owns those behaviors.

### Treat route slugs and user-facing labels separately

A concise route slug is not a substitute for an accessible navigation label,
document title, heading, or localized display name. Choose route paths for stable
identification and choose user-facing labels for comprehension in their display
context.

The shared route contract already models accessibility metadata separately from
the path. Preserve that separation rather than deriving display text mechanically
from a slug. Products can localize display labels independently of the current
route-path character repertoire.

## Guidance versus conformance examples

The following examples illustrate the separation between advisory style and
normative route validity.

| Path | Guidance assessment | Current route-schema assessment |
| --- | --- | --- |
| `/account/settings` | Preferred stable lowercase hierarchy | Valid |
| `/Account_Settings.HTML` | Discouraged by case, separator, and implementation-detail guidance | Valid |
| `relative/path` | Not evaluated as an alternative style because it is not an absolute route path | Invalid |
| `/a/../b` | Avoid parent traversal in a public identifier | Invalid |
| `/reports/` | A directory-style canonical URL is representable in routes v5 | Valid |
| `/café` | Internationalized literal path requires contract evolution under the current representation | Invalid |

The second row is deliberate: a validator that rejects
`/Account_Settings.HTML` solely because it departs from this document would turn
guidance into an undeclared normative requirement. That would violate the
repository authority model.

The final two rows illustrate the opposite direction. Guidance cannot waive a
constraint that the owning normative route contract already imposes.

## Change discipline

When considering a new URL or path rule, first decide whether it is required for
route interoperability, safety, deterministic composition, or another genuine
conformance invariant. If so, evolve the normative route contract and its tests
through the existing contract-versioning process.

If the rule instead expresses a preferred design choice with valid exceptions,
keep it here as guidance and test that validators do not enforce it accidentally.
Do not strengthen guidance by moving the same wording into a schema assertion
without an explicit normative contract change.

## Background references

The preferences above are informed by stable Web architecture and operational
practice, including:

- RFC 3986, *Uniform Resource Identifier (URI): Generic Syntax*, for URI component
  and hierarchical path semantics: <https://www.rfc-editor.org/rfc/rfc3986>;
- Google Search Central, *URL Structure Best Practices*, for simple descriptive
  URLs and readable word separation:
  <https://developers.google.com/search/docs/crawling-indexing/url-structure>;
- W3C, *Cool URIs don't change*, for persistence and avoiding implementation
  details in durable identifiers: <https://www.w3.org/Provider/Style/URI>.

These references provide rationale and interoperability context. They do not
replace the Composition-owned route contract as the conformance authority for
repositories using this foundation.
