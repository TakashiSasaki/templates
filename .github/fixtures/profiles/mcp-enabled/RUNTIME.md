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
| Lockfile policy | The fixture pins the direct `mcp` dependency to 1.0.0 in `Gemfile`; the isolated fixture harness resolves transitive dependencies during validation and does not commit the generated lockfile. |
| Source layout | `src/text_stats.rb` contains deterministic operation logic and `mcp/server.rb` contains the stdio MCP adapter. |
| Supported operating systems | Linux with CRuby 3.1 or newer |

## Commands

Run every command from the skill root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` |
| Run in place | `bundle exec ruby mcp/server.rb` |
| Agent launcher | `bundle exec ruby mcp/server.rb` |
| Test | `bundle exec ruby tests/test_mcp_server.rb` |
| Lint/static analysis | `ruby -c src/text_stats.rb && ruby -c mcp/server.rb && ruby -c tests/test_mcp_server.rb` |
| Format check | `ruby -c src/text_stats.rb && ruby -c mcp/server.rb && ruby -c tests/test_mcp_server.rb` |
| Build/package | NOT APPLICABLE |

### MCP commands

| Purpose | Exact command |
|---|---|
| Start stdio MCP server | `bundle exec ruby mcp/server.rb` |
| Inspect MCP server and tool inventory | `bundle exec ruby tests/test_mcp_server.rb --name test_initialization_and_tool_inventory` |
| Invoke one MCP tool over stdio | `bundle exec ruby tests/test_mcp_server.rb --name test_successful_tool_call` |
| Invoke sequential MCP tool calls over stdio | `bundle exec ruby tests/test_mcp_server.rb --name test_sequential_tool_calls` |
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
| Legacy compatibility policy | No legacy protocol behavior is exposed; a client that cannot accept the server-selected revision must end the session before discovery or calls. |
| JSON Schema dialects | JSON Schema Draft 2020-12 through the SDK input and output schema validators |
| Optional MCP extensions | NONE |
| Deprecated feature policy | Deprecated features and capabilities outside this contract are not advertised. |
| Negotiation and compatibility tests | Tests verify exact-revision initialization, successful server selection after another string revision, malformed-revision rejection, tools-only capability advertisement, and continued operation after protocol and tool-validation errors. |

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
| Cancellation behavior | The only operation is bounded and synchronous; a caller timeout closes stdin, waits for graceful exit, sends TERM if the child remains alive, then sends KILL and reaps the process if TERM is ignored. |
| Child-process shutdown and escalation | Close stdin, wait up to two seconds, send TERM, wait one additional second, then send KILL and reap the process. Tests use controlled child processes to cover both TERM and KILL escalation after EOF. |

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
| CLI distribution | NOT APPLICABLE |
| MCP distribution | Bundled with the skill source and activated by registering the documented stdio command |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | NONE |
| Version source of truth | `TextStatsMcp::VERSION` in `src/text_stats.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| NONE | NO | The fixture has no environment-controlled behavior. | NO |

## Decision rationale

Ruby matches the existing executable fixture ecosystem and the official `mcp` 1.0.0 SDK provides initialization, JSON-RPC framing, schema validation, and stdio lifecycle support without a custom protocol implementation. A single read-only tool and stdio-only transport are the smallest sufficient `mcp-enabled` profile. Streamable HTTP, resources, prompts, tasks, sampling, elicitation, roots, and a public bundled client are omitted because this fixture does not need them and would require additional contracts and tests.
