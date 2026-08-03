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
| Source layout | `src/text_stats.rb` contains the deterministic operation; `mcp/server_factory.rb` owns the tool and MCP server definition; `mcp/http_server.rb` owns the authenticated Streamable HTTP adapter and systemd notification; `deployment/systemd/` owns the fixed unit template and safe renderer; `tests/` owns protocol, renderer, and real systemd lifecycle evidence. |
| Supported operating systems | Linux with CRuby 3.1 or newer and systemd 249 or newer with `Type=notify`, `LoadCredential=`, control-group kill, and service hardening directives used by the unit. |

## Commands

Run repository-local commands from the skill root. System unit changes require explicit operator privileges.

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
| Inspect MCP server and tool inventory | `bundle exec ruby tests/test_http_server.rb --name test_file_backed_http_contract` |
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
| Render systemd unit | `bundle exec ruby deployment/systemd/render_unit.rb --service-user text-stats-mcp --service-group text-stats-mcp --skill-root /opt/text-stats-mcp --token-file /etc/text-stats-mcp/token --runtime-bin-dir /usr/bin --bundle-path /usr/bin/bundle --port 4572 --output /tmp/text-stats-mcp.service` |
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
| Default revision or negotiation mode | Server-selected revision `2025-11-25`; another string revision receives `2025-11-25` in the initialization result and the caller decides whether to continue. Missing or non-string revisions are rejected by SDK validation. |
| MCP SDK or protocol library | Official Ruby MCP SDK gem `mcp` |
| SDK version | `1.0.0` |
| Legacy compatibility policy | No legacy revision or cross-transport fallback is exposed. |
| JSON Schema dialects | JSON Schema Draft 2020-12 through the SDK validators |
| Optional MCP extensions | NONE |
| Deprecated feature policy | Deprecated capabilities outside this contract are not advertised. |
| Negotiation and compatibility tests | Tests initialize the real HTTP endpoint, verify the selected revision and inventory, send `notifications/initialized`, invoke sequential real tool calls, and compare deterministic structured results. |

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
| Port | Fixed deployment default `4572`; the renderer accepts one integer from 1 through 65535 for an explicit unit |
| Supported protocol eras | initialization-era revision `2025-11-25` only |
| Revision-specific state model | Stateful SDK-issued sessions with a 300-second idle timeout and explicit DELETE cleanup; no persistence or resumability |
| Concurrent-client policy | At most 16 live sessions; excess initialization receives HTTP 503 |
| Authentication | Every `/mcp` request requires an exact Bearer token. Direct test launch accepts only an explicit service-user-owned regular non-symlink file with no group or other access. Under systemd, the application opens only `CREDENTIALS_DIRECTORY/text-stats-mcp-token` and relies on the manager-provided read-only credential directory as the access-control authority instead of reinterpreting copied-file owner or mode metadata. Both sources together are rejected. |
| Host-header validation | Every request requires the exact configured loopback authority; nondefault ports require `127.0.0.1:PORT` |
| Origin validation granularity | EVERY HTTP REQUEST before health, authentication, session lookup, or dispatch |
| Allowed origins and absent-Origin policy | Absent Origin is accepted for non-browser clients; a present Origin must be same-scheme loopback HTTP with the configured effective port and no userinfo, path, query, or fragment |
| Connection-reuse security tests | Focused tests verify that invalid Origin and missing Bearer values are rejected independently of prior successful requests on one reused HTTP/1.1 connection |
| Readiness check | `GET /readyz` returns only `{"status":"ready"}` after listener creation. The server sends `READY=1` to `NOTIFY_SOCKET` from the listener callback, so `Type=notify` does not become active before readiness. |
| Liveness check | `GET /livez` returns only `{"status":"live"}` while the event loop responds |
| Cancellation behavior | The operation is synchronous and bounded; client disconnect does not create a detached task or persistence |
| Shutdown/restart policy | systemd owns the main process and control group. TERM is the graceful signal, `TimeoutStopSec=10s` bounds shutdown, `FinalKillSignal=SIGKILL` handles resistance, explicit restart performs stop then start, and `Restart=on-failure` restarts only unexpected failures subject to start limits; configuration failures exit 78 and `RestartPreventExitStatus=78` prevents futile restart loops. |
| Non-loopback support | NO; reverse-proxy trust and remote clients are not supported |

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
| Service runtime or entry point | systemd system unit rendered from `deployment/systemd/text-stats-mcp.service.in`, starting the fixed `mcp/http_server.rb` adapter |
| Protocol or API surface | HTTP/1.1 Streamable HTTP MCP at `POST` and `DELETE /mcp`; minimal `GET /readyz` and `GET /livez` |
| Endpoint or listener model | One systemd-owned main process and one loopback listener |
| Default bind address | `127.0.0.1` |
| Port policy | Fixed deployment default `4572`; one render-time integer from 1 through 65535 |
| Authentication | The renderer accepts a regular non-symlink source token owned by root or the unprivileged service user, with no group or other access. systemd `LoadCredential=` copies the value into its per-unit read-only credential directory, which is accessible only to the service identity and root. The application opens the fixed credential name nonblocking without following symlinks, bounds and validates the token value, and checks it on every MCP request. |
| Authorization | The authenticated caller may invoke only the read-only `text_stats` tool; no lifecycle, file, shell, administrative, or mutating operation exists |
| Exposure and non-loopback policy | Loopback-only; the renderer fixes `TEXT_STATS_MCP_HTTP_BIND=127.0.0.1`, and the application independently rejects every other bind before listener creation |
| Request size and rate limits | Request bodies are bounded at 65,536 bytes by the SDK transport; no remote rate limiter is claimed because remote exposure is unsupported |
| Concurrent request policy | At most 16 live MCP sessions; health remains separately reachable |
| State or session model | Process-local MCP sessions only; no persistent application state |
| Readiness check | systemd `Type=notify` plus `READY=1` after listener creation and `GET /readyz` over loopback |
| Liveness check | `systemctl is-active` plus `GET /livez`; no watchdog extension is claimed |
| Timeout and cancellation policy | systemd bounds startup at 15 seconds and stop at 10 seconds; the MCP operation is synchronous and bounded |
| Graceful shutdown and restart policy | systemd sends TERM to the main process, owns the control group, escalates with KILL after the stop timeout, performs explicit restart without overlap, restarts unexpected failures with one-second delay under a three-start-per-30-second limit, waits for notify readiness after restart, and does not restart application configuration exit 78 |
| Deployment topology | One rendered systemd system unit, one unprivileged service identity, one read-only skill artifact, one external credential source, and one loopback HTTP listener |
| Security and deployment smoke tests | Unit renderer tests reject unsafe identities, privileged service users, paths, symlinked or permissive tokens, invalid token ownership, invalid ports, and incomplete runtime selections. The real smoke verifies unit syntax, manager-owned copied credentials, notify readiness, authenticated MCP execution, explicit restart, KILL-triggered on-failure restart through active readiness, configuration-exit restart prevention, control-group stop, and token absence from the journal. |

The fixed unit applies `NoNewPrivileges`, empty capability sets, private temporary and device namespaces, read-only system and home views, kernel and cgroup protection, SUID/SGID restriction, locked personality, address-family restriction, mode-`0077` creation, journal output, and no shell-based `ExecStart`. The renderer creates one exact-mode-0644 output file under a canonical non-symlink parent only and refuses unresolved placeholders, unsafe substitution characters, existing output paths, and symlinked output parents.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive installed at a fixed service-readable path |
| CLI distribution | NOT SUPPORTED |
| MCP distribution | Streamable HTTP endpoint bundled with the skill source and activated only through the rendered systemd unit |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | systemd system unit rendered from the committed fixed template; no unit is installed automatically |
| Version source of truth | `TextStatsMcpSystemd::VERSION` in `src/text_stats.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `CREDENTIALS_DIRECTORY` | YES under systemd, supplied by the service manager | Locate the fixed manager-protected `text-stats-mcp-token` credential copied by `LoadCredential=` | NO; directory path only |
| `NOTIFY_SOCKET` | YES under `Type=notify`, supplied by systemd | Send `READY=1` after listener creation and `STOPPING=1` before managed shutdown | NO |
| `TEXT_STATS_MCP_HTTP_TOKEN_FILE` | Direct test launch only | Use one explicit service-user-owned mode-0600 token file when systemd credentials are not active | YES: file contents |
| `TEXT_STATS_MCP_HTTP_BIND` | Set by the unit | Must remain `127.0.0.1` | NO |
| `TEXT_STATS_MCP_HTTP_PORT` | Set by the unit | Selected render-time loopback port | NO |

## Decision rationale

The systemd variant is the smallest topology after a bundled local controller because the OS service manager becomes the sole lifecycle owner while the application protocol, domain operation, authentication, and loopback network boundary remain unchanged. `Type=notify` prevents active-state publication before the listener is ready, `LoadCredential=` keeps the secret out of the unit and process arguments while systemd owns copied-credential access control, and the fixed unit bounds failure restart and control-group shutdown. Non-loopback exposure, trusted proxies, TLS, socket activation, containers, multiple workers, persistence, migration, backup, metrics, zero-downtime rollout, and orchestration remain separate unsupported boundaries.
