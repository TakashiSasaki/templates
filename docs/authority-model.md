# Repository authority model

## Status and scope

This document is the canonical Site-owned normative contract for interpreting
authority ownership and semantic roles across `TakashiSasaki/templates`.

Site is the repository integration and publication authority. Site is not a
parent, override, or super-authority above Composition or Policy. This document
defines only repository-wide integration semantics: it does not transfer or
redefine provider-specific semantics.

The ownership test is:

> Site may own a semantic rule when the rule governs integration or interaction
> between independent authorities and cannot correctly be owned by either
> provider independently.

The negative boundary is equally important:

> Provider-specific semantics remain owned by their provider even when Site
> publishes, explains, validates, translates, or projects them.

A rule that fails the ownership test belongs to the applicable provider, not to
Site merely because the rule is useful to multiple readers or appears in the
integrated portal.

## Authority boundaries

### Composition

Composition owns Agent Skill, Website, and Web application artifact semantics,
component selection, capabilities, foundations, lifecycle semantics, recipes,
schemas, validators, deterministic Composer behavior, and Composition consumer
management.

Site must not redefine Composition-specific artifact semantics, component
selection semantics, lifecycle semantics, or Composer consumer mutation
semantics.

### Policy

Policy owns coding-agent operating policy, review semantics, Policy profiles and
runtime/release semantics, Policy procedures, selection/validation/rendering/
adoption/release tooling, and Policy consumer management.

Site must not redefine Policy-specific coding-agent semantics, profiles,
runtime/release semantics, or Policy consumer mutation semantics.

### Site

Site owns repository integration and publication semantics, including reviewed
provider revision selection, publication assembly, reader-facing information
architecture, navigation/localization integration, human/machine projection
parity, Pages/PWA publication, cross-provider integration validation, and
cross-authority rules that pass the ownership test above.

At an integration boundary Site may observe, validate, publish, route, translate,
or project provider semantics. It must not become a third umbrella management
plane that adopts, updates, repairs, migrates, renders, or otherwise mutates
provider-owned consumer state on behalf of Composition or Policy.

## Semantic roles

The semantic role of material is determined by its owning authority and declared
function, not by file format, filename, rendering surface, or the existence of a
schema or validator.

### Normative authority

A normative authority is the authority that has decision rights for a semantic
domain. It determines which requirements govern conformance, required behavior,
allowed behavior, and prohibited behavior in that domain.

Markdown, JSON, schemas, executable validators, or canonical prose can all carry
normative authority when the owning authority defines them to do so. Conversely,
a machine-readable file is not normative merely because it is JSON, and prose is
not advisory merely because it is Markdown.

### Normative requirement

A normative requirement is a rule issued by the owning normative authority that
participates in conformance. Violating an applicable normative requirement may
make a composition, policy configuration, repository state, publication, or
other governed object invalid.

A rule does not become normative merely because it is repeated in a projection,
example, test fixture, generated artifact, or advisory document.

### Guidance

Guidance expresses a preferred design choice or implementation approach. A
consumer may depart from guidance without becoming invalid solely because of
that departure.

Guidance may cause a conformance failure only when the same rule is separately
defined by the owning authority as a normative requirement. Validators and tests
must not silently promote guidance into requirements.

### Evidence

Evidence demonstrates that a normative requirement has been satisfied or that a
specified behavior occurred. Evidence may be required by a normative contract,
but evidence does not change the source requirement it demonstrates.

A report, screenshot, trace, test result, manifest, or other evidence artifact
must not silently strengthen, weaken, or reinterpret the governing requirement.

### Projection

A projection represents existing authority for another reader, medium, locale,
or machine interface. Examples include provider authority rendered into a Site
page, projected into `agent.json`, translated for readers, or generated into
coding-agent instructions.

A projection must preserve the owner and meaning of its source authority. It must
not create new provider semantics merely because the projected representation is
more convenient, executable, localized, or machine-readable.

### Example

An example illustrates a valid or useful application of existing authority. It
is non-authoritative unless the owning authority explicitly and separately makes
a demonstrated property normative.

Examples must not silently narrow the set of valid implementations to the one
shown.

### Explanation

Explanation supplies rationale, terminology, migration context, or conceptual
help. Explanation is non-authoritative unless the owning authority explicitly
designates the relevant prose as normative authority.

The presence of explanatory prose next to normative rules does not weaken those
rules, and the presence of normative prose in Markdown does not make it advisory.

## Normative and advisory wording

RFC 2119 / RFC 8174 keywords are reserved for normative contexts in this
repository:

- `MUST` and `MUST NOT` express absolute normative requirements;
- `SHOULD` and `SHOULD NOT` are normative requirements that permit justified
  exceptions under the conditions described by the owning authority; and
- `MAY` expresses normative permission.

In particular, `SHOULD` must not be reduced to a casual recommendation.

Advisory material should avoid capitalized RFC keywords. Prefer ordinary-language
signals such as `prefer`, `consider`, `avoid`, or lowercase `recommended`, and
label the material as guidance when ambiguity is possible.

This vocabulary rule applies prospectively. Existing repository prose does not
change semantic role merely because it predates this wording convention.

## Projection and validation rules

Human-facing and machine-facing projections may differ in presentation but must
converge on the same authority owner, applicable normative requirements,
provider independence, and Site integration boundaries.

Site validation may detect projection drift or a cross-authority conflict. Such
detection does not transfer ownership to Site. A provider-specific defect must be
fixed in the owning provider authority; Site may update its projection only after
that authority changes or when the Site projection itself was wrong.

Evidence and projections must be traceable to the authority they represent when
that identity is material to safe interpretation. Traceability does not make the
evidence or projection a new source of semantics.

## Machine discovery

`agent.json` remains the machine bootstrap surface. Its Site role token
`publication-integration`, the `consumer_repository_mutation: false` boundary,
and its Site-owned integration contract registry are stable machine anchors for
this model.

The repository-wide model is directly discoverable as:

```text
agent.json
  -> integration_contracts.authority_model
  -> docs/authority-model.md
```

The Policy–Composition coexistence contract remains a separate Site-owned entry
because it governs one concrete cross-provider boundary rather than the general
repository-wide semantic vocabulary.

Schema version 5 adds only this direct canonical repository path. It does not
introduce a semantic-classification system, universal document metadata, or a
requirement to classify existing repository material. A future schema expansion
is warranted only if a machine consumer needs to make an automated decision that
cannot be made safely from the authority role, non-mutation boundary, direct
contract path, and canonical prose.

## Change rule

A change to this document requires Site review because it changes repository-wide
integration semantics. Such a change must not be used to alter provider-specific
behavior indirectly.

When a new rule is proposed:

1. identify the semantic owner before choosing the file or representation;
2. apply the Site ownership test if the rule crosses independent authorities;
3. state whether the rule is a normative requirement, guidance, evidence rule,
   projection rule, example, or explanation;
4. keep provider-specific rules in the provider authority; and
5. verify that human and machine projections still describe the same authority
   boundaries.

This model intentionally does not require repository-wide front matter,
retrospective classification of every existing document, or a universal
semantic-role metadata schema.
