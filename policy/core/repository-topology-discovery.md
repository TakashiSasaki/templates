---
id: core.discover-repository-topology-fail-closed
severity: mandatory
overridable: false
order: 45
---
# Discover repository topology fail-closed before mutation

Before planning repository mutations, inspect repository-local authority instructions
and the declaration at `contracts/repository-topology.json`. Absence selects no
explicit Composition topology; it never overrides authority instructions or proves
that branch histories are related. A present but unreadable, unsafe, malformed, or
unsupported declaration must halt dependent operations.

Composition owns topology semantics. Consume its immutable contract and validator
rather than maintaining an independent Policy definition. The operational adapter
uses the Composition snapshot identified in `agent_policy/_topology_contract/source.json`;
consumer schema files cannot relax its validation. Validation of a declaration is
not proof of the live Git graph. Before mutation, independently verify the current
branch, authority ancestry, immutable gitlinks, submodule repository identity, and
projection consistency against that declaration. Perform operations only on the
corresponding authority and refresh affected bindings before use.
