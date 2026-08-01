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
| Project manifest | `Gemfile` |
| Lockfile policy | The isolated fixture harness resolves dependencies during validation; no generated lockfile is committed. |
| Source layout | `src/text_stats.rb` contains deterministic operation logic and `web/server.rb` contains the Web adapter and lifecycle command. |
| Supported operating systems | Linux with CRuby 3.1 or newer |

## Commands

Run every command from the skill root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` |
| Run in place | `TEXT_STATS_WEB_ENABLED=1 bundle exec ruby web/server.rb` |
| Agent launcher | NOT APPLICABLE |
| Test | `bundle exec ruby tests/test_web_server.rb` |
| Lint/static analysis | `ruby -c src/text_stats.rb && ruby -c web/server.rb && ruby -c tests/test_web_server.rb` |
| Format check | `ruby -c src/text_stats.rb && ruby -c web/server.rb && ruby -c tests/test_web_server.rb` |
| Build/package | NOT APPLICABLE |

### Browser-interface commands

| Purpose | Exact command |
|---|---|
| Start human verification Web UI | `TEXT_STATS_WEB_ENABLED=1 bundle exec ruby web/server.rb` |
| Stop human verification Web UI | `bundle exec ruby web/server.rb --stop` |
| Check human verification Web UI readiness | `bundle exec ruby web/server.rb --health` |

## Optional human verification Web interface deployment

| Item | Selected value |
|---|---|
| Supported | YES |
| Web runtime or entry point | `web/server.rb` using WEBrick 1.9.1 |
| Deployment selection time | startup |
| Supported topologies | same process and listener for the page, static assets, application API, and Web health endpoint |
| Default topology | one explicitly enabled loopback process bound to `127.0.0.1:4567` |
| Shared-listener support | YES |
| Separate-listener support | NO |
| External-origin model | same origin |
| Browser-visible MCP exposure capability | not supported |
| Enablement configuration | Set `TEXT_STATS_WEB_ENABLED=1`; absence or any other value keeps the interface disabled. |

The port may be overridden for local testing, including port `0` for operating-system allocation. The bind address is fixed to `127.0.0.1`; non-loopback values are rejected before listener creation. The process writes its PID to `tmp/text-stats-web.pid` by default so the documented stop command can send TERM. TERM and INT trigger graceful WEBrick shutdown and PID-file removal.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | not supported |
| Human Web interface distribution | same artifact as the skill source |
| Service integration | none |
| Version source of truth | `TextStatsWeb::VERSION` in `src/text_stats.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `TEXT_STATS_WEB_ENABLED` | YES for startup | Must equal `1` to enable the browser interface. | NO |
| `TEXT_STATS_WEB_BIND` | NO | Defaults to and must remain `127.0.0.1`. | NO |
| `TEXT_STATS_WEB_PORT` | NO | Defaults to `4567`; accepts `0` only for local dynamic-port testing. | NO |
| `TEXT_STATS_WEB_PID_FILE` | NO | Overrides the default `tmp/text-stats-web.pid` lifecycle file. | NO |

## Decision rationale

Ruby matches the existing executable fixture ecosystem, and the maintained WEBrick gem provides a bounded HTTP listener without adding a framework or a second runtime. A same-process loopback listener is the smallest topology that can exercise browser routing, same-origin request policy, readiness, redaction, and process lifecycle. The interface uses a non-MCP application API because no MCP behavior is needed to establish the browser-interface contract. Explicit startup enablement and loopback-only binding keep this verification fixture out of production and remote-service scope.
