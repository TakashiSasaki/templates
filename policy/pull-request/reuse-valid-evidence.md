---
id: pull-request.reuse-valid-exact-head-evidence
severity: mandatory
overridable: true
order: 975
---
# Reuse valid pull-request evidence until an applicable binding changes

Once scope, validation, review, or other acceptance evidence has been accepted for a defined proposed-head identity and applicability context, reuse that evidence while the facts that bind it remain unchanged.

Do not make repeated observations, extra review cycles, waiting periods, or redundant evidence collection mandatory solely because they are more conservative. Additional diagnostic work may be performed when concrete uncertainty exists, but it must not silently enlarge the acceptance baseline or become a new merge requirement unless current repository policy requires it.

Reacquire only the evidence affected by a concrete invalidation signal. A changed proposed head invalidates evidence bound to the former head. Target-branch movement requires impact evaluation, but it does not by itself invalidate unrelated exact-head evidence whose applicability and semantic basis remain unchanged. Changes to scope, validation definitions, review state, or another evidence-binding condition invalidate the corresponding evidence. Elapsed time alone does not invalidate exact-head evidence unless current repository policy defines an explicit freshness limit.

If the continued validity of relied-upon evidence cannot be established, fail closed and reacquire the affected evidence rather than inventing a broader gate.
