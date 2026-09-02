<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Risk-domain analysis reference

This is a **provider-neutral procedure-support reference** for `pr-review`. It helps execute the multi-pass candidate-discovery and falsification procedure from the frozen review bundle. It does not define defects, severity, review completion, merge authorization, or provider output. The retained semantic review policy remains authoritative for those meanings.

Select applicable domains from the independently established **Observed** change model. Do not activate a domain merely because a pull-request description names a technology or risk, and do not mechanically run every domain as an approval checklist. A domain is useful when the actual operations, state transitions, authority boundaries, consumers, or failure modes make its questions material.

| Domain | Typical semantic trigger | Reference |
| --- | --- | --- |
| Identity and authority | identity selects authority, scope, ownership, or privilege | `identity-and-authority.md` |
| Namespace and indirection | a name can resolve through aliases, redirects, parents, links, or other indirection | `namespace-and-indirection.md` |
| State mutation and recovery | the change creates, replaces, deletes, migrates, rolls back, or partially mutates state | `state-mutation-and-recovery.md` |
| Concurrency and temporal consistency | a correctness decision can become stale before or during use | `concurrency-and-temporal-consistency.md` |
| Privileged execution | inputs, environment, configuration, or artifacts influence privileged/executable behavior | `privileged-execution.md` |
| Persistence and integrity | durable data, schema, serialization, migration, or stored identity changes | `persistence-and-integrity.md` |
| External interaction | requests, callbacks, remote resources, redirects, or externally controlled responses cross a boundary | `external-interaction.md` |
| Resource behavior | work, memory, descriptors, storage, retries, fan-out, or cleanup can scale or accumulate | `resource-behavior.md` |
| Build, provenance, and CI | trusted bytes, generated artifacts, dependencies, runtime selection, tests, or CI establish evidence | `build-provenance-and-ci.md` |
| Consumer and execution paths | correctness depends on what a downstream consumer actually receives or executes | `consumer-and-execution-paths.md` |

The references intentionally describe failure mechanisms rather than required APIs. Concrete implementation techniques may be useful evidence, but no language, framework, library, operating system, provider, or tool name becomes a universal requirement by appearing in an example.

Use candidate seeds to broaden discovery, then apply the procedure's aggressive falsification pass. A seed that is unreachable, already prevented, outside change causality, or materially under-evidenced must be discarded rather than promoted to a finding.
