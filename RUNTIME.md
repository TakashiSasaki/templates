# Runtime decision record

Complete this file before implementing a concrete skill. This is the authoritative index of toolchain and command choices.

## Status

```text
Selection status: UNSELECTED
```

Change the status to `SELECTED` after completing every required field.

## Primary implementation

| Item | Selected value |
|---|---|
| Language | TODO |
| Runtime | TODO |
| Minimum runtime version | TODO |
| Dependency/package manager | TODO |
| Project manifest | TODO |
| Lockfile policy | TODO |
| Source layout | TODO |
| Supported operating systems | TODO |

Examples of valid decisions include Python with pip, Python with uv, Node.js with npm, Node.js with pnpm, or bun as the runtime and package manager. These are examples, not defaults.

## Commands

Commands must work from an explicitly documented working directory.

| Purpose | Exact command |
|---|---|
| Install development dependencies | TODO |
| Run in place | TODO |
| Human CLI | TODO |
| Agent launcher | TODO |
| Start stdio MCP server | TODO or NOT SUPPORTED |
| Invoke MCP ad hoc | TODO or NOT SUPPORTED |
| Test | TODO |
| Lint/static analysis | TODO |
| Format check | TODO |
| Build/package | TODO or NOT APPLICABLE |

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone / submodule / release archive / other: TODO |
| CLI distribution | TODO |
| MCP distribution | bundled / separate package / not supported: TODO |
| Version source of truth | TODO |

## Environment and configuration

Document required environment variables without placing secrets in this repository.

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| TODO | TODO | TODO | TODO |

## Decision rationale

Explain why the selected runtime and package manager fit this skill better than the credible alternatives.

TODO
