# Headless service interface contract

This contract is materialized by `capability.service`. It applies to an independently reachable non-browser service, whether or not the same implementation also exposes CLI, MCP, or Web adapters.

`RUNTIME.md` owns runtime, process, listener, port, container, gateway, and deployment selections. This file owns caller-visible service behavior and its security/lifecycle contract.

## Machine-readable authority

`contracts/service-interface.json` is the canonical machine-readable state for this selected capability. Its lifecycle is `template` -> `planning` -> `product`.

- `template` makes no caller-visible service claim and keeps the operation inventory empty.
- Before product coding, switch to `planning`, select the caller-visible protocol/API surface, and enumerate every intended caller-visible operation by stable `id` and non-empty `purpose`. The protocol is a planning-level contract decision (for example, an explicit HTTP/JSON requirement); do not invent concrete invocation strings or success/negative wire behavior before implementation decisions exist.
- Bind every planned operation exactly to an implementation-evidence planning target `contract-item / service_interface / operation / <operation-id>`, with `integration-test` or `end-to-end-test` proof strength declared before coding. Composition validation must pass in this planning state.
- Promote the same stable IDs and protocol to `product` when concrete invocation/success/negative behavior is known. Product implementation evidence then supplies the executable positive and negative proof across the maintained service boundary.

When `capability.service` is selected, planning implementation evidence cannot validate while this contract is still in `template` mode, and phantom planning target IDs are rejected. Product implementation evidence cannot remain valid while this contract is not in `product` mode. Static source inspection and unit-only proof do not satisfy the service executable-proof obligation.

Keep this narrative contract aligned with the JSON authority. Runtime listener/deployment details remain in `RUNTIME.md`.

## Public reachability

| Item | Selected value |
|---|---|
| Protocol or API surface | TODO |
| Endpoint/listener model | TODO |
| Authentication | TODO |
| Authorization | TODO |
| Exposure/non-loopback policy | TODO |
| Request size limits | TODO |
| Rate limits | TODO |
| Concurrent request policy | TODO |
| State/session model | TODO |

Define how another process or node reaches the service and which identities may invoke it. A listening socket is not proof of application readiness.

## Operation contract

For every maintained operation or operation family, document:

| Item | Selected behavior |
|---|---|
| Inputs and validation | TODO |
| Successful result | TODO |
| Negative domain result | TODO |
| Errors | TODO |
| Side effects | TODO |
| Idempotency/retry | TODO |
| Timeout/cancellation | TODO |
| Required permissions | TODO |

## Health and lifecycle

| Item | Selected value |
|---|---|
| Readiness check | TODO |
| Liveness check | TODO |
| Startup behavior | see `RUNTIME.md` |
| Graceful shutdown | TODO |
| In-flight request termination | TODO |
| Restart/stale-process behavior | TODO |

Readiness must demonstrate that the service can accept the class of work claimed by the contract. Liveness answers a different question and must not be substituted for readiness.

## Security boundary

- authenticate and authorize before operation dispatch where practical;
- validate request size and rate limits at the service boundary;
- do not trust network locality as identity;
- require an explicit transport-security design for exposure beyond a trusted local boundary;
- keep secrets out of logs, public errors, committed configuration, and process arguments where safer mechanisms exist;
- make destructive and externally visible actions explicit and approval-gated where required.

## Failure isolation

Document whether failure is isolated from co-located CLI, MCP, or Web adapters. Shared process/container deployment does not merge interface contracts or health semantics.

## Semantic equivalence

When another maintained interface exposes the same operation under the same identity, authorization, configuration, and workspace policy, inputs, results, side effects, and safety checks must have equivalent meaning.

## Required tests

Test at least:

- authentication and authorization allow/deny paths;
- input validation and size limits;
- representative successful and negative domain results;
- timeout and cancellation;
- readiness versus liveness;
- graceful shutdown with in-flight work;
- restart/stale-process handling;
- non-loopback exposure policy where supported;
- semantic equivalence with other maintained adapters.

## Decision rationale

Explain why an independently reachable service is required, why its exposure and deployment model are appropriate, and which failure/security properties remain invariant across supported deployments.

TODO
