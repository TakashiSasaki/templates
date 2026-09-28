# Source register and observation scope

Baseline observation: **2026-09-28**. Upstream discovery branch `main` resolved to
`ad30107c31c06aec8a7d5636e0d1058118604e6f`; its `SPEC.md` labels itself **0.2**.
The [machine-readable observation](observation-2026-09-28.json) records source
identities, question IDs, observed discussion states, and synthetic probe results.
Git blob identity does not establish authenticity, redistribution rights, or
upstream endorsement of this study. No external bytes are committed here.

## Pinned specification and implementation

<a id="s1"></a>
### S1 — Specification

[SPEC.md at the inspected commit](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/SPEC.md)

Git blob: `c06e3eede0c910d0ecf12524c34204156f8795ac`.
Relevant sections: 2-4 (identity/bundle/concepts), 5 (provenance/trust/lifecycle),
6-9 (paths/index/log), 10 (computation), 11-13 (conformance/versioning/history).
Section numbers refer to these bytes, not an arbitrary future `main`.

<a id="s2"></a>
### S2 — Reference index generator

[index.py](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/src/reference_agent/bundle/index.py)

Git blob: `68cccd4cea6e8a583ab7929744348f4d82ff8364`.
Read in full; exact blob matched before the eight local generator probes.

<a id="s3"></a>
### S3 — Reference document parser

[document.py](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/src/reference_agent/bundle/document.py)

Git blob: `b770a92f33adf9942e2932529308d066430b02a6`.
Read in full; exact blob matched before probes. Parsing and validation are separate.

<a id="s4"></a>
### S4 — Reference index tests

[test_index.py](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/tests/test_index.py)

Git blob: `d9a0ba61cccd8bfedb3b4c0042c950560b4323dd`.
Read, not executed as the upstream test suite. It tests grouping, relative child
links, an empty-only tree, and single-child description reuse.

<a id="s5"></a>
### S5 — Sample auxiliary-resource index

[acme_retail/attesters/index.md](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/bundles/acme_retail/attesters/index.md)

Git blob: `c22f7f68b33072e17dddc36772bb736b6333b9c9`.
Direct Python-attester link observed. This is a sample, not a specification amendment.

<a id="s6"></a>
### S6 — Sample root index

[acme_retail/index.md](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/bundles/acme_retail/index.md)

Git blob: `f8bc4b247169a5d2c5823e0e9bd4608bbbf2c210`.
Explicit child `index.md` links observed; no `viz.html` link in this file.
This is not a survey of all bundles or all producers.

<a id="s7"></a>
### S7 — Reference viewer documentation

[README.md](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/README.md)

Git blob: `0e88bcf81ca9ade7e830f077f9687bb89ec0319c`.
The inspected Visualize section describes `viz.html` as generated consumer output.
The viewer itself was not executed or security-audited.

<a id="s8"></a>
### S8 — Directory description synthesizer

[synthesizer.py](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/src/reference_agent/bundle/synthesizer.py)

Git blob: `489aacafc4d847ed39d6c5318ebf0f89d845b95f`.
Read in full. It calls a model and has fallback behavior. It was replaced only at
the dependency-injection boundary by an offline callback for the local probes.

## Community watchlist

The following issue bodies and metadata were read on 2026-09-28. Except where
explicitly stated otherwise, comment threads were **not** re-read. State is an
observation, not a conclusion about consensus. Issue text is mutable; the
`updated_at` values in the observation aid comparison but do not pin immutable
issue-body bytes. No linked external experiments were rerun.

<a id="d10"></a>
- [D10: topic lead concepts](https://github.com/GoogleCloudPlatform/open-knowledge-format/issues/10): open; directory-topic placement proposal, relevant to Q08/Q10/Q13.
<a id="d11"></a>
- [D11: deletion semantics](https://github.com/GoogleCloudPlatform/open-knowledge-format/issues/11): open; discovery of removed concepts, relevant to Q11/Q15/Q17. The issue's own terminology is not imported as normative text.
<a id="d24"></a>
- [D24: version label and timestamp changes](https://github.com/GoogleCloudPlatform/open-knowledge-format/issues/24): open; relevant to Q05/Q16.
<a id="d25"></a>
- [D25: preserve root version on regeneration](https://github.com/GoogleCloudPlatform/open-knowledge-format/pull/25): open, unmerged; proposal head `e23c32f73c222f94a29201dfa0659a23a0dd612c`; relevant to Q01/Q14 and G01. The PR's test claims were not independently rerun.
<a id="d26"></a>
- [D26: bundle parts and reserved-name collisions](https://github.com/GoogleCloudPlatform/open-knowledge-format/issues/26): open; relevant to Q01/Q10/Q14/Q17. Also asks how to retain descriptions absent from concept frontmatter.
<a id="d28"></a>
- [D28: generated versus revised/edited](https://github.com/GoogleCloudPlatform/open-knowledge-format/issues/28): open; relevant to Q05/Q16/Q17.
<a id="d29"></a>
- [D29: frontmatter path resolution](https://github.com/GoogleCloudPlatform/open-knowledge-format/issues/29): open; relevant to Q05/Q12 and G10.

Earlier discussion also mentioned relationship proposals and an older repository's
root-metadata issue. Those are leads for a future investigation, not verified
amendments in this observation. This watchlist is deliberately non-exhaustive;
it cannot substantiate a claim about the dominant direction of the community.
