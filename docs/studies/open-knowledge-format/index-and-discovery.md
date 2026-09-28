# Index structure and progressive discovery

This document distinguishes the [section 8 contract](sources.md#s1) from one
implementation and from design analysis. It is not a local enforcement profile.

## What the specification actually supplies

Indexes are optional at any directory level. They enumerate available content
for progressive disclosure. The ordinary no-frontmatter rule has a bundle-root
version-key exception. The body consists of headed sections; the example uses
Markdown link entries and short descriptions. Reusing the linked concept's
frontmatter description is a recommendation. Producer generation and consumer
synthesis are both permitted. [S1 §§8,11,12](sources.md#s1)

This locally authored illustration follows the example shape; it is not a
normative grammar:

```markdown
# Topics

* [Queue semantics](topics/queues.md) - Delivery and ordering guarantees.

# Collections

* [Storage](storage/) - Storage models and related resources.
```

## Syntax and semantic questions kept separate

| Concern | Explicit contract/example | What is not settled by it |
| --- | --- | --- |
| Sections | One or more headed sections. | Complete section grammar or empty-section handling. |
| Heading levels | Examples and generator use sibling H1 headings. | Exactly one H1, H1-only, or rules for H2/H3 nesting. |
| Grouping | Concepts grouped under headings. | Mandatory type-based grouping or fixed heading names. |
| List spelling | Example uses `*` and a link/description separator. | Mandatory marker byte, ordered-list treatment, escaping/line wrapping. |
| Indentation | Example is top-level and unindented. | OKF-specific width or nested-list limit. |
| Extra blocks | Descriptions appear in entries. | Permission/prohibition and preservation for independent prose, tables, code or HTML. |
| Targets | Concepts and a directory appear in examples; sample also indexes Python. | Closed file-type whitelist and universal auxiliary-artifact support. |
| Target depth | Relative paths are illustrated. | Immediate-child-only rule or mandatory physical-level traversal. |
| Order | No universal ordering rule supplied. | Alphabetic/type sorting as a normative requirement. |

These distinctions address Q07-Q13. A producer may choose a narrower grammar,
but should name it as its own profile. A consumer may support richer Markdown,
but that does not establish a guarantee for other consumers. The exact Markdown
parser/dialect and the interpretation of its AST must be stated by an
implementation rather than invented on behalf of OKF. [S1](sources.md#s1)

## Physical containment is not necessarily the discovery graph

The user's concern was a chain such as:

```text
bundle/
  index.md
  engineering/storage/consistency/model.md
```

A discovery path can be designed as either multiple intermediate indexes or a
single link to the deep concept. A directory can likewise be reached by a deep
relative link. No immediate-child-only sentence was found in section 8, but
that absence is not an explicit guarantee that every consumer handles every
such choice. The reference generator chooses immediate children and ancestor
indexes instead. [S1 §§6,8](sources.md#s1) [S2](sources.md#s2)

**Design interpretation:** Place an intermediate discovery step when it adds a
useful distinction, a stable subject boundary, or a manageable choice set. Do
not add a fetch merely to mirror a structural directory. Conversely, do not
flatten hundreds of leaves simply to minimize hop count. A stable semantic
category with one current item can still justify its own entry point.

This can be reasoned about as a tradeoff among fetch cost, information presented
per step, and decision usefulness. It is not an OKF optimization function and no
numeric fan-out/depth threshold is implied. Direct shortcuts and a longer
category route to the same target can coexist in a graph; duplication of routes
need not mean duplicate ownership or duplicate concept content.

## Directory links and serving

The specification illustrates `subdir/`; the checked-in generator and sample
also use `subdir/index.md`. A filesystem, Git browser, and static HTTP
server need not resolve the directory spelling identically. Index semantics and
server defaults are different contracts. No prescribed HTTP redirect, directory
listing response, or automatic Markdown-index response was found in section 8.
[S1](sources.md#s1) [S2](sources.md#s2) [S6](sources.md#s6)

## Auxiliary resources and derived views

The terms auxiliary resource and derived/consumer artifact are analytical
categories in this study, not a standardized OKF payload taxonomy.

The checked-in Python-attester link is evidence of an auxiliary-resource use,
not evidence that Python becomes a concept. SQL and schemas can be modeled as
referenced resources without changing their formats. HTML visualization is a
derived consumer artifact; its existence does not prove that an index must list
it or that it belongs to the same normative payload class. See Q06-Q07 for the
limits of this reading. [S5](sources.md#s5) [S7](sources.md#s7)

## Freshness and curation

For an application-defined expected set D and reachable set R, `D - R` can expose
missing discovery links only if D is independently trustworthy. Link checks do
not decide whether prose is accurate or a grouping is useful. Full regeneration
also needs a preservation contract: the reference generator rewrites indexes
and can lose independently curated descriptions or shortcuts. A local system
can separate authored and generated indexes, but that distinction is not an
upstream ownership schema supplied by section 8. [S2](sources.md#s2) [D26](sources.md#d26)
