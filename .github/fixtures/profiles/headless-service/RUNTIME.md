# Runtime decision record

## Status

Selection status: SELECTED

## Primary implementation

| Item | Selected value |
|---|---|
| Language | Python |
| Runtime | CPython |
| Minimum runtime version | 3.12 |
| Dependency/package manager | NONE; the service and tests use only the Python standard library |
| Project manifest | NONE |
| Lockfile policy | NONE |
| Source layout | `src/text_stats.py` contains deterministic domain logic plus bounded health, token-file, process-identity, and secure PID-record primitives; `service/server.py` contains the authenticated HTTP adapter, listener, routing, admission control, and lifecycle command. |
| Supported operating systems | Linux with CPython 3.12 or newer and `/proc` process identity support |

## Commands

Run every command from the skill root. Create the service token outside the repository as a regular file readable only by its owner.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | NONE; verify the existing runtime with `python --version` |
| Run in place | `TEXT_STATS_SERVICE_TOKEN_FILE=/path/to/mode-0600-token python service/server.py` |
| Agent launcher | NOT APPLICABLE |
| Test | `python tests/test_service_server.py` |
| Lint/static analysis | `python -m py_compile src/text_stats.py service/server.py tests/test_service_server.py` |
| Format check | `python -m py_compile src/text_stats.py service/server.py tests/test_service_server.py` |
| Build/package | NOT APPLICABLE |

### Headless-service commands

| Purpose | Exact command |
|---|---|
| Start headless service | `TEXT_STATS_SERVICE_TOKEN_FILE=/path/to/mode-0600-token python service/server.py` |
| Stop headless service | `python service/server.py --stop` |
| Check headless service readiness | `python service/server.py --health` |
| Check headless service liveness | `python service/server.py --live` |

## Headless service deployment

| Item | Selected value |
|---|---|
| Supported | YES |
| Service runtime or entry point | `service/server.py` using Python standard-library HTTP and socket facilities |
| Protocol or API surface | HTTP/1.1 JSON: `POST /v1/text-stats`; minimal `GET /readyz` and `GET /livez` health endpoints |
| Endpoint or listener model | One foreground process and one HTTP listener serving only the versioned API and health endpoints |
| Default bind address | `127.0.0.1` |
| Port policy | Fixed default `4568`; configurable from `0` through `65535`, with `0` reserved for local test allocation |
| Authentication | `POST /v1/text-stats` requires an exact Bearer token loaded through one nonblocking no-follow descriptor from a regular file owned by the service user with no group or other permission bits; health endpoints are unauthenticated and minimal |
| Authorization | The authenticated identity may invoke only the read-only `text_stats` operation; no administrative or mutating operation exists |
| Exposure and non-loopback policy | Loopback-only; any bind other than `127.0.0.1` is rejected before listener creation, and remote exposure or reverse proxying is unsupported |
| Request size and rate limits | API request bodies are incrementally limited to 65,536 bytes for Content-Length and chunked transfer; no application rate limiter is claimed because exposure is loopback-only, while concurrency remains explicitly bounded |
| Concurrent request policy | At most one API request is admitted at a time; excess or draining API requests receive HTTP 503, while readiness and liveness remain independently available; at most eight client request threads are admitted by the listener |
| State or session model | Stateless request processing with process-local readiness and admission counters only; no session, persistence, cookie, or request replay state |
| Readiness check | `GET /readyz` and `python service/server.py --health`; HTTP 200 while configuration is valid and the process is not draining, independent of temporary API-slot saturation; the command uses a raw incremental HTTP parser with a two-second overall deadline, a 4,096-byte complete-header cap applied before header materialization, and a 4,096-byte body cap before JSON parsing |
| Liveness check | `GET /livez` and `python service/server.py --live`; HTTP 200 while the process event loop is alive; the command uses the same total deadline and separate header/body caps as readiness |
| Timeout and cancellation policy | API body reads use a two-second request timeout and idle keep-alive uses a one-second timeout; a stalled admitted request returns HTTP 408 with connection closure and releases the API admission slot; lifecycle probes close their socket on every success or failure path; client disconnect cancels response delivery without retaining request state |
| Graceful shutdown and restart policy | TERM and INT handlers are installed before PID record publication. Each missing PID-parent path component is created separately and immediately forced to service-user-owned mode `0700`, so the documented default `tmp/text-stats-service.pid` remains usable even under process umask `0777`; existing parent-directory permissions remain operator-managed. The record is built in a same-directory exclusive no-follow staging file, forced to exact mode `0600` independently of umask, fully written, synchronized, and descriptor-verified. A no-replace hard link publishes the complete inode atomically at the configured PID pathname; incomplete writes and publication failures remove staging state, and post-link verification failure removes only the inode published by that call. Later reads use one nonblocking no-follow descriptor and require a regular service-user-owned mode-0600 file no larger than 4,096 bytes containing PID and Linux process start ticks; `--stop` identity-verifies the record before signaling, and restart is an external operator action. |
| Deployment topology | Separate foreground process from the same skill artifact, reached by local non-browser clients over loopback HTTP |
| Security and deployment smoke tests | Tests cover token-file descriptor validation including writerless FIFO rejection, Bearer authentication, Host and Origin rejection, request bounds and timeout recovery, concurrency, bounded health commands, health isolation, fixed-port collision, PID descriptor and identity validation including writerless FIFO rejection, graceful shutdown, restrictive-umask default-path creation, and atomic no-replace PID publication including injected partial-write cleanup. |

The service is intentionally not a browser surface. Any request containing an `Origin` header is rejected, no CORS permission is emitted, and `WEB_INTERFACE.md` is not retained. API responses are JSON with `Cache-Control: no-store`; request bodies and Bearer tokens are never logged or returned.

`POST /v1/text-stats` accepts exactly one JSON string field named `text`. Success returns `contractVersion: 1`, `ok: true`, and integer `bytes`, `lines`, and `words` fields under `result`. Authentication, media-type, encoding, JSON, schema, size, timeout, concurrency, route, and method failures remain distinct HTTP outcomes.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | NOT SUPPORTED |
| Human Web interface distribution | NOT SUPPORTED |
| Service integration | Direct foreground process; no system service manager or container integration is included |
| Version source of truth | `VERSION` in `src/text_stats.py` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `TEXT_STATS_SERVICE_TOKEN_FILE` | YES for startup | Path to the external 32-to-128-character visible-ASCII Bearer token file; it is opened without following symlinks and without blocking, and must be regular, owned by the service user, and inaccessible to group and other users. | YES: file contents |
| `TEXT_STATS_SERVICE_BIND` | NO | Defaults to and must remain `127.0.0.1`. | NO |
| `TEXT_STATS_SERVICE_PORT` | NO | Defaults to `4568`; accepts `0` only for local test allocation. | NO |
| `TEXT_STATS_SERVICE_PID_FILE` | NO | Overrides the default `tmp/text-stats-service.pid` lifecycle record. Missing parent components are created sequentially and forced to exact mode `0700` independently of umask. The configured pathname is published only after a complete same-directory staging record has been mode-forced, synchronized, and descriptor-verified; publication refuses replacement. Subsequent reads use nonblocking no-follow semantics with ownership, mode, type, size, and process-identity checks. | NO |

## Decision rationale

CPython 3.12 supplies the required bounded HTTP listener, socket deadlines, JSON processing, constant-time digest comparison, signal handling, descriptor-based filesystem checks, and atomic hard-link publication without a third-party framework. A loopback-only, Bearer-authenticated JSON API remains the smallest headless service that establishes endpoint, authentication, authorization, request-limit, concurrency, health, lifecycle, and shutdown contracts without creating a browser interface or production network deployment. The token is read from a permission-checked external file rather than committed configuration or a command-line argument. Remote exposure, TLS termination, reverse proxies, persistence, sessions, automatic restart, and service-manager packaging remain outside this fixture.
