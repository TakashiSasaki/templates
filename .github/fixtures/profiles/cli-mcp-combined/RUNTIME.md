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
| Lockfile policy | Commit and update `Gemfile.lock` with CLI package or MCP SDK dependency changes |
| Source layout | `src/text_stat.rb` contains shared domain and CLI logic; `src/text_stats.rb` is the thin MCP domain wrapper; `bin/text-stat` and `mcp/server.rb` are the public entry points |
| Supported operating systems | Linux, macOS, and Windows with CRuby 3.1 or newer for the CLI; the stdio MCP fixture is validated on Linux with CRuby 3.1 or newer |

## Commands

Run every repository-local command from the skill root unless the installed CLI contract states otherwise.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` |
| Run in place | `bundle exec ruby mcp/server.rb` |
| Agent launcher | `bundle exec ruby mcp/server.rb` |
| Test | `bundle exec ruby tests/test_text_stat.rb && bundle exec ruby tests/test_mcp_server.rb && bundle exec ruby tests/test_interface_equivalence.rb` |
| Lint/static analysis | `ruby -c src/text_stat.rb && ruby -c src/text_stats.rb && ruby -c bin/text-stat && ruby -c mcp/server.rb && ruby -c tests/test_text_stat.rb && ruby -c tests/test_mcp_server.rb && ruby -c tests/test_interface_equivalence.rb` |
| Format check | `ruby -c src/text_stat.rb && ruby -c src/text_stats.rb && ruby -c bin/text-stat && ruby -c mcp/server.rb && ruby -c tests/test_text_stat.rb && ruby -c tests/test_mcp_server.rb && ruby -c tests/test_interface_equivalence.rb` |
| Build/package | `gem build text-stat.gemspec` |
| Install packaged command locally | `gem install --no-document --install-dir .local/gems --bindir .local/bin ./text-stat-1.0.0.gem` |

The local installation keeps the gem and executable inside the repository working tree. Activate those paths before invoking the installed CLI fallback.

| Shell | Exact command |
|---|---|
| POSIX shell | `export GEM_HOME="$PWD/.local/gems"; export GEM_PATH="$GEM_HOME"; export PATH="$PWD/.local/bin:$PATH"; text-stat --help` |
| PowerShell | `$env:GEM_HOME="$PWD/.local/gems"; $env:GEM_PATH=$env:GEM_HOME; $env:PATH="$PWD/.local/bin;$env:PATH"; text-stat --help` |

### Packaged CLI commands

| Purpose | Exact command |
|---|---|
| Human CLI | `text-stat` |

### MCP commands

| Purpose | Exact command |
|---|---|
| Start stdio MCP server | `bundle exec ruby mcp/server.rb` |
| Inspect MCP server and tool inventory | `bundle exec ruby tests/test_mcp_server.rb --name test_initialization_and_tool_inventory` |
| Invoke one MCP tool over stdio | `bundle exec ruby tests/test_interface_equivalence.rb` |
| Invoke sequential MCP tool calls over stdio | `bundle exec ruby tests/test_mcp_server.rb --name test_tool_error_keeps_session_usable_for_sequential_calls` |
| Start Streamable HTTP MCP server | NOT SUPPORTED |
| Stop Streamable HTTP MCP server | NOT SUPPORTED |
| Invoke one MCP tool over Streamable HTTP | NOT SUPPORTED |
| Invoke sequential MCP tool calls over Streamable HTTP | NOT SUPPORTED |
| Check MCP readiness | NOT SUPPORTED |

## MCP protocol support

| Item | Selected value |
|---|---|
| Supported protocol revisions | `2025-11-25` |
| Supported protocol eras | initialization-era |
| Default revision or negotiation mode | Server-selected revision `2025-11-25`; when a client supplies another string revision, initialization succeeds with `2025-11-25` in the response and the client decides whether to continue. Missing or non-string revision values are rejected by SDK parameter validation. |
| MCP SDK or protocol library | Official Ruby MCP SDK gem `mcp` |
| SDK version | `1.0.0` |
| Legacy compatibility policy | No legacy protocol behavior is exposed; a client that cannot accept the server-selected revision must end the session before discovery or calls and may use the separate CLI fallback only under `INTERFACES.md`. |
| JSON Schema dialects | JSON Schema Draft 2020-12 through the SDK input and output schema validators |
| Optional MCP extensions | NONE |
| Deprecated feature policy | Deprecated features and capabilities outside this contract are not advertised. |
| Negotiation and compatibility tests | Tests verify initialization, exact selected revision, tools-only capability advertisement, raw inventory, tool-validation errors, sequential calls, and actual CLI/MCP semantic equivalence through `tests/test_interface_equivalence.rb`. |

## MCP variants

### stdio variant

| Item | Selected value |
|---|---|
| Supported | YES |
| Server entry point | `mcp/server.rb` |
| Lifecycle owner | MCP host |
| Invocation scope | Multiple sequential operations in one initialized child-process session |
| Protocol negotiation/discovery | Send one well-formed `initialize` request; the response selects revision `2025-11-25`; send `notifications/initialized` and continue to `tools/list` only when the caller accepts that revision. |
| Request metadata behavior | The SDK parses and preserves standard request metadata; the fixture defines no custom request metadata. |
| Startup cost policy | Start one trusted child process only when the host activates the skill and reuse it for sequential calls. |
| Cancellation behavior | The operation is bounded and synchronous; a caller timeout closes stdin, waits for graceful exit, sends TERM if the child remains alive, then sends KILL and reaps the process if TERM is ignored. |
| Child-process shutdown and escalation | Close stdin, wait up to two seconds, send TERM, wait one additional second, then send KILL and reap the process. The dedicated MCP fixture retains controlled TERM/KILL escalation tests; this combined fixture verifies graceful EOF shutdown and shared-domain behavior. |

### Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | NO |
| Server entry point | NOT SUPPORTED |
| Endpoint path | NOT SUPPORTED |
| Default bind address | NOT SUPPORTED |
| Port | NOT SUPPORTED |
| Supported protocol eras | NOT SUPPORTED |
| Revision-specific state model | NOT SUPPORTED |
| Concurrent-client policy | NOT SUPPORTED |
| Authentication | NOT SUPPORTED |
| Host-header validation | NOT SUPPORTED |
| Origin validation granularity | NOT SUPPORTED |
| Allowed origins and absent-Origin policy | NOT SUPPORTED |
| Connection-reuse security tests | NOT SUPPORTED |
| Readiness check | NOT SUPPORTED |
| Cancellation behavior | NOT SUPPORTED |
| Shutdown/restart policy | NOT SUPPORTED |
| Non-loopback support | NOT SUPPORTED |

### Bundled ad hoc MCP tool client

| Item | Selected value |
|---|---|
| Supported | NO |
| Scope | NOT SUPPORTED |
| Stable public command | NOT SUPPORTED |
| Supported transports | NOT SUPPORTED |
| Negotiation and compatibility behavior | NOT SUPPORTED |
| Invocation scope | NOT SUPPORTED |
| Interaction modes | NOT SUPPORTED |
| Server-information command | NOT SUPPORTED |
| Tool-list command | NOT SUPPORTED |
| Tool-show command | NOT SUPPORTED |
| Single tool-call command | NOT SUPPORTED |
| Sequential tool-run command | NOT SUPPORTED |
| Pagination request policy | NOT SUPPORTED |
| Lossless tool-list page format | NOT SUPPORTED |
| Flattened inventory presentation | NOT SUPPORTED |
| Page-level cache-hint policy | NOT SUPPORTED |
| Lossless call-result mode | NOT SUPPORTED |
| Other presentation output modes | NOT SUPPORTED |
| Modern MRTR policy | NOT SUPPORTED |
| Initialization-era elicitation policy | NOT SUPPORTED |
| Non-interactive policy | NOT SUPPORTED |
| Timeout and cancellation policy | NOT SUPPORTED |
| Task or extension support | NOT SUPPORTED |
| Roots/workspace policy | NOT SUPPORTED |
| Exit-code mapping | NOT SUPPORTED |

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive |
| CLI distribution | Ruby gem `text-stat` with the `text-stat` executable |
| MCP distribution | Bundled with the skill source and activated by registering the documented stdio command |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | NONE |
| Version source of truth | `TextStat::VERSION` in `src/text_stat.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `GEM_HOME` | Only for the repository-local packaged installation | Locate the locally installed CLI gem | NO |
| `GEM_PATH` | Only for the repository-local packaged installation | Restrict gem lookup for the local CLI installation | NO |
| `PATH` | Only for the repository-local packaged installation | Make `.local/bin/text-stat` available as the installed fallback | NO |

No application-specific or MCP-specific environment configuration is required.

## Decision rationale

Ruby supplies the deterministic domain operation and packaged command, while the official `mcp` 1.0.0 SDK supplies protocol framing, schemas, and stdio lifecycle. One `TextStat.analyze` implementation is shared by the CLI and MCP adapters. MCP is preferred for registered agent hosts; the gem command is the network-free fallback. Streamable HTTP, a public MCP client, browser UI, and service deployment are intentionally omitted.
