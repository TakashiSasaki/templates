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
| Lockfile policy | The fixture pins `mcp` 1.0.0, `rack` 3.2.1, `rackup` 2.2.1, and `webrick` 1.9.1 directly; the isolated fixture harness resolves transitive dependencies and does not commit a generated lockfile. |
| Source layout | `src/text_stats.rb` contains the deterministic operation; `mcp/server_factory.rb` owns the MCP definition; `mcp/http_server.rb` owns authentication, bounded HTTP reads, transport, and systemd notification; `deployment/systemd/` owns the unit template and renderer; `tests/` owns renderer, protocol, hardening, and lifecycle evidence. |
| Supported operating systems | Linux with CRuby 3.1 or newer and systemd 249 or newer with the selected notify, credential, control-group, and hardening features. |

## Commands

Run repository-local commands from the skill root. Unit installation and lifecycle changes require explicit operator privileges.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` |
| Run in place | `TEXT_STATS_MCP_HTTP_TOKEN_FILE=/path/to/mode-0600-token bundle exec ruby mcp/http_server.rb` |
| Agent launcher | NOT APPLICABLE |
| Test | `bundle exec ruby tests/test_unit_renderer.rb && bundle exec ruby tests/test_http_server.rb` |
| Lint/static analysis | `ruby -c src/text_stats.rb && ruby -c mcp/server_factory.rb && ruby -c mcp/http_server.rb && ruby -c deployment/systemd/render_unit.rb && ruby -c tests/test_unit_renderer.rb && ruby -c tests/test_http_server.rb && ruby -c tests/systemd_smoke_client.rb && bash -n tests/systemd_smoke.sh` |
| Format check | `ruby -c src/text_stats.rb && ruby -c mcp/server_factory.rb && ruby -c mcp/http_server.rb && ruby -c deployment/systemd/render_unit.rb && ruby -c tests/test_unit_renderer.rb && ruby -c tests/test_http_server.rb && ruby -c tests/systemd_smoke_client.rb && bash -n tests/systemd_smoke.sh` |
| Build/package | NOT APPLICABLE |

### MCP commands

| Purpose | Exact command |
|---|---|
| Start stdio MCP server | NOT SUPPORTED |
| Inspect MCP server and tool inventory | `bundle exec ruby tests/test_http_server.rb --name test_file_backed_http_contract_and_reused_connection_policy` |
| Invoke one MCP tool over stdio | NOT SUPPORTED |
| Invoke sequential MCP tool calls over stdio | NOT SUPPORTED |
| Start Streamable HTTP MCP server | `sudo systemctl start text-stats-mcp.service` |
| Stop Streamable HTTP MCP server | `sudo systemctl stop text-stats-mcp.service` |
| Invoke one MCP tool over Streamable HTTP | `bundle exec ruby tests/systemd_smoke_client.rb` |
| Invoke sequential MCP tool calls over Streamable HTTP | `bundle exec ruby tests/systemd_smoke_client.rb` |
| Check MCP readiness | `curl --fail --silent --show-error http://127.0.0.1:4572/readyz` |

### Headless-service commands

| Purpose | Exact command |
|---|---|
| Render systemd unit | `bundle exec ruby deployment/systemd/render_unit.rb --service-user text-stats-mcp --service-group text-stats-mcp --skill-root /usr/local/lib/text-stats-mcp --token-file /etc/text-stats-mcp/token --runtime-bin-dir /usr/bin --bundle-path /usr/bin/bundle --port 4572 --output /tmp/text-stats-mcp.service` |
| Verify rendered systemd unit | `systemd-analyze verify /tmp/text-stats-mcp.service` |
| Start headless service | `sudo systemctl start text-stats-mcp.service` |
| Stop headless service | `sudo systemctl stop text-stats-mcp.service` |
| Restart headless service | `sudo systemctl restart text-stats-mcp.service` |
| Check headless service readiness | `curl --fail --silent --show-error http://127.0.0.1:4572/readyz` |
| Check headless service liveness | `curl --fail --silent --show-error http://127.0.0.1:4572/livez` |
| Run systemd deployment smoke | `bundle exec bash tests/systemd_smoke.sh` |

## MCP protocol support

| Item | Selected value |
|---|---|
| Supported protocol revisions | `2025-11-25` |
| Supported protocol eras | initialization-era |
| Default revision or negotiation mode | Server-selected revision `2025-11-25`; another string revision receives `2025-11-25`, while missing or non-string revisions are rejected. |
| MCP SDK or protocol library | Official Ruby MCP SDK gem `mcp` |
| SDK version | `1.0.0` |
| Legacy compatibility policy | No legacy revision or cross-transport fallback is exposed. |
| JSON Schema dialects | JSON Schema Draft 2020-12 through the SDK validators |
| Optional MCP extensions | NONE |
| Deprecated feature policy | Deprecated capabilities outside this contract are not advertised. |
| Negotiation and compatibility tests | Real HTTP tests cover selected, alternate-string, missing, and non-string revision outcomes plus inventory and sequential calls. |

## MCP variants

### stdio variant

| Item | Selected value |
|---|---|
| Supported | NO |
| Server entry point | NOT SUPPORTED |
| Lifecycle owner | NOT SUPPORTED |
| Invocation scope | NOT SUPPORTED |
| Protocol negotiation/discovery | NOT SUPPORTED |
| Request metadata behavior | NOT SUPPORTED |
| Startup cost policy | NOT SUPPORTED |
| Cancellation behavior | NOT SUPPORTED |
| Child-process shutdown and escalation | NOT SUPPORTED |

### Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | YES |
| Server entry point | `mcp/http_server.rb` |
| Endpoint path | `/mcp` |
| Default bind address | `127.0.0.1`; every other configured bind is rejected before listener creation |
| Port | Fixed deployment default `4572`; one explicit render-time integer from 1 through 65535 |
| Supported protocol eras | initialization-era revision `2025-11-25` only |
| Revision-specific state model | SDK-issued process-local sessions with 300-second idle expiry and explicit DELETE cleanup; no persistence or resumability |
| Concurrent-client policy | At most 16 live sessions; excess initialization receives HTTP 503, and DELETE releases capacity |
| Authentication | Every `/mcp` request requires the exact Bearer token. Direct launch requires a service-user-owned regular non-symlink file with no group or other access; systemd launch uses only its fixed manager-protected credential path. |
| Host-header validation | Every request requires the exact configured loopback authority |
| Origin validation granularity | EVERY HTTP REQUEST before health, authentication, session lookup, or dispatch |
| Allowed origins and absent-Origin policy | Absent Origin is accepted; a present Origin must be exact same-origin loopback HTTP with no userinfo, path, query, or fragment |
| Connection-reuse security tests | One reused HTTP/1.1 connection proves valid, invalid-Origin, missing-authentication, invalid-Host, and subsequent-valid decisions remain request scoped |
| Readiness check | `GET /readyz` returns only `{"status":"ready"}`; `READY=1` is sent only after listener creation |
| Liveness check | `GET /livez` returns only `{"status":"live"}` while the server responds |
| Cancellation behavior | The operation is synchronous and bounded; disconnect does not create detached or persistent work |
| Shutdown/restart policy | systemd owns the process and control group, sends TERM, waits 10 seconds, applies final SIGKILL, performs explicit restart, bounds failure restart, and does not restart configuration exit 78 |
| Non-loopback support | NO; reverse-proxy trust and remote clients are unsupported |

Declared `Content-Length` above 65,536 bytes is rejected before body reading. Chunked or streaming input is stopped as soon as cumulative reads exceed 65,536 bytes. The SDK retains the same limit as defense in depth. Direct tests require HTTP 413 for both forms and prove readiness remains available afterward.

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

## Headless service deployment

| Item | Selected value |
|---|---|
| Supported | YES |
| Service runtime or entry point | Rendered systemd system unit starting the fixed `mcp/http_server.rb` adapter |
| Protocol or API surface | HTTP/1.1 Streamable HTTP MCP at `POST` and `DELETE /mcp`; minimal `GET /readyz` and `GET /livez` |
| Endpoint or listener model | One systemd-owned main process and one loopback listener |
| Default bind address | `127.0.0.1` |
| Port policy | Fixed default `4572`; one render-time integer from 1 through 65535 |
| Authentication | A root- or service-user-owned mode-0600 source is copied by `LoadCredential=` into systemd's protected credential directory; the application opens only the fixed credential name, bounds and validates the value, and checks it on every MCP request |
| Authorization | The caller may invoke only the read-only `text_stats` tool; no lifecycle, file, shell, administrative, or mutating operation exists |
| Exposure and non-loopback policy | Loopback-only in both rendered environment and application validation |
| Request size and rate limits | WEBrick rejects declared and chunked bodies above 65,536 bytes at the server read boundary; the SDK repeats the bound; no remote rate limiter is claimed |
| Concurrent request policy | At most 16 live sessions; excess initialization is 503 and DELETE restores capacity |
| State or session model | Process-local MCP sessions only; no persistent application state |
| Readiness check | `Type=notify` plus `READY=1` after listener creation and loopback `GET /readyz` |
| Liveness check | `systemctl is-active` plus loopback `GET /livez`; no watchdog extension |
| Timeout and cancellation policy | Startup is bounded at 15 seconds and stop at 10 seconds; MCP work is synchronous and bounded |
| Graceful shutdown and restart policy | TERM is graceful, final KILL removes resistant processes and children from the control group, explicit restart has no overlap, unexpected failure restarts within start limits, and exit 78 is not restarted |
| Deployment topology | One rendered system unit, one non-root user, one non-root group, one immutable skill tree, one verified immutable Ruby/Bundler selection, one external credential source, and one loopback listener |
| Security and deployment smoke tests | Renderer tests cover account diagnostics, UID/GID privilege, actual Bundler identity, path replacement, ownership, write permissions, symlinks, tokens, ports, and runtime selection. Real smoke checks effective systemd properties and `/proc` state, authenticated MCP calls, restart paths, resistant control-group escalation, configuration failure, and journal redaction. |

The renderer requires an existing non-root user and non-root group, verifies membership, verifies the selected Ruby can execute the supplied Bundler launcher, and rejects any selected skill or runtime path that the service identity owns, can replace through an ancestor, or can modify through group or other write permissions. The fixed unit applies `NoNewPrivileges`, empty capability sets, private temporary and device namespaces, read-only system and home views, kernel and cgroup protection, SUID/SGID restriction, locked personality, restricted address families, mode `0077`, journal output, and no shell-based `ExecStart`.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive installed at a fixed immutable service-readable path |
| CLI distribution | NOT SUPPORTED |
| MCP distribution | Streamable HTTP endpoint bundled with the skill source and activated only through the rendered systemd unit |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | systemd unit rendered from the committed template; no unit is installed automatically |
| Version source of truth | `TextStatsMcpSystemd::VERSION` in `src/text_stats.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `CREDENTIALS_DIRECTORY` | YES under systemd, supplied by the service manager | Locate the fixed manager-protected credential | NO; directory path only |
| `NOTIFY_SOCKET` | YES under `Type=notify`, supplied by systemd | Publish ready and stopping state | NO |
| `TEXT_STATS_MCP_HTTP_TOKEN_FILE` | Direct test launch only | Select one service-user-owned mode-0600 token file outside systemd | YES: file contents |
| `TEXT_STATS_MCP_HTTP_BIND` | Set by the unit | Must remain `127.0.0.1` | NO |
| `TEXT_STATS_MCP_HTTP_PORT` | Set by the unit | Select the loopback port | NO |

## Decision rationale

This is the smallest topology in which the OS service manager is the sole lifecycle owner while the application protocol and loopback trust boundary remain fixed. The renderer certifies the service identity and immutable code/runtime inputs before emitting a unit. `Type=notify`, `LoadCredential=`, bounded server reads, session-cap recovery, effective hardening checks, and resistant control-group shutdown provide executable evidence for the selected local systemd boundary. Non-loopback exposure, proxy trust, TLS, socket activation, containers, multiple workers, persistence, migration, backup, metrics, zero-downtime rollout, and orchestration remain unsupported.
