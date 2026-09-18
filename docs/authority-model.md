# Repository authority model

The repository has five independent authorities and Git histories:

| Authority | Responsibility |
|---|---|
| Modeling | Information-model records, bounded discovery catalog and resource documentation; registration does not transfer normative ownership |
| Composition | Composition-specific artifacts, capabilities, lifecycle/topology semantics, Composer, schemas, validators and consumer contracts |
| Policy | Coding-agent operating policy, procedures, profiles, review/release semantics and adoption/validation tooling |
| Integration | Reviewed provider selection, cross-authority contracts, publication mapping and staging, IA, translation availability, glossary, guided/source models and deterministic Publication Bundles |
| Site | Presentation, browser runtime, accessibility, PWA, Pages packaging and explicit deployment |

`composition + policy → integration → site → GitHub Pages`

Site is not a parent or super-authority. Integration is independent of Site runtime.
Site consumes only an exact versioned Integration output selected by
`integration-source.json`. It has no independent provider publication lock.
A provider/Integration release does not cause Site adoption or deployment. A Site-only
fix may retain the same Integration revision. Consumer tooling used to maintain
Site is distinct from its provider-publication input.

Provider-specific rules belong to their provider. Cross-authority publication rules
belong to Integration. Site may render those rules and detect projection corruption;
it cannot redefine them. The Integration [authority contract](https://github.com/TakashiSasaki/templates/blob/a2b21d731e3aea09f60c6f0dc8a9280089c1a946/AUTHORITY.md)
is canonical for cross-authority integration. This page is the Site reader projection.

Translation ownership follows canonical ownership. Integration derives provider
current/stale/missing status; Site renders it. Site compiles only its own translations.
English remains authoritative and stale derivatives retain a visible canonical link.

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

`agent.json` schema 6 projects all five roles and the dependency direction.
Its Site token is `presentation-runtime-deployment`; Integration's token is
`cross-authority-publication-integration`. The integration contract registry is
Integration-owned. Published discovery adds exact immutable Bundle/provider provenance.
Human prose and machine discovery must agree; neither creates new provider semantics.

## Change rule

Change provider semantics in the owning authority and cross-authority publication
semantics in Integration. Site changes update only this presentation/projection or
Site runtime. Review ownership before editing, preserve normative versus explanatory
meaning, and mechanically verify the Bundle boundary and discovery parity.
