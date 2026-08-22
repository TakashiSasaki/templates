# Choosing an implementation runtime

An **implementation runtime** is the implementation ecosystem and operational choices used to build and run the artifact. Select one after identifying the artifact's actual requirements. The selection starts with the implementation language/runtime and dependency workflow; `RUNTIME.md` records the exact commands, environment, distribution, and deployment choices. Runtime neutrality is a composition-source property, not a requirement that every consumer support every ecosystem.

## Questions to answer

- Which libraries are required?
- Is startup latency important for ad hoc commands or stdio child processes?
- Must a CLI be distributed as a standalone executable?
- Which operating systems must be supported?
- Is the implementation mostly subprocess orchestration, structured-data processing, filesystem work, or network access?
- Is the selected protocol/SDK support mature enough for every claimed interface?
- Can adapters share one tested application/domain implementation?
- Does the dependency workflow provide a reproducible lockfile where reproducibility matters?
- Can cancellation, timeout, connection cleanup, and process shutdown be made deterministic?

## MCP SDK evaluation

When `capability.mcp` is selected, do not choose an SDK merely because it can start a server or perform one tool call. Evaluate the exact protocol revision, discovery/negotiation model, schema support, result preservation, pagination, cancellation, Streamable HTTP security, extension gating, and test utilities recorded in `RUNTIME.md`.

Prefer an official SDK when it correctly implements the required revision. A hand-written protocol layer requires an explicit interoperability reason and broader conformance tests.

## Ecosystem selection

Python is often suitable for filesystem work, validation, data transformation, and mature libraries. Node.js/TypeScript is often suitable for Web-oriented tooling and npm ecosystem libraries. Go, Rust, JVM languages, .NET, or another compiled runtime may be preferable for startup time, single-file distribution, or deployment constraints.

Select one package/dependency workflow for the implementation. Do not add competing manifests or lockfiles for unused ecosystems.

## Lockfile rule

Commit the lockfile used by the selected workflow when reproducibility requires it. Do not commit lockfiles for unused package managers.

## Secondary interfaces do not require secondary languages

A single implementation language can expose CLI, MCP, browser, and service adapters. Multiple public interfaces are not by themselves a reason to introduce multiple implementation languages.
