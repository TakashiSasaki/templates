# Specification, sample, and implementation gaps

All observations below are tied to upstream commit
`ad30107c31c06aec8a7d5636e0d1058118604e6f`. A behavior is not automatically a bug
merely because the standard leaves it open. The purpose is to prevent accidental
promotion of implementation choices into normative constraints.

## Evidence method

The source register identifies [the generator](sources.md#s2),
[its document parser](sources.md#s3), [its tests](sources.md#s4), and
[the description synthesizer](sources.md#s8). The generator and parser were
materialized temporarily outside the repository and their bytes matched the
reported Git blob IDs. Eight synthetic local probes used these exact two
modules with an injected offline description callback. No model/API was called;
no upstream bundle was modified. This was not the upstream full test suite,
production reference-agent execution, or an OKF conformance test.

Inputs and observed outputs are summarized below and recorded in the
[observation](observation-2026-09-28.json). In particular, several probes
intentionally contain invalid or incomplete concepts to observe tolerant
processing; passing through the generator does not make those inputs conformant.

## Gap register

| ID | Evidence and observation | Consequence / unresolved question |
| --- | --- | --- |
| G01 | S1 §§8/12 authorize a root version key; S2 rewrites an eligible index without reading prior bytes. P01 lost `okf_version` and introductory prose. | Permission to generate does not define preservation. PR #25 proposes version-key retention, not general curation retention. |
| G02 | S5 directly indexes `sql_equality.py`; S2 emits file entries only for `.md`. In mixed input P03, a curated Python link vanished; SQL/HTML were not emitted. | Sample capability and generic generator capability differ. Do not infer non-Markdown links are banned. |
| G03 | P02 created all intermediate indexes for one deep concept. S4 tests description reuse for a single child, not collapse of a directory hop. | Immediate-child traversal is the algorithm, not a mandatory discovery-depth rule. |
| G04 | S1 illustrates sibling H1 sections; P07 emits more than one H1 with type groups. | A single document-title H1 with H2 sections, or H1-only restrictions, are application decisions rather than a documented universal grammar. |
| G05 | S1 illustrates directory URLs; S2/S6 use explicit index-file URLs. | Consumer serving/resolution behavior must not be inferred from Markdown alone. |
| G06 | S3 separates parsing and validation; S2 calls parse but not validate. P06 listed frontmatter-free `guide.md` and reserved `log.md` under `Other`. | Parseability, indexing, and concept conformance are not equivalent. Listing a reserved file does not make it a concept. |
| G07 | With a Markdown concept present, P05 emitted links to child directories' indexes even when those indexes were absent. P04, a Python-only root, generated no index. | Generated links do not prove target existence. OKF's tolerant consumer rule and a local strict checker are different requirements. |
| G08 | P08 preserved an existing Python-only index because there were no new eligible entries and the generator skipped its write. | Do not overstate G02 as 'every non-Markdown link is always deleted'; rewrite eligibility matters. |
| G09 | S2 sorts headings/titles but calls S8, which can ask a model for directory descriptions and has a fallback. | Stable ordering is not proof of deterministic full output. The local probes fixed the callback and did not evaluate model variation. |
| G10 | S1 §6.2 gives explicit root-relative and relative forms, while §6.3/§10 examples use unprefixed paths into references. D29 reports conflicting resolution in samples. | Preserve the text/example tension; do not silently add root fallback and describe it as normative. D29's 12-of-12 measurement is the issue author's report, not rerun here. |
| G11 | S1 §11's broad frontmatter/type wording meets the reserved root exception in §§8/12. | Do not require `type` on the root version declaration. The general wording needs scoped reading/clarification. |
| G12 | S1 §§12/13 describes compatibility/versioning; D24 questions unchanged `0.2` labeling after timestamp revisions. | Pin source commits as well as labels. Do not assert that all documents labeled 0.2 have identical semantics. |

## Probe observations

| Probe | Synthetic input | Observed result |
| --- | --- | --- |
| P01 | Root version frontmatter and prose plus one valid concept. | Index rewritten; version block and prose absent. |
| P02 | One concept at `a/b/c/topic.md`. | Root, `a`, `a/b`, and `a/b/c` indexes written; no collapsed deep link. |
| P03 | Valid concept plus Python, SQL, HTML and a curated Python index link. | Only the concept became a file entry in the rewritten root. |
| P04 | Python only, no Markdown. | No indexes written. |
| P05 | One concept plus an auxiliary-only child and an empty child represented by a placeholder. | Root links to two nonexistent child index files. |
| P06 | A conventional log and a heading-only guide, neither with concept metadata. | Both listed as `Other`; no concept validation was invoked by generation. |
| P07 | Two valid concepts of distinct types. | Sibling H1 groups and flat `*` lists emitted. |
| P08 | Existing curated index plus Python only. | Existing index preserved because no entries triggered a rewrite. |

A future fix can change an observation without changing the specification. A
future specification clarification can change an interpretation without changing
code. Record those as different events. Do not make the present generator's
output a golden conformance oracle for future versions.
