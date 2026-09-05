---
id: pull-request.disposition-known-findings-before-review-reacquisition
severity: mandatory
overridable: true
order: 963
---
# Disposition known findings before review reacquisition

Before intentionally starting a new merge-acceptance review acquisition cycle for a proposed candidate, account for every material actionable finding already known from submitted review evidence and applicable to that candidate. For each such finding, establish either a repair validated for the current proposed head or an evidence-backed no-change disposition validated against the current proposed head and applicable authority. Do not intentionally request another merge-acceptance review merely to accumulate more findings while a known material actionable finding remains without one of those validated outcomes.

Apply this requirement independently of provider representation. A finding in a resolvable thread, a top-level review body, a summary, or another non-resolvable review surface remains subject to the same disposition requirement when it is independently actionable. Provider thread resolution is bookkeeping and does not itself establish semantic closure.

Treat reviewer text as a defect hypothesis rather than authority. A finding first reported against an older head may be re-evaluated against the current proposed head; if current evidence falsifies it, record the decisive no-change disposition instead of making an appeasement edit. Do not force an unrelated suggestion into the current pull-request scope solely to clear the reacquisition gate.

This rule governs intentional acquisition of a new merge-acceptance review cycle. It does not require delaying an urgent operational, security, or data-integrity repair in order to batch review work; does not prohibit naturally triggered CI or review-provider behavior; and does not require waiting for hypothetical future findings. When an explicit human-handoff procedure authorizes one final diagnostic whole-stack audit, perform it only after known material findings have received the validated dispositions required above. Such a diagnostic audit remains distinct from merge-acceptance evidence and does not satisfy or waive the independent exact-head review requirements for later merge authorization.
