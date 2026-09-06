---
id: pull-request.bind-review-result-classification-to-applicable-cycle-and-revision
severity: mandatory
overridable: true
order: 966
---
# Bind review-result classification to the applicable cycle and revision

Before classifying review as pending, complete, problem-free, or containing findings, identify the latest applicable review request for the review purpose being evaluated and bind the classification to that review cycle. Do not let an older completed review establish completion or `no findings` for a later applicable request that is still pending, incomplete, failed, or otherwise unresolved.

Determine applicability by purpose as well as time. A diagnostic whole-stack audit, merge-acceptance review, security review, or other explicitly distinct review purpose does not supersede a different purpose merely because its request is newer. When several requests belong to the same purpose and candidate lineage, the latest applicable request defines the current cycle unless repository authority or the review procedure explicitly establishes different aggregation semantics.

When observed review evidence identifies a reviewed commit, head SHA, stack identity, or other revision binding, compare that binding with the current proposed candidate before relying on the evidence. Classify the evidence as current and applicable only when the required revision relation is established by the applicable review contract. For merge-acceptance evidence governed by the independent exact-head rule, this requires the exact current proposed head. If the candidate head changed after that review, the completed review is stale for merge acceptance. If the required revision binding is absent or its applicability cannot be established, keep the affected completion or no-findings conclusion fail-closed rather than assuming that the review covered the current candidate.

Review-cycle completion applicability and finding applicability are distinct. Evidence from an earlier review cycle must not by itself establish completion or `no findings` for a later cycle, but a material actionable finding reported earlier remains part of the known finding backlog while its causal condition remains applicable to the current candidate and until it has a validated repair or evidence-backed no-change disposition. Do not discard a finding solely because the head changed or a newer review request exists.

When current evidence is insufficient to determine which request a result belongs to, what purpose it served, or whether its revision binding applies to the current candidate, record the ambiguity and do not promote the review state to complete or problem-free. Historical evidence may still be retained for traceability and finding disposition without being accepted as current-cycle completion evidence.
