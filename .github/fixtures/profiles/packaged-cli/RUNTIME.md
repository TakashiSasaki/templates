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

Run all repository-local commands from the repository root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` |
| Run in place | `ruby bin/text-stat --help` |
| Agent launcher | `ruby bin/text-stat` |
| Test | `ruby tests/test_text_stat.rb` |
| Lint/static analysis | `ruby -c src/text_stat.rb && ruby -c bin/text-stat` |
| Format check | `ruby -c src/text_stat.rb && ruby -c bin/text-stat` |
| Build/package | `gem build text-stat.gemspec` |
| Install packaged command locally | `gem install --no-document --install-dir .local/gems --bindir .local/bin ./text-stat-1.0.0.gem` |

The local installation keeps the gem and executable inside the repository working tree. Activate those paths before invoking the preferred installed interface.

| Shell | Exact command |
|---|---|
| POSIX shell | `export GEM_HOME="$PWD/.local/gems"; export GEM_PATH="$GEM_HOME"; export PATH="$PWD/.local/bin:$PATH"; text-stat --help` |
| PowerShell | `$env:GEM_HOME="$PWD/.local/gems"; $env:GEM_PATH=$env:GEM_HOME; $env:PATH="$PWD/.local/bin;$env:PATH"; text-stat --help` |

The activation commands above persist for the current shell session and apply only to the repository-local installation. A normal RubyGems installation may use the environment's configured gem home and executable directory instead.

### Packaged CLI commands

| Purpose | Exact command |
|---|---|
| Human CLI | `text-stat` |

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
| `GEM_HOME` | Only for the repository-local packaged installation | Locate the locally installed gem | NO |
| `GEM_PATH` | Only for the repository-local packaged installation | Restrict gem lookup to the local installation | NO |
| `PATH` | Only for the repository-local packaged installation | Make `.local/bin/text-stat` available as `text-stat` | NO |

No application-specific environment configuration is required.

## Decision rationale

Ruby provides the standard-library JSON, option parsing, package, and test support needed for a small deterministic CLI without runtime dependencies. A gem supplies a stable installed command while the in-place launcher exercises the same implementation.
