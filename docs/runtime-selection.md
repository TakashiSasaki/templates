# Runtime selection

Select a runtime after identifying the skill's actual requirements. Runtime neutrality is a template property, not a requirement that every concrete skill support every ecosystem.

## Questions to answer

- Which libraries are required?
- Is startup latency important for ad hoc stdio MCP invocations and child-process lifetime?
- Must the CLI be distributed as a standalone executable?
- Which operating systems must be supported?
- Is the skill mostly subprocess orchestration, structured-data processing, or network access?
- Will contributors already have a particular runtime?
- Is the MCP SDK sufficiently mature in the selected language?
- Does the SDK explicitly support the required protocol revisions and modern/initialization-era negotiation policy?
- Can the SDK preserve raw result objects, unknown extension metadata, opaque cursors, and revision-specific list-cache fields?
- Does its schema layer support JSON Schema 2020-12 and explicit supported `$schema` values where required?
- For `2026-07-28`, does it support `server/discover`, per-request metadata, modern multi-round-trip `input_required`, required Streamable HTTP headers, JSON and SSE responses, and `x-mcp-header`?
- For `2025-11-25` or earlier compatibility, does it support `initialize`, negotiated capabilities, required server-to-client request handlers, elicitation actions, and applicable legacy HTTP behavior?
- Does it expose deterministic cancellation, timeout, connection cleanup, and child-process shutdown primitives?
- Can non-interactive additional-input behavior be implemented and tested without unexpected terminal prompts?
- Can stdio and Streamable HTTP adapters share one server factory or operation registry?

## MCP SDK evaluation

Do not select an SDK only because it can start a server or perform one `tools/call`. Evaluate the exact feature set the skill claims:

- protocol revision and negotiation support;
- standard method and result-type coverage;
- lossless access to protocol objects and `_meta`;
- pagination and cache semantics;
- schema dialect support;
- modern and initialization-era interaction models;
- cancellation and cleanup behavior;
- Streamable HTTP security and request-header support;
- extension gating and unknown-extension preservation;
- test utilities for both success and failure paths.

Prefer an official SDK when it implements the required revision correctly. A hand-written protocol layer requires an explicit interoperability reason and substantially broader conformance tests.

## Python

Python is often suitable for filesystem work, validation, data transformation, and mature libraries. A concrete skill may use pip, uv, pip-tools, Poetry, or another justified workflow. Do not add multiple competing Python dependency files.

If uv is selected, state whether it is required for users or only for development. If uv is not selected, commands must not assume it.

## Node.js and compatible runtimes

Node.js or TypeScript is often suitable for web-oriented tooling and npm ecosystem libraries. Select npm, pnpm, yarn, or bun based on the concrete distribution and contributor environment.

If bun is selected, state whether it is used only as a package manager, as the execution runtime, or both. Do not assume that all Node.js dependencies behave identically under bun without tests.

## Other runtimes

Go, Rust, JVM languages, .NET, or a compiled binary may be better when single-file distribution, startup time, or strict deployment constraints dominate.

## Lockfile rule

Commit the lockfile used by the selected workflow when reproducibility requires it. Do not commit lockfiles for unused package managers.

## Secondary interfaces do not require secondary languages

A Python implementation can expose CLI and MCP. A TypeScript implementation can expose CLI and MCP. The existence of multiple interfaces is not a reason to introduce multiple implementation languages.
