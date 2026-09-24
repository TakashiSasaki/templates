# Core policy navigation

## Change and evidence

- [Acceptance baseline](acceptance-baseline.md) - Establish the minimum evidence for a completed change.
- [Change contract](change-contract.md) - Bind requested work to explicit scope and outcomes.
- [Change scope](change-scope.md) - Keep mutation within the authorized change boundary.
- [Semantic decision gates](semantic-decision-gates.md) - Surface decisions that cannot be inferred mechanically.
- [Evidence layers](evidence-layers.md) - Separate source, local, CI, review, and external evidence.
- [Truthful reporting](truthful-reporting.md) - Report state, limitations, and unperformed actions accurately.

## Safety and validation

- [Adversarial invariant testing](adversarial-invariant-testing.md) - Exercise negative paths and invariant failures.
- [Compatibility](compatibility.md) - Preserve declared compatibility boundaries.
- [Destructive actions](destructive-actions.md) - Guard irreversible or difficult-to-recover mutations.
- [Generated artifacts](generated-artifacts.md) - Keep projections tied to their authoritative source.
- [Regression safety](regression-safety.md) - Add regression evidence before changing behavior.
- [Testing](testing.md) - Select and report tests proportionate to risk.
- [Transaction ownership](transaction-ownership.md) - Keep mutation ownership and recovery explicit.
- [Validation operation binding](validation-operation-binding.md) - Bind checks to the operation they qualify.

## Repository topology and completion

- [Local checkout topology discovery](local-checkout-topology-discovery.md) - Discover checkout and worktree topology before mutation.
- [Policy applicability](policy-applicability.md) - Scope instruction and policy applicability to the governed target.
- [Repository topology discovery](repository-topology-discovery.md) - Discover repository authority and projection topology.
- [Repository change anti-stall](repository-change-anti-stall.md) - Keep long-running work moving with bounded next actions.
- [Repository change completion](repository-change-completion.md) - Close work only after required evidence and handoff.
