# OKF question register

These questions preserve the substantive concerns raised by the user, paraphrased
for general reuse rather than copied as a conversation transcript. Each answer
is scoped to the [2026-09-28 baseline](sources.md). Open questions are not closed
merely because a local implementation needs a decision.

<a id="q01"></a>
## Q01 — May index.md contain frontmatter?

**Specified:** Section 8 says index files have no frontmatter, except that the
bundle-root index may carry `okf_version`; section 12 repeats the root exception.
**Unsettled:** The text does not provide a separate root-index key schema. The
only expressly authorized key is `okf_version`; extending the concept-only
additional-key rule to root indexes is not justified by section 4.1 alone.
Section 11's broadly worded requirement for `type` in every frontmatter block
also needs to be read with the reserved-file exception, not used to force a
concept `type` onto the root index. A conservative root-key whitelist is a local
interpretation, not a separately published OKF schema. **Revisit when:** root
metadata, reserved-file conformance, or bundle metadata placement changes.
**Evidence:** [S1 §§8,11,12](sources.md#s1); [D25](sources.md#d25), [D26](sources.md#d26).

<a id="q02"></a>
## Q02 — Must ordinary Markdown have frontmatter, or is it optional?

**Specified:** In a selected bundle tree, non-reserved `.md` files are concepts;
sections 4 and 11 require parseable YAML frontmatter and a nonempty `type`.
A frontmatter block containing only `title` is insufficient. This includes a
`README.md` inside that bundle; filename familiarity does not exempt it.
**Boundary:** This concerns the chosen bundle, not automatically every directory
of a larger Git repository. Declaring `okf_version` does not transform bytes or
supply missing metadata, and omitting that optional declaration does not waive
concept conformance. **Revisit when:** membership, exclusion, nested-bundle, or
reserved-name rules change. **Evidence:** [S1 §§3,4,11,12](sources.md#s1).

<a id="q03"></a>
## Q03 — May concept frontmatter contain arbitrary extra properties?

**Specified:** Section 4.1 permits producer-defined keys, forbids consumer
rejection solely for unrecognized fields, and recommends preservation during
round trips. **Boundary:** Unknown fields need not be interpreted. This is not
permission to redefine standard fields, and it is not an index-frontmatter
extension rule. Namespacing extensions is an interoperability design option,
not an OKF-mandated `x-` prefix. **Revisit when:** extension namespaces, typing,
or round-trip rules are standardized. **Evidence:** [S1 §§4.1,11](sources.md#s1).

<a id="q04"></a>
## Q04 — Is type a controlled vocabulary, and are title/description special?

**Specified:** `type` is a required standard key, but its values are not centrally
registered and unknown types must be handled gracefully. `title` and
`description` are standard recommended optional keys, not arbitrary extensions.
A missing title may be derived from the filename. **Boundary:** Open vocabulary
does not mean every value has no defined semantics: `Attested Computation` has
a specific contract, including `runtime`. **Revisit when:** a type registry or
new type-specific contract appears. **Evidence:** [S1 §§4.1,10.2,11](sources.md#s1).

<a id="q05"></a>
## Q05 — What other standard properties exist, and where do times belong?

**Specified:** The basic, provenance, trust, lifecycle, and computation fields
are cataloged in [the property reference](concepts-and-properties.md). In
particular, source `last_modified`, concept `generated.at`, verification `at`,
and `stale_after` describe different events. `log.md` is scope history, not an
index metadata table. **Unsettled:** There is no standard index-modified-time
field in the inspected text. Future revision/creation separation is proposed,
not adopted in this baseline. **Revisit when:** timestamp precision, freshness,
`generated`/`revised`, or index metadata changes. **Evidence:** [S1 §§5,7-10](sources.md#s1);
[D24](sources.md#d24), [D28](sources.md#d28).

<a id="q06"></a>
## Q06 — Is an OKF bundle restricted to Markdown files?

**Specified:** Concepts are Markdown and the introduction to section 3 describes
a Markdown directory tree. **Example:** The specification also points to Python
and SQL resources, and the sample/README supplies code and an HTML viewer.
**Interpretation:** A Markdown-only payload whitelist is not a sound reading of
all these sources together. **Unsettled:** A complete auxiliary/derived payload
membership and packaging model is not defined. An arbitrary binary format's
consumer support does not follow from the absence of a prohibition.
**Revisit when:** payload typing, bundle membership, exclusions, or packaging is
formalized. **Evidence:** [S1 §§3,6.3,10,11](sources.md#s1), [S5-S7](sources.md#s5).

<a id="q07"></a>
## Q07 — May an index link to Python, SQL, JSON, or a generated HTML viewer?

**Example:** The checked-in `acme_retail/attesters/index.md` directly links
`sql_equality.py`. This establishes an upstream example, not a mandatory behavior
for every generator. **Unsettled:** Section 8 alternates between directory
contents and concepts; it gives no closed target-type list. SQL/JSON links are
reasonable auxiliary-resource analogies, not independently demonstrated examples
in this observation. The inspected root sample does not link `viz.html`; that
absence neither bans HTML nor proves universal HTML-link support. **Boundary:**
Indexing a non-Markdown resource does not make it a concept or grant execution
permission. **Revisit when:** target types or consumer traversal rules change.
**Evidence:** [S1 §8](sources.md#s1), [S2](sources.md#s2), [S5-S7](sources.md#s5).

<a id="q08"></a>
## Q08 — Which heading levels and section organizations are prescribed?

**Specified:** Section 8 describes one or more headed sections. **Example:** Its
example and reference generator use sibling H1 sections, potentially more than
one H1. **Unsettled:** There is no complete heading-level grammar, exactly-one-H1
rule, nested-heading contract, mandatory section name, or mandatory grouping by
`type`. The generator's type grouping is implementation behavior. **Revisit
when:** an index grammar or section model becomes normative.
**Evidence:** [S1 §8](sources.md#s1), [S2-S4](sources.md#s2), probe P07.

<a id="q09"></a>
## Q09 — What are the rules for bullets, indentation, levels, and nesting?

**Example:** Section 8 uses unindented `*` entries, a Markdown link, and a short
explanation after a hyphen. The generator emits flat lists. **Unsettled:** Exact
bullet spelling, ordered-list treatment, indentation width, nested-list depth,
line wrapping, and a normative Markdown dialect/AST profile are not specified
there. Valid generic Markdown and an interoperable OKF index are distinct
questions. **Revisit when:** explicit grammar and consumer parsing tests cover
these variations. **Evidence:** [S1 §8](sources.md#s1), [S2-S4](sources.md#s2).

<a id="q10"></a>
## Q10 — May index.md contain standalone prose, tables, code, or HTML?

**Specified:** The defined index purpose is discovery through headed sections;
entry descriptions are part of the illustrated form. **Unsettled:** Independent
paragraphs and richer blocks are neither explicitly authorized nor explicitly
lexically banned. Section 4.2's free-form concept body is not automatically the
reserved index contract. **Observed implementation:** Regeneration replaces
curated text when a file is rewritten. It is not a prose-preserving round trip.
**Interpretation:** Put substantial knowledge in a concept and link to it when
interoperability matters; this is design guidance, not an upstream no-prose
rule. **Revisit when:** section introductions, preservation, or richer bodies
are defined. **Evidence:** [S1 §§4.2,8,11](sources.md#s1), [S2](sources.md#s2), probe P01.

<a id="q11"></a>
## Q11 — Must every subdirectory have an index, and how is it linked?

**Specified:** Indexes may occur at any level and are optional. Consumers may
synthesize them; missing indexes alone are not grounds to reject a bundle.
**Examples:** The specification shows `subdir/`; the generator and root sample
use `subdir/index.md`. **Unsettled:** No server protocol promises that requesting
a directory URL returns Markdown. Explicit file links remove that particular
serving ambiguity but are not the only permitted spelling stated by OKF.
**Revisit when:** resolution, serving, or synthesis contracts change.
**Evidence:** [S1 §§8,11](sources.md#s1), [S2](sources.md#s2), [S6](sources.md#s6).

<a id="q12"></a>
## Q12 — May a parent/root index point to a deep directory or leaf concept?

**Specified:** Section 8 does not state an immediate-child-only restriction.
Section 6 supplies path forms. **Observed implementation:** The reference
algorithm enumerates immediate children and creates ancestor indexes; it does
not generate deep shortcuts. **Interpretation:** Direct descendant links are
plausible and no explicit depth restriction was found. This is weaker than an
express permission covering all consumers. **Unsettled:** Descendant enumeration
and shortcut preservation have no detailed contract. **Revisit when:** scope or
reachability rules are clarified. **Evidence:** [S1 §§6,8](sources.md#s1), [S2](sources.md#s2), P02.

<a id="q13"></a>
## Q13 — Does skipping a one-concept directory defeat progressive discovery?

**User concern:** Adding a fetch for every directory in a one-child chain can
add work without offering any new choice. **Interpretation:** Separate the
physical tree from a discovery graph. A meaningful category may deserve a node
even with one item; a structural namespace may be bypassed even several levels
down. Use the number and meaning of choices and retrieval cost, not physical
depth alone. A few shortcuts differ from flattening every leaf into a huge root.
**Unsettled:** OKF specifies no hop budget, fan-out limit, or collapse algorithm.
Do not attribute this design interpretation to upstream. **Revisit when:**
community usability evidence or traversal policy addresses these tradeoffs.
**Evidence:** [S1 §8](sources.md#s1); contrast [S2](sources.md#s2), P02.

<a id="q14"></a>
## Q14 — Should paths and last-updated information be duplicated in an index?

**Specified:** The entry link already locates its target; sections 5 and 9 offer
distinct concept/source time and log mechanisms. Section 8 recommends reusing a
linked concept's description. **Unsettled:** It does not define a path column,
index timestamp, SHA, or provenance table. **Interpretation:** Avoid copying
volatile metadata without a declared source and regeneration rule. The absence
of an index field is not a ban on every explanatory mention of a date.
**Revisit when:** structured index metadata or generation ownership is defined.
**Evidence:** [S1 §§5,8,9](sources.md#s1).

<a id="q15"></a>
## Q15 — Are conformance, parsing, generation, and acceptance equivalent?

**Specified:** Section 11 defines bundle conditions but also instructs consumers
to tolerate missing optional metadata, unknown fields/types, broken links, and
missing indexes. **Observed implementation:** Parsing does not itself call
concept validation; the generator can list a frontmatter-free document or
`log.md`. **Boundary:** Neither a generated link nor parser acceptance proves
concept conformance. A stricter local link checker is an application policy, not
a restatement of OKF consumer rejection rules. **Revisit when:** validators and
conformance text align these layers explicitly. **Evidence:** [S1 §§4,6,11](sources.md#s1),
[S2-S3](sources.md#s2), P06.

<a id="q16"></a>
## Q16 — What changed from 0.1 to 0.2, and is a version string enough?

**Specified retrospectively:** Section 13 describes the replacement of
`timestamp` by `generated.at` and of the body citations list by `sources`, with
fallbacks; it lists the trust/lifecycle/computation additions and says other
structure carries forward. **Limit:** An independent 0.1 release snapshot was
not inspected in this observation. Do not turn a retrospective summary into a
byte-for-byte two-release verification. **Proposal:** Issue #24 challenges
same-label timestamp changes; exact commit binding avoids silently conflating
revisions. **Revisit when:** version, errata, release, or compatibility policy
changes. **Evidence:** [S1 §§12-13](sources.md#s1), [D24](sources.md#d24).

<a id="q17"></a>
## Q17 — Is the continuing discussion about frontmatter or the body?

**Observed proposals:** Both are represented: topic leads/deletion/part merging
affect discovery; version preservation, timestamp semantics, and path-valued
metadata affect frontmatter. **Limit:** The checked watchlist is not a census of
the community or evidence of which topic dominates. A proposal is not an
accepted amendment. **Revisit when:** a linked decision or merged specification
change actually settles one of these questions. **Evidence:** [D10-D29](sources.md#d10).

<a id="q18"></a>
## Q18 — Can index freshness be determined mechanically?

**Interpretation:** Given an independently declared expected set D and a
reachable set R, `D - R` detects missed discovery targets. Existence, local link
resolution, and deterministic generated-byte freshness can be checked. **Limit:**
These checks do not by themselves choose a meaningful classification, judge
summary quality, prove external URLs live, or establish OKF conformance. The
completeness of D must be justified independently of existing index entries.
A machine must be able to report uncertainty rather than inventing authority.
No audit status enum or mutation algorithm is standardized by the inspected
OKF text. **Revisit when:** upstream defines inventories or discovery validation.
**Evidence:** design analysis of [S1 §§8,11](sources.md#s1), not an upstream requirement.
