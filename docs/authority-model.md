# Repository authority model

## Status and scope

This is the human-facing Site projection of the four independent repository
authorities. Integration's `authority.json`, `AGENTS.md`, `RELEASE.md` and versioned
Publication Bundle contract govern cross-authority integration. Site publishes this
explanation; it does not become a parent, override or super-authority.

```text
composition ─┐
             ├──> integration ───> site ───> GitHub Pages
policy ──────┘
```

## Authority boundaries

### Composition

Composition owns Composition semantics, artifacts, capabilities, foundations,
lifecycle and repository/workspace topology semantics, recipes, Composer, schemas,
validators and consumer behavior. It owns its canonical documents, translations,
synchronization metadata, glossary concepts and publication catalog.

### Policy

Policy owns operating policy, procedures, profiles, review/release semantics,
adoption/validation/rendering/release tooling, Work-ledger policy and consumer
behavior. It owns its canonical documents, translations, synchronization metadata,
glossary concepts and publication catalog.

### Integration

Integration owns exact reviewed provider selection, provider locks, compatibility,
publication mapping and staging, destinations and reader information architecture,
semantic navigation, translation availability, integrated glossary, guided graphs,
provider source/read models, provenance and deterministic Publication Bundles.
Provider semantics and provider translations remain provider-owned.

The ownership test is whether a contract governs interaction between independent
authorities and cannot correctly belong to either provider independently.

### Site

Site owns HTML/static rendering, CSS/layout, navigation/search/browser/glossary UI,
translation warnings and switching, accessibility, browser interactions, PWA and
Service Worker behavior, runtime freshness, Pages packaging and explicit deployment.
`integration-source.json` selects one exact reviewed Integration release and Bundle
identity. Site does not select provider revisions or derive provider freshness.

Site qualification consumes only that Bundle and Site-owned source. Missing artifact
evidence may cause regeneration by the pinned Integration qualification workflow;
it does not authorize following upstream heads or changing provider selection.

An Integration release stops before Site. Explicit Site adoption, Site qualification,
Site release and deployment are separate operations. A Site-only fix can retain the
same Integration lock. Independent Git histories remain independent and do not imply
adoption of Composition's reusable hub-and-orphan consumer topology.

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
provider independence, and Integration boundaries.

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
and its Integration-owned integration contract registry are stable machine anchors for
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

Reader classification is an independent axis defined in the
[audience architecture](architecture/audience/README.md). Integration owns that
projection; assigning an audience never changes the semantic owner defined here.

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
