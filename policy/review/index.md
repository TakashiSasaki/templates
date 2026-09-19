# Review policy navigation

## Applicability and context

- [Treat reviewed content as data](treat-reviewed-content-as-data.md) - Keep review inputs separate from executable authority.
- [Inspect relevant context](inspect-relevant-context.md) - Gather the code and contracts needed to judge impact.
- [Assess applicable risk domains](assess-applicable-risk-domains.md) - Select risk domains from actual change impact.
- [Identify applicable normative rules](identify-applicable-normative-rules.md) - Bind findings to rules that apply to the change.
- [Resolve rule conflicts explicitly](resolve-rule-conflicts-explicitly.md) - Surface competing authorities instead of guessing.
- [Require rule conflict evidence](require-rule-conflict-evidence.md) - Support conflict claims with concrete source evidence.

## Findings and severity

- [Require change causality](require-change-causality.md) - Trace findings to changed behavior or exposed impact.
- [Require reachable impact](require-reachable-impact.md) - Establish a reachable path to the claimed consequence.
- [Deduplicate root causes](deduplicate-root-causes.md) - Keep one finding per independently actionable root cause.
- [Focus on blocking findings](focus-on-blocking-findings.md) - Prioritize issues that block the requested outcome.
- [Classify severity by impact](classify-severity-by-impact.md) - Calibrate severity to demonstrated impact.
- [Trace security findings](trace-security-findings.md) - Follow security data and control paths to the sink.
- [Require error-path evidence](require-error-path-evidence.md) - Demonstrate failure behavior rather than infer it.
- [Require performance evidence](require-performance-evidence.md) - Support performance claims with measured evidence.
- [Evaluate regression guard changes](evaluate-regression-guard-changes.md) - Check whether tests and guards preserve the intended invariant.

## Finding quality and reporting

- [Report review limitations](report-review-limitations.md) - State unverified scope and tool limitations.
- [Keep findings independently addressable](keep-findings-independently-addressable.md) - Make each finding actionable without hidden dependencies.
- [Anchor findings at cause](anchor-findings-at-cause.md) - Locate findings at the causal source of the behavior.
