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
| Lockfile policy | The fixture pins `mcp` 1.0.0, `rack` 3.2.1, `rackup` 2.2.1, and `webrick` 1.9.1 directly in `Gemfile`; the isolated fixture harness resolves transitive dependencies during validation and does not commit the generated lockfile. |
| Source layout | `src/text_stats.rb` contains deterministic operation logic; `mcp/server_factory.rb` owns the shared tool and server definition; `mcp/server.rb` and `mcp/http_server.rb` are thin stdio and Streamable HTTP adapters; `tests/` contains transport, boundary, and lifecycle tests. |
| Supported operating systems | Linux with CRuby 3.1 or newer |

## Commands

Run every command from the skill root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` |
| Run in place | `bundle exec ruby mcp/server.rb` |
| Agent launcher | `bundle exec ruby mcp/server.rb` |
| Test | `bundle exec ruby tests/test_mcp_server.rb && bundle exec ruby tests/test_http_server.rb && bundle exec ruby tests/test_http_boundaries.rb && bundle exec ruby tests/test_http_lifecycle.rb && bundle exec ruby tests/test_mcp_client.rb` |
| Lint/static analysis | `ruby -c src/text_stats.rb && ruby -c mcp/server_factory.rb && ruby -c mcp/server.rb && ruby -c mcp/http_server.rb && ruby -c mcp/client.rb && ruby -c tests/test_mcp_server.rb && ruby -c tests/test_http_server.rb && ruby -c tests/test_http_boundaries.rb && ruby -c tests/test_http_lifecycle.rb && ruby -c tests/test_mcp_client.rb` |
| Format check | `ruby -c src/text_stats.rb && ruby -c mcp/server_factory.rb && ruby -c mcp/server.rb && ruby -c mcp/http_server.rb && ruby -c mcp/client.rb && ruby -c tests/test_mcp_server.rb && ruby -c tests/test_http_server.rb && ruby -c tests/test_http_boundaries.rb && ruby -c tests/test_http_lifecycle.rb && ruby -c tests/test_mcp_client.rb` |
| Build/package | NOT APPLICABLE |

### MCP commands

| Purpose | Exact command |
|---|---|
| Start stdio MCP server | `bundle exec ruby mcp/server.rb` |
| Inspect MCP server and tool inventory | `bundle exec ruby tests/test_mcp_server.rb --name test_initialization_and_tool_inventory` |
| Invoke one MCP tool over stdio | `bundle exec ruby tests/test_mcp_server.rb --name test_successful_tool_call` |
| Invoke sequential MCP tool calls over stdio | `bundle exec ruby tests/test_mcp_server.rb --name test_sequential_tool_calls` |
| Start Streamable HTTP MCP server | `bundle exec ruby mcp/http_server.rb` |
| Stop Streamable HTTP MCP server | `kill -TERM "$TEXT_STATS_MCP_HTTP_PID"` |
| Invoke one MCP tool over Streamable HTTP | `bundle exec ruby tests/test_http_server.rb --name test_http_inventory_calls_and_stdio_equivalence` |
| Invoke sequential MCP tool calls over Streamable HTTP | `bundle exec ruby tests/test_http_server.rb --name test_request_scoped_host_origin_and_authentication_on_reused_connection` |
| Test HTTP expiry and disconnect recovery | `bundle exec ruby tests/test_http_lifecycle.rb` |
| Check MCP readiness | `curl --fail --silent --show-error http://127.0.0.1:4570/readyz` |

## MCP protocol support

| Item | Selected value |
|---|---|
| Supported protocol revisions | `2025-11-25` |
| Supported protocol eras | initialization-era |
| Default revision or negotiation mode | Server-selected revision `2025-11-25`; when a client supplies another string revision, initialization succeeds with `2025-11-25` in the response and the client decides whether to continue. Missing or non-string revision values are rejected by SDK parameter validation. |
| MCP SDK or protocol library | Official Ruby MCP SDK gem `mcp` |
| SDK version | `1.0.0` |
| Legacy compatibility policy | No legacy protocol behavior is exposed; a client that cannot accept the server-selected revision must end the session before discovery or calls. No cross-transport protocol fallback occurs inside an active session. |
| JSON Schema dialects | JSON Schema Draft 2020-12 through the SDK input and output schema validators |
| Optional MCP extensions | NONE |
| Deprecated feature policy | Deprecated features and capabilities outside this contract are not advertised. |
| Negotiation and compatibility tests | Tests verify exact-revision initialization, successful server selection after another string revision, malformed-revision rejection, tools-only capability advertisement, continued operation after protocol and tool-validation errors, equivalent stdio and HTTP tool results, canonical default-port authority handling, idle-expiry capacity recovery, explicit outcome recording for a client disconnect, post-disconnect session usability and cleanup, and preserved shutdown requests during startup. |

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
| Supported | YES |
| Server entry point | `mcp/http_server.rb` |
| Endpoint path | `/mcp` |
| Default bind address | `127.0.0.1`; any other configured bind is rejected before listener creation |
| Port | Fixed default `4570`, configurable at startup through `TEXT_STATS_MCP_HTTP_PORT` to an integer from 1 through 65535 |
| Supported protocol eras | initialization-era revision `2025-11-25` only |
| Revision-specific state model | Stateful SDK-issued UUID sessions with an operational 300-second idle timeout, explicit DELETE cleanup, and no resumability or hidden application state. The lifecycle suite uses a test-only shorter timeout to prove that expired sessions restore capacity without DELETE. |
| Concurrent-client policy | At most 16 live MCP sessions; the seventeenth initialization receives HTTP 503 until a session is deleted or expires; each tool operation is synchronous, read-only, and independent |
| Authentication | Exact Bearer token loaded from `TEXT_STATS_MCP_HTTP_TOKEN`; 32 to 128 non-whitespace printable ASCII characters; constant-time comparison on every `/mcp` request and no token output |
| Host-header validation | Every request must carry the configured loopback authority in canonical form; nondefault ports require `127.0.0.1:PORT`, while port 80 accepts the equivalent `127.0.0.1` and `127.0.0.1:80` forms |
| Origin validation granularity | EVERY HTTP REQUEST before readiness, authentication, session lookup, or MCP dispatch; no connection-scoped allow decision |
| Allowed origins and absent-Origin policy | An absent Origin is accepted for non-browser clients; a present HTTP Origin must parse to host `127.0.0.1` and the configured effective port with no userinfo, path, query, or fragment; every other present Origin receives HTTP 403 |
| Connection-reuse security tests | One HTTP/1.1 keep-alive connection carries accepted and rejected Host, Origin, and Bearer values in sequence and proves that a valid earlier request does not authorize later requests; focused boundary tests cover equivalent default-port authority forms |
| Readiness check | Unauthenticated `GET /readyz` returns JSON status only after the listener is serving; it still applies the same per-request canonical Host and Origin gate and remains independent of MCP request failures and session capacity |
| Cancellation behavior | In the pinned SDK 1.0.0 JSON-response mode, closing the HTTP socket is not itself an MCP cancellation signal. The bounded synchronous operation may complete after the caller disconnects and is not detached into a task. The controlled regression records the outcome separately, asserts normal bounded completion for this SDK, then proves that the same session can answer `ping`, be deleted, and be replaced. Protocol-level MCP cancellation remains distinct and is not claimed by this disconnect test. |
| Shutdown/restart policy | One foreground process records TERM or INT even before the server callback attaches, shuts down WEBrick once available, closes the SDK transport and sessions, emits diagnostics only to stderr, releases the port, and can restart on the same port; a live-port collision fails promptly |
| Non-loopback support | NO; non-loopback bind configuration is rejected and no reverse-proxy trust or remote-client mode is claimed |

### Bundled ad hoc MCP tool client

| Item | Selected value |
|---|---|
| Supported | YES |
| Scope | tools only; bounded discovery and invocation helper, not a general MCP host |
| Stable public command | NOT SUPPORTED |
| Bundled helper command | `bundle exec ruby mcp/client.rb` |
| Supported transports | both |
| Negotiation and compatibility behavior | Fixed selected revision `2025-11-25`; initialize, verify the server-selected revision, send `notifications/initialized`, then continue; no cross-transport retry or revision fallback |
| Invocation scope | one tool call or multiple sequential `tools/call` requests; never JSON-RPC batch |
| Interaction modes | non-interactive JSON arguments only |
| Server-information command | `server-info` |
| Tool-list command | `tools list` |
| Tool-show command | `tools show TOOL`; local filtering over lossless `tools/list` pages |
| Single tool-call command | `tools call TOOL --arguments JSON` |
| Sequential tool-run command | `tools run --call TOOL --arguments JSON ...` |
| Pagination request policy | follow opaque `nextCursor` values until absent, with a default limit of 32 pages and a maximum configurable limit of 128 |
| Lossless tool-list page format | ordered `pages` records containing client-side `requestCursor` metadata and an untouched `mcpResult` object for every page |
| Flattened inventory presentation | `tools show` derives one local view; it never replaces the lossless page sequence |
| Page-level cache-hint policy | preserve page-specific cache hints, `_meta`, and unknown fields without inventing aggregate cache metadata |
| Lossless call-result mode | every successful or `isError` tool result is retained under `mcpResult`, including unknown additive fields |
| Other presentation output modes | compact JSON only; no humanized loss that could discard protocol fields |
| Modern MRTR policy | NOT SUPPORTED |
| Initialization-era elicitation policy | no client capabilities are advertised; server-to-client requests are not handled |
| Non-interactive policy | no prompts, response files, or automatic retries; arguments are bounded JSON objects |
| Timeout and cancellation policy | default 5 seconds, maximum 30 seconds; stdio closes stdin then uses bounded TERM/KILL escalation, while HTTP attempts session deletion, closes the connection, and surfaces cleanup failures as non-success outcomes; socket close is not claimed as MCP cancellation |
| Task or extension support | NOT SUPPORTED |
| Roots/workspace policy | NOT SUPPORTED; no filesystem workspace or MCP roots are exposed |
| Exit-code mapping | 0 success; 2 usage/configuration; 3 transport; 4 authentication; 5 timeout; 6 protocol/JSON-RPC; 7 tool result `isError`; 8 invalid result; 9 pagination; 10 request policy; 11 capacity |

The private helper is invoked from the fixture root with `bundle exec ruby mcp/client.rb`. Its stdio server command is fixed to `bundle exec ruby mcp/server.rb`. Its HTTP endpoint is supplied as `--endpoint` and must be loopback `/mcp`; its Bearer token is read only from `TEXT_STATS_MCP_HTTP_TOKEN`. The helper never exposes an arbitrary command, request ID, token argument, implicit HTTP-server startup, or unbounded retry.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | Bundled with the skill source; stdio is activated by host registration and Streamable HTTP is an explicitly started local foreground process |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | Manual foreground local process only; no service manager, container, reverse proxy, automatic restart, or remote exposure |
| Version source of truth | `TextStatsMcp::VERSION` in `src/text_stats.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `TEXT_STATS_MCP_HTTP_TOKEN` | YES for Streamable HTTP; unused by stdio | Bearer token checked on every `/mcp` request | YES |
| `TEXT_STATS_MCP_HTTP_BIND` | NO | Optional bind assertion; only `127.0.0.1` is accepted | NO |
| `TEXT_STATS_MCP_HTTP_PORT` | NO | Select a startup port from 1 through 65535; default 4570 | NO |

The operator launching the HTTP process records its PID in the shell variable `TEXT_STATS_MCP_HTTP_PID` when using the documented stop command. The server does not write a PID file or read that shell variable. Test-only lifecycle hooks are gated by `TEXT_STATS_MCP_TEST_MODE=1` and are not supported runtime configuration.

## Decision rationale

Ruby matches the executable fixture ecosystem and the official `mcp` 1.0.0 SDK provides initialization, schemas, stdio, stateful Streamable HTTP, bounded request bodies, and session lifecycle without a custom MCP implementation. The two thin adapters share one server factory and one read-only operation. HTTP remains loopback-only, explicitly started, authenticated, request-scoped for canonical Host and Origin decisions, bounded to 16 sessions, recoverable after session expiry, and usable after bounded work completes following a client disconnect; stdio remains the no-listener fallback. A public bundled client, remote deployment, reverse proxy, TLS termination, service manager, persistence, tasks, sampling, elicitation, roots, and optional extensions remain unsupported and require separate contracts and fixtures.
