# Open Knowledge Format: interpretation and evolution study

This is an **informative, locally authored study**, not the OKF specification, an
upstream-approved interpretation, a conformance profile, or an adoption decision.
Its purpose is to preserve the questions raised during a design discussion and
the evidence needed to revisit them as OKF evolves. It is independent of any
particular repository's index-placement implementation or publication pipeline.
The upstream project retains normative ownership. This folder is not declared to
be an OKF bundle; its own documentation layout is not a proposed OKF requirement.

## Reading route

Start with the [question register](questions.md). Use the
[concept and property reference](concepts-and-properties.md) for frontmatter,
the [index model](index-and-discovery.md) for navigation and Markdown structure,
and the [implementation observations](implementation-gaps.md) for behavior that
must not be mistaken for a standard. The [source register](sources.md) binds the
claims to inspected material and a dated observation.

## Baseline and evidence labels

The baseline is the specification labeled **0.2** at upstream commit
`ad30107c31c06aec8a7d5636e0d1058118604e6f`, inspected on **2026-09-28**.
A version label, a Git commit, a file blob, an issue's current state, and an
observation date are different identities. This is a bounded observation, not a
promise that a mutable branch or community discussion will remain unchanged.

The following labels are editorial categories for this study, not OKF fields:

| Label | Meaning |
| --- | --- |
| Specified | An explicit statement or requirement in the pinned specification. |
| Recommended | A recommendation, including a SHOULD; not silently strengthened to MUST. |
| Example | A specification example or a checked-in sample, not a universal rule. |
| Observed implementation | Behavior read from pinned code or reproduced in a bounded probe. |
| Interpretation | A reasoned reading; its assumptions and alternatives remain visible. |
| Unsettled | The inspected text does not settle the requested distinction. |
| Proposal | A community proposal; existence, comments, or a green PR do not make it adopted. |

Normative text need not contain an uppercase RFC keyword to express a requirement.
Conversely, the absence of an explicit prohibition does **not** establish an
explicit permission or an interoperability guarantee. Specification, examples,
implementation, and this study's recommendations must remain distinguishable.

## Principal conclusions to retain

Concept documents require YAML frontmatter and a nonempty `type`; `type` values
are open, while some named types have additional semantics. `title` and
`description` are standard, recommended, optional fields. Producer extensions
are explicitly allowed for concepts. These conclusions do not authorize arbitrary
frontmatter in reserved index files. [S1](sources.md#s1)

Index files are optional navigation documents. The ordinary no-frontmatter rule
has a bundle-root `okf_version` exception. The body is section-and-link oriented,
but exact heading levels, nesting, indentation, standalone prose, immediate-child
restrictions, and a closed set of link target types are not fully specified.
Do not resolve these silences by copying a reference generator's restrictions
into the standard. [S1](sources.md#s1)

A checked-in index directly links a Python attester. The generic generator does
not enumerate non-Markdown files as entries. A generated HTML visualization is
another, derived surface, not automatically a concept or a guaranteed index
entry. [S2](sources.md#s2) [S5](sources.md#s5) [S7](sources.md#s7)

The design insight raised by the user is worth preserving separately: **a useful
discovery step provides a meaningful choice, not merely a filesystem hop**.
Skipping a one-child directory chain can reduce work without flooding the root
with all leaves. This is a reusable design interpretation, not an adopted OKF
placement rule. See [Q13](questions.md#q13).

## Corrections to overstrong readings in the discussion

The durable record does not retain the earlier claims that deep links are
normatively discouraged, H1-only/one-H1 syntax is mandatory, every physical
level requires an index, or prose is definitively prohibited. Nor does it replace
them with the equally unsupported claim that all such forms are guaranteed to
work with every consumer. See Q08-Q13.

Do not describe `generated.at` merely as original creation time; the pinned
specification gives it last-meaningful-content-change semantics. Do not infer
that any copied Markdown repository is a conformant bundle, that an index link
turns a Python/JSON file into a concept, or that successful generation proves
conformance. See Q02, Q04-Q07 and Q15-Q16.

## Boundaries

No full upstream standard or upstream implementation is vendored here. The
source register supplies immutable references. Small synthetic probe inputs and
results are locally authored observations. Rights to redistribute an upstream
artifact, authenticity, an upstream release decision, and an implementation's
correctness are not established merely by recording a URL or a Git blob ID.
