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
| Source layout | `src/text_stats.rb` contains deterministic domain logic and the bounded lifecycle-probe client module; `service/server.rb` contains the authenticated HTTP adapter, listener, routing, and lifecycle command. |
| Supported operating systems | Linux with CRuby 3.1 or newer and `/proc` process identity support |

## Commands

Run every command from the skill root. Create the service token outside the repository as a regular file readable only by its owner.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `bundle install` |
| Run in place | `TEXT_STATS_SERVICE_TOKEN_FILE=/path/to/mode-0600-token bundle exec ruby service/server.rb` |
| Agent launcher | NOT APPLICABLE |
| Test | `bundle exec ruby tests/test_service_server.rb` |
| Lint/static analysis | `ruby -c src/text_stats.rb && ruby -c service/server.rb && ruby -c tests/test_service_server.rb` |
| Format check | `ruby -c src/text_stats.rb && ruby -c service/server.rb && ruby -c tests/test_service_server.rb` |
| Build/package | NOT APPLICABLE |

### Headless-service commands

| Purpose | Exact command |
|---|---|
| Start headless service | `TEXT_STATS_SERVICE_TOKEN_FILE=/path/to/mode-0600-token bundle exec ruby service/server.rb` |
| Stop headless service | `bundle exec ruby service/server.rb --stop` |
| Check headless service readiness | `bundle exec ruby service/server.rb --health` |
| Check headless service liveness | `bundle exec ruby service/server.rb --live` |

## Headless service deployment

| Item | Selected value |
|---|---|
| Supported | YES |
| Service runtime or entry point | `service/server.rb` using WEBrick 1.9.1 |
| Protocol or API surface | HTTP/1.1 JSON: `POST /v1/text-stats`; minimal `GET /readyz` and `GET /livez` health endpoints |
| Endpoint or listener model | One foreground process and one HTTP listener serving only the versioned API and health endpoints |
| Default bind address | `127.0.0.1` |
| Port policy | Fixed default `4568`; configurable from `0` through `65535`, with `0` reserved for local test allocation |
| Authentication | `POST /v1/text-stats` requires an exact Bearer token loaded through one nonblocking no-follow descriptor from a regular file owned by the service user with no group or other permission bits; health endpoints are unauthenticated and minimal |
| Authorization | The authenticated identity may invoke only the read-only `text_stats` operation; no administrative or mutating operation exists |
| Exposure and non-loopback policy | Loopback-only; any bind other than `127.0.0.1` is rejected before listener creation, and remote exposure or reverse proxying is unsupported |
| Request size and rate limits | API request bodies are incrementally limited to 65,536 bytes for Content-Length and chunked transfer; no application rate limiter is claimed because exposure is loopback-only, while concurrency remains explicitly bounded |
| Concurrent request policy | At most one API request is admitted at a time; excess or draining API requests receive HTTP 503, while readiness and liveness remain independently available; WEBrick allows at most eight client threads |
| State or session model | Stateless request processing with process-local readiness and admission counters only; no session, persistence, cookie, or request replay state |
| Readiness check | `GET /readyz` and `bundle exec ruby service/server.rb --health`; HTTP 200 while configuration is valid and the process is not draining, independent of temporary API-slot saturation; the command uses a raw incremental HTTP parser with a two-second overall deadline, a 4,096-byte complete-header cap applied before header materialization, and a 4,096-byte body cap before JSON parsing |
| Liveness check | `GET /livez` and `bundle exec ruby service/server.rb --live`; HTTP 200 while the process event loop is alive; the command uses the same total deadline and separate header/body caps as readiness |
| Timeout and cancellation policy | WEBrick applies a two-second request timeout and one-second keep-alive timeout; a stalled request body returns HTTP 408 with connection closure and releases the API admission slot; lifecycle probes close their socket on every success or failure path; the operation is synchronous and bounded, and client disconnect cancels response delivery without retaining work or state |
| Graceful shutdown and restart policy | TERM and INT handlers are installed before PID record publication; the record is opened through one nonblocking no-follow descriptor, must be a regular service-user-owned mode-0600 file no larger than 4,096 bytes, contains PID and Linux process start ticks, and is identity-verified by `--stop` before signaling; restart is an external operator action |
| Deployment topology | Separate foreground process from the same skill artifact, reached by local non-browser clients over loopback HTTP |
| Security and deployment smoke tests | Tests cover token-file descriptor validation including writerless FIFO rejection, Bearer authentication, Host and Origin rejection, request bounds and timeout recovery, concurrency, bounded health commands, health isolation, fixed-port collision, PID descriptor and identity validation including writerless FIFO rejection, graceful shutdown, and prompt missing-implementation failure; current-head CI additionally exercises the raw header-bounded lifecycle client through the existing readiness and adversarial streaming checks |

The service is intentionally not a browser surface. Any request containing an `Origin` header is rejected, no CORS permission is emitted, and `WEB_INTERFACE.md` is not retained. API responses are JSON with `Cache-Control: no-store`; request bodies and Bearer tokens are never logged or returned.

`POST /v1/text-stats` accepts exactly one JSON string field named `text`. Success returns `contractVersion: 1`, `ok: true`, and integer `bytes`, `lines`, and `words` fields under `result`. Authentication, media-type, encoding, JSON, schema, size, timeout, concurrency, route, and method failures remain distinct HTTP outcomes.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | not supported |
| Human Web interface distribution | not supported |
| Service integration | Direct foreground process; no system service manager or container integration is included |
| Version source of truth | `TextStatsService::VERSION` in `src/text_stats.rb` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `TEXT_STATS_SERVICE_TOKEN_FILE` | YES for startup | Path to the external 32-to-128-character visible-ASCII Bearer token file; it is opened without following symlinks and without blocking, and must be regular, owned by the service user, and inaccessible to group and other users. | YES: file contents |
| `TEXT_STATS_SERVICE_BIND` | NO | Defaults to and must remain `127.0.0.1`. | NO |
| `TEXT_STATS_SERVICE_PORT` | NO | Defaults to `4568`; accepts `0` only for local test allocation. | NO |
| `TEXT_STATS_SERVICE_PID_FILE` | NO | Overrides the default `tmp/text-stats-service.pid` lifecycle record; it is opened without following symlinks and without blocking and must satisfy the ownership, mode, type, size, and process-identity checks above. | NO |

## Decision rationale

Ruby and the pinned WEBrick gem match the existing executable fixture ecosystem and provide a real bounded HTTP listener without a framework or second runtime. A loopback-only, Bearer-authenticated JSON API is the smallest headless service that establishes endpoint, authentication, authorization, request-limit, concurrency, health, lifecycle, and shutdown contracts without creating a browser interface or production network deployment. The token is read from a permission-checked external file rather than committed configuration or a command-line argument. Remote exposure, TLS termination, reverse proxies, persistence, sessions, automatic restart, and service-manager packaging are omitted because each would add a separate deployment and security contract beyond this fixture.
