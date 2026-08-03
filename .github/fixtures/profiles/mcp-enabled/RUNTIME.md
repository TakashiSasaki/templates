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
| Source layout | `src/text_stats.rb` contains deterministic operation logic; `mcp/server_factory.rb` owns the shared tool and server definition; `mcp/server.rb` and `mcp/http_server.rb` are thin stdio and Streamable HTTP adapters; `mcp/service_manager.rb` is an optional serialized local lifecycle controller; `tests/` contains transport, boundary, lifecycle, client, and managed-deployment tests. |
| Supported operating systems | Linux with CRuby 3.1 or newer and `/proc` process identity plus advisory `flock` support for the managed lifecycle variant |

## Commands

Run every command from the skill root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` |
| Run in place | `bundle exec ruby mcp/server.rb` |
| Agent launcher | `bundle exec ruby mcp/server.rb` |
| Test | `bundle exec ruby tests/test_mcp_server.rb && bundle exec ruby tests/test_http_server.rb && bundle exec ruby tests/test_http_boundaries.rb && bundle exec ruby tests/test_http_lifecycle.rb && bundle exec ruby tests/test_mcp_client.rb && bundle exec ruby tests/test_service_manager.rb` |
| Lint/static analysis | `ruby -c src/text_stats.rb && ruby -c mcp/server_factory.rb && ruby -c mcp/server.rb && ruby -c mcp/http_server.rb && ruby -c mcp/client.rb && ruby -c mcp/service_manager.rb && ruby -c tests/test_mcp_server.rb && ruby -c tests/test_http_server.rb && ruby -c tests/test_http_boundaries.rb && ruby -c tests/test_http_lifecycle.rb && ruby -c tests/test_mcp_client.rb && ruby -c tests/test_service_manager.rb` |
| Format check | `ruby -c src/text_stats.rb && ruby -c mcp/server_factory.rb && ruby -c mcp/server.rb && ruby -c mcp/http_server.rb && ruby -c mcp/client.rb && ruby -c mcp/service_manager.rb && ruby -c tests/test_mcp_server.rb && ruby -c tests/test_http_server.rb && ruby -c tests/test_http_boundaries.rb && ruby -c tests/test_http_lifecycle.rb && ruby -c tests/test_mcp_client.rb && ruby -c tests/test_service_manager.rb` |
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
| Start managed Streamable HTTP MCP service | `TEXT_STATS_MCP_HTTP_TOKEN_FILE=/path/to/mode-0600-token bundle exec ruby mcp/service_manager.rb start` |
| Stop managed Streamable HTTP MCP service | `bundle exec ruby mcp/service_manager.rb stop` |
| Restart managed Streamable HTTP MCP service | `bundle exec ruby mcp/service_manager.rb restart` |
| Check managed MCP readiness | `bundle exec ruby mcp/service_manager.rb ready` |
| Check managed MCP liveness | `bundle exec ruby mcp/service_manager.rb live` |
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
| Authentication | Exact Bearer token supplied by either `TEXT_STATS_MCP_HTTP_TOKEN` for an explicitly foreground-launched process or `TEXT_STATS_MCP_HTTP_TOKEN_FILE` for file-backed startup. Exactly one source is accepted. The file source is opened nonblocking without following symlinks and must be a regular service-user-owned file with no group or other permission bits. The token is checked with constant-time comparison on every `/mcp` request and is never emitted. |
| Host-header validation | Every request must carry the configured loopback authority in canonical form; nondefault ports require `127.0.0.1:PORT`, while port 80 accepts the equivalent `127.0.0.1` and `127.0.0.1:80` forms |
| Origin validation granularity | EVERY HTTP REQUEST before readiness, authentication, session lookup, or MCP dispatch; no connection-scoped allow decision |
| Allowed origins and absent-Origin policy | An absent Origin is accepted for non-browser clients; a present HTTP Origin must parse to host `127.0.0.1` and the configured effective port with no userinfo, path, query, or fragment; every other present Origin receives HTTP 403 |
| Connection-reuse security tests | One HTTP/1.1 keep-alive connection carries accepted and rejected Host, Origin, and Bearer values in sequence and proves that a valid earlier request does not authorize later requests; focused boundary tests cover equivalent default-port authority forms |
| Readiness check | Unauthenticated `GET /readyz` returns `{"status":"ready"}` for foreground mode. Managed mode adds its per-start `instanceNonce`; the controller accepts readiness only when that value matches the nonce in the locked PID record, preventing another listener on the configured port from satisfying startup. The endpoint still applies the same per-request canonical Host and Origin gate and remains independent of MCP request failures and session capacity. |
| Liveness check | Unauthenticated `GET /livez` returns `{"status":"live"}` for foreground mode and includes the same managed instance nonce when selected. The managed `live` command verifies PID, Linux process-start identity, and nonce before accepting the endpoint response. |
| Cancellation behavior | In the pinned SDK 1.0.0 JSON-response mode, closing the HTTP socket is not itself an MCP cancellation signal. The bounded synchronous operation may complete after the caller disconnects and is not detached into a task. The controlled regression records the outcome separately, asserts normal bounded completion for this SDK, then proves that the same session can answer `ping`, be deleted, and be replaced. Protocol-level MCP cancellation remains distinct and is not claimed by this disconnect test. |
| Shutdown/restart policy | Manual foreground mode records TERM or INT even before the server callback attaches, shuts down WEBrick once available, closes SDK sessions, releases the port, and can restart on the same port. Optional managed mode serializes every lifecycle command with an owner-only advisory lock, uses an identity- and nonce-verified mode-0600 PID record, applies bounded readiness, explicit start/stop/restart, TERM followed by KILL after fixed grace periods, and retains the PID record if bounded cleanup cannot prove the process exited. No automatic restart is claimed. |
| Non-loopback support | NO; non-loopback bind configuration is rejected and no reverse-proxy trust or remote-client mode is claimed |

### Managed local lifecycle variant

| Item | Selected value |
|---|---|
| Supported | YES, optional for the Streamable HTTP adapter |
| Controller | `mcp/service_manager.rb`; private operator command, not a packaged public CLI or MCP tool |
| Process topology | One detached local process group running the same `mcp/http_server.rb` adapter; all controller actions using one PID path are serialized by an owner-only `flock` lock file |
| Start policy | Acquire the lifecycle lock; validate the external token, runtime directories, and non-aliasing token/log/lock identities before process creation; reject an already-live identity; safely remove only a stale verified PID record; create a mode-0600 log; generate a per-start nonce; spawn the fixed Ruby entry point; atomically publish a mode-0600 PID/start-tick/nonce record; and require the spawned instance's matching nonce within eight seconds. Readiness from a pre-existing listener is rejected. |
| Stop policy | Under the same lifecycle lock, verify PID plus Linux `/proc` start ticks before signaling the process group; send TERM, wait two seconds, send KILL when still live, wait one additional second, and remove only the unchanged inode and record after exit is proved. Retain the record and fail when bounded escalation cannot prove exit. |
| Restart policy | Complete the serialized bounded stop successfully before a new start; no overlap, zero-downtime handoff, or automatic restart is claimed |
| Stale-process policy | A missing process, zombie, or start-tick mismatch is stale. The controller removes the unchanged safe record without signaling an unrelated process. A malformed, symlinked, wrong-owner, non-regular, oversized, overly permissive, replaced-inode, or unsafely located record is rejected rather than repaired or followed. |
| Secret boundary | Managed startup requires `TEXT_STATS_MCP_HTTP_TOKEN_FILE`; the token file must be distinct by path and inode from the PID, log, and lifecycle-lock files. The secret value is never placed in argv, PID metadata, stdout, stderr, or the managed log. A missing token is a configuration failure. Direct environment-token mode remains supported only for explicit foreground launch. |
| Runtime files | Default PID `tmp/text-stats-mcp-http.pid`, lifecycle lock `tmp/text-stats-mcp-http.pid.lock`, and log `tmp/text-stats-mcp-http.log`. Missing directories are created owner-only; existing final runtime directories must be service-user-owned, non-symlink directories not writable by group or other users. Lock and log files are exact mode `0600`; PID publication is no-replace and atomic. |
| Unsupported | OS service installation, privilege changes, multiple workers, socket activation, automatic restart, non-loopback exposure, TLS, reverse proxy, container, orchestrator, persistence, log rotation, and upgrade handoff |
| Smoke and negative tests | Real start/ready/live/restart/stop; foreground-listener port conflict with nonce ownership; lifecycle-command serialization; stale-record replacement; missing, insecure, and symlinked token rejection; token/log hardlink rejection without secret modification; PID symlink refusal; existing world-writable and symlinked runtime-directory rejection; failed-start record retention; secret redaction; and synchronized TERM-ignoring process-group escalation |

### Bundled ad hoc MCP tool client

| Item | Selected value |
|---|---|
| Supported | YES |
| Scope | tools only; bounded discovery and invocation helper, not a general MCP host |
| Stable public command | NOT SUPPORTED |
| Bundled helper command | `bundle exec ruby mcp/client.rb` |
| Supported transports | both |
| Negotiation and compatibility behavior | Fixed selected revision `2025-11-25`; initialize, verify the server-selected revision, validate known capability object shapes and boolean flags, send `notifications/initialized`, require its HTTP response status to be `202`, then continue; no cross-transport retry or revision fallback |
| Invocation scope | one tool call or multiple sequential `tools/call` requests, bounded to at most 32 sequential calls; `tools run` requires at least one `--call` before transport startup and rejects trailing operands; never JSON-RPC batch |
| Interaction modes | non-interactive JSON arguments only; terminal `--arguments-stdin` is rejected and non-EOF stdin reads are bounded by the configured `--timeout` before transport startup |
| Response-size policy | each successful JSON response body and stdio message is limited to 65,536 bytes; larger responses are rejected before JSON parsing |
| JSON response media-type policy | JSON HTTP responses for request messages must declare the `application/json` media type; optional parameters are allowed, while a missing or other media type is a protocol failure before JSON parsing |
| Server-information command | `server-info` |
| Tool-list command | `tools list` |
| Tool-show command | `tools show TOOL`; local filtering over lossless `tools/list` pages |
| Single tool-call command | `tools call TOOL --arguments JSON` |
| Sequential tool-run command | `tools run --call TOOL --arguments JSON ...`; empty `--call` sequences fail with usage exit 2 before transport startup |
| Pagination request policy | follow opaque `nextCursor` values until absent, with a default limit of 32 pages and a maximum configurable limit of 128 |
| Lossless tool-list page format | ordered `pages` records containing client-side `requestCursor` metadata and an untouched `mcpResult` object for every page; each tool's optional `outputSchema` must be an object when present, optional `annotations` must be an object with string `title` and boolean known hint fields when present, and optional `_meta` must be an object |
| Flattened inventory presentation | `tools show` derives one local view; it never replaces the lossless page sequence |
| Page-level cache-hint policy | preserve page-specific cache hints, `_meta`, and unknown fields without inventing aggregate cache metadata |
| Lossless call-result mode | every successful or `isError` tool result is retained under `mcpResult`, including unknown additive fields; completed ordered results are emitted when a later sequential call fails; result-level and content-block `_meta` values, when present, must be objects |
| Other presentation output modes | compact JSON only; no humanized loss that could discard protocol fields |
| Modern MRTR policy | NOT SUPPORTED |
| Initialization-era elicitation policy | no client capabilities are advertised; server-to-client requests are not handled |
| Non-interactive policy | no prompts, response files, or automatic retries; arguments are bounded JSON objects |
| Timeout and cancellation policy | default 5 seconds, maximum 30 seconds; stdin argument reads use the same bounded timeout before transport startup; stdio closes stdin then uses bounded TERM/KILL escalation and surfaces an unexpected natural nonzero child exit, while HTTP attempts session deletion, closes the connection, and surfaces cleanup failures as non-success outcomes; socket close is not claimed as MCP cancellation |
| Task or extension support | NOT SUPPORTED |
| Roots/workspace policy | NOT SUPPORTED; no filesystem workspace or MCP roots are exposed |
| Exit-code mapping | 0 success; 2 usage/configuration; 3 transport or readiness failure; 4 authentication; 5 timeout; 6 protocol/JSON-RPC; 7 tool result `isError`; 8 invalid result; 9 pagination; 10 request policy; 11 capacity |

The private helper is invoked from the fixture root with `bundle exec ruby mcp/client.rb`. Its stdio server command is fixed to `bundle exec ruby mcp/server.rb`. Its HTTP endpoint is supplied as `--endpoint` and must be loopback `/mcp`; its Bearer token is read only from `TEXT_STATS_MCP_HTTP_TOKEN`. The helper never exposes an arbitrary command, request ID, token argument, implicit HTTP-server startup, or unbounded retry.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | Bundled with the skill source; stdio is activated by host registration and Streamable HTTP is either an explicitly started foreground process or an explicitly managed local process |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | Optional bundled local lifecycle controller only; no systemd, launchd, Windows service, container, orchestrator, reverse proxy, automatic restart, or remote exposure |
| Version source of truth | `TextStatsMcp::VERSION` in `src/text_stats.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `TEXT_STATS_MCP_HTTP_TOKEN` | YES for direct foreground Streamable HTTP unless the file source is selected; unused by stdio and managed mode | Bearer token checked on every `/mcp` request | YES |
| `TEXT_STATS_MCP_HTTP_TOKEN_FILE` | YES for managed startup; alternative to the direct token for foreground startup | Path to a non-symlink regular token file owned by the service user with no group or other permission bits | YES: file contents |
| `TEXT_STATS_MCP_HTTP_BIND` | NO | Optional bind assertion; only `127.0.0.1` is accepted | NO |
| `TEXT_STATS_MCP_HTTP_PORT` | NO | Select a startup port from 1 through 65535; default 4570 | NO |
| `TEXT_STATS_MCP_HTTP_PID_FILE` | NO | Managed mode PID/start-tick/instance-nonce record; default `tmp/text-stats-mcp-http.pid`; also determines the adjacent `.lock` path | NO |
| `TEXT_STATS_MCP_HTTP_LOG_FILE` | NO | Managed mode stdout/stderr log; default `tmp/text-stats-mcp-http.log` | NO |

The manual foreground launcher records its PID in the shell variable `TEXT_STATS_MCP_HTTP_PID` when using the documented manual stop command; the server does not read that variable. Managed mode instead owns the secure PID record and adjacent advisory lock. `TEXT_STATS_MCP_MANAGED_INSTANCE_NONCE` is controller-owned internal state and is not a supported operator input. Test-only lifecycle hooks are gated by `TEXT_STATS_MCP_TEST_MODE=1` and are not supported runtime configuration.

## Decision rationale

Ruby matches the executable fixture ecosystem and the official `mcp` 1.0.0 SDK provides initialization, schemas, stdio, stateful Streamable HTTP, bounded request bodies, and session lifecycle without a custom MCP implementation. The two thin adapters share one server factory and one read-only operation. HTTP remains loopback-only, authenticated, request-scoped for canonical Host and Origin decisions, bounded to 16 sessions, and recoverable after session expiry. The optional lifecycle controller adds only serialized local start, stop, restart, instance-owned readiness/liveness, external-secret, stale-record, protected-runtime-path, and bounded-escalation behavior around the existing adapter. It does not enlarge the network trust boundary or claim an OS service manager, remote production deployment, reverse proxy, TLS, container, persistence, automatic restart, public client, tasks, sampling, elicitation, roots, or optional extensions.
