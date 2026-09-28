# Revisit protocol for OKF evolution

This is a research-maintenance method for this informative study, not an OKF
producer requirement, repository-wide operating policy, or automatic adoption
mechanism. Keep the [question register](questions.md) stable while the evidence
changes. Start with the [source register](sources.md) and its dated observation.

## When to revisit

A version bump is one trigger, not the only trigger. Recheck when specification
bytes change under the same label, reference code or samples change, an issue
acquires a concrete resolution, a proposed PR merges, or a new producer/consumer
exposes a counterexample. A closed issue alone is not proof that its proposed
rule was accepted. A merged code fix alone is not a specification amendment.

## Evidence-preserving procedure

1. Resolve upstream discovery references and record the exact specification and
   implementation commits separately. Read their actual declared versions; do
   not assume the same tag covers both. Keep old observations available.
2. Read changed normative passages in context, including conformance and
   exception clauses. Record whether wording is a requirement, recommendation,
   example, explicit permission, or unresolved silence. Do not infer permission
   solely from absence of a ban, or infer a ban from a minimal example.
3. Inspect the reference generator, parser/validator, tests, samples, and relevant
   consumer behavior independently. Code is not automatically a normative oracle.
   Record which files, comments, issue revisions and external experiments were
   actually read or executed; uninspected references remain leads.
4. Revisit each affected Q/G identifier using the matrix below. Preserve the
   original question, old answer, new answer, change reason, supporting source,
   and applicable specification/implementation revisions. A new local preference
   does not close an upstream ambiguity.
5. Add a dated observation instead of overwriting the old observation's date,
   version, pins, or discussion states. Correct an error transparently with its
   reason; do not rewrite history to make an old conclusion look newly verified.
6. Update the current reading guide and cross-links to the new observation. Keep
   explicit labels for historical evidence, superseded interpretations, newly
   answered questions, and questions still open. Recheck generated/prose examples
   separately from the actual upstream requirement.
7. Run offline integrity checks. A link/pin/coverage check validates the study's
   organization, not the truth of an interpretation or OKF conformance. Downstream
   adoption, stricter application profiles, and serving behavior need their own
   explicit decisions outside this study.

## Question-to-change matrix

| Changed surface | Questions / gaps to reconsider | Evidence needed |
| --- | --- | --- |
| Bundle membership and reserved files | Q01-Q02, Q06-Q07, G11 | Definition, exclusions, exceptions, conformance clauses. |
| Concept field catalog and types | Q03-Q05 | Requiredness, value vocabularies, nested shapes, unknown-field behavior. |
| Index grammar | Q08-Q10, G04 | Explicit heading/list/prose rules and independent parser examples. |
| Paths, directories and traversal | Q11-Q13, G03/G05/G07/G10 | Root/file-relative resolution, descendant rules, serving vs logical traversal. |
| Auxiliary and derived artifacts | Q06-Q07, G02/G08 | Payload roles, sample links, generator preservation and consumer support. |
| Generation and curation | Q10/Q14/Q18, G01/G06/G09 | Round-trip ownership, preservation, validation calls, deterministic inputs. |
| Dates, trust and versioning | Q05/Q16, G12 | Exact before/after editions, errata and compatibility statements. |
| Topic leads, deletions, parts or relationships | Q11/Q13/Q15/Q17 | Accepted wording, not just discussion popularity or issue state. |

## Optional reproduction of the pinned implementation observations

[probe_reference.py](probe_reference.py) is locally authored test material. It
loads only the two source paths identified in the observation and refuses a
Git-blob mismatch. It is **not a sandbox**: run it only with independently
trusted source and an independently trusted observation/pin record. Hash equality
establishes identity, not trust. Do not execute arbitrary proposal code merely
because it was linked from a discussion.

The helper requires PyYAML in its execution environment, as the inspected parser
does. It fetches nothing. Obtain and inspect a trusted upstream checkout through
your own approved means, then run from this study directory:

```sh
python probe_reference.py \
  --trusted-upstream-root /path/to/trusted/open-knowledge-format \
  --observation observation-2026-09-28.json
```

The eight synthetic bundles are temporary; the upstream checkout is not edited.
The description callback is an offline stub, not the production model-backed
synthesizer. Exit 0 means the observations match the recorded probe results;
exit 1 means behavior differs from that observation; exit 2 means inputs/source
identity or execution prerequisites could not be validated. None of these is an
OKF conformance verdict. The upstream full test suite is a separate experiment.

When investigating a new revision, inspect it first and use a new observation
with its independently recorded pins. Do not change old pins just to bypass the
identity guard. A mismatch is evidence to investigate, not automatically an
upstream regression. Ordinary repository CI must not fetch or execute upstream
code: it checks the committed study and its locally authored material only.

## Preserve the central design question

Continue to test the user's counterexample: a directory with one concept need
not deserve an extra fetch just because it exists. Compare discovery utility,
fan-out, and retrieval cost without declaring a universal numeric threshold.
If upstream later mandates a different algorithm, retain the distinction between
that new requirement and this earlier design interpretation. Conversely, if the
reference generator continues to create all intermediate indexes, do not treat
that persistence as evidence of a normative immediate-child restriction.
