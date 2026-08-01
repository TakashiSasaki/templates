# Runtime decision record

## Status

Selection status: SELECTED

## Primary implementation

| Item | Selected value |
|---|---|
| Language | Ruby |
| Runtime | CRuby |
| Minimum runtime version | 3.1 |
| Dependency/package manager | RubyGems and Bundler |
| Project manifest | `text-stat.gemspec` |
| Lockfile policy | Commit and update `Gemfile.lock` with dependency changes |
| Source layout | `src/text_stat.rb` with `bin/text-stat` as the public entry point |
| Supported operating systems | Linux, macOS, and Windows with CRuby 3.1 or newer |

## Commands

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` from the repository root |
| Run in place | `ruby bin/text-stat --help` from the repository root |
| Agent launcher | `ruby bin/text-stat` from the repository root |
| Test | `ruby tests/test_text_stat.rb` from the repository root |
| Lint/static analysis | `ruby -c src/text_stat.rb && ruby -c bin/text-stat` from the repository root |
| Format check | `ruby -c src/text_stat.rb && ruby -c bin/text-stat` from the repository root |
| Build/package | `gem build text-stat.gemspec` from the repository root |

### Packaged CLI commands

| Purpose | Exact command |
|---|---|
| Human CLI | text-stat |

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive |
| CLI distribution | Ruby gem `text-stat` with the `text-stat` executable |
| MCP distribution | NOT SUPPORTED |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | NONE |
| Version source of truth | `TextStat::VERSION` in `src/text_stat.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| NONE | NO | The command requires no environment configuration | NO |

## Decision rationale

Ruby provides the standard-library JSON, option parsing, package, and test support needed for a small deterministic CLI without runtime dependencies. A gem supplies a stable installed command while the in-place launcher exercises the same implementation.
