# Runtime selection

Select a runtime after identifying the skill's actual requirements. Runtime neutrality is a template property, not a requirement that every concrete skill support every ecosystem.

## Questions to answer

- Which libraries are required?
- Is startup latency important for ad hoc stdio MCP sessions?
- Must the CLI be distributed as a standalone executable?
- Which operating systems must be supported?
- Is the skill mostly subprocess orchestration, structured-data processing, or network access?
- Will contributors already have a particular runtime?
- Is the MCP SDK sufficiently mature in the selected language?

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
