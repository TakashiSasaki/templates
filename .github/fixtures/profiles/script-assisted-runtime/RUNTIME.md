# Runtime decision record

## Status

Selection status: SELECTED

## Primary implementation

| Item | Selected value |
|---|---|
| Language | Ruby |
| Runtime | CRuby |
| Minimum runtime version | 3.1 |
| Dependency/package manager | NONE; the helper uses only the Ruby standard library |
| Project manifest | NONE |
| Lockfile policy | NONE |
| Source layout | `scripts/normalize.rb` |
| Supported operating systems | Linux, macOS, and Windows environments with CRuby 3.1 or newer |

## Commands

Run every command from the skill root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | NONE; verify the existing runtime with `ruby --version` |
| Run in place | `ruby scripts/normalize.rb INPUT OUTPUT` |
| Agent launcher | `ruby scripts/normalize.rb INPUT OUTPUT` |
| Test | `ruby -c scripts/normalize.rb` followed by representative helper execution |
| Lint/static analysis | `ruby -c scripts/normalize.rb` |
| Format check | `ruby -c scripts/normalize.rb` |
| Build/package | NOT APPLICABLE |

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive containing `SKILL.md`, `RUNTIME.md`, and `scripts/normalize.rb` |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | not supported |
| Human Web interface distribution | not supported |
| Service integration | none |
| Version source of truth | Repository commit containing the skill files |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| NONE | NO | The helper accepts only positional input and output paths | NO |

## Decision rationale

CRuby 3.1 or newer is selected because the helper is a small portable Ruby script that uses only standard-library file and encoding APIs. A separate runtime record is retained to make the supported interpreter, exact invocation, validation command, distribution boundary, and absence of dependencies explicit without promoting the helper to a packaged public CLI or adding unused manifests and lockfiles.
