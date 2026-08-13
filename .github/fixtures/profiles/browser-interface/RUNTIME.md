# Runtime decision record

## Status

Selection status: SELECTED

## Primary implementation

| Item | Selected value |
|---|---|
| Language | Python |
| Runtime | CPython |
| Minimum runtime version | 3.12 |
| Dependency/package manager | NONE; the fixture uses only the Python standard library |
| Project manifest | NONE |
| Lockfile policy | NONE |
| Source layout | `src/text_stats.py` contains deterministic operation logic and `web/server.py` contains the Web adapter and lifecycle command. |
| Supported operating systems | Linux with CPython 3.12 or newer |

## Commands

Run every command from the skill root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | NONE; verify the existing runtime with `python --version` |
| Run in place | `TEXT_STATS_WEB_ENABLED=1 python web/server.py` |
| Agent launcher | NOT APPLICABLE |
| Test | `python tests/test_web_server.py` |
| Lint/static analysis | `python -m py_compile src/text_stats.py web/server.py tests/test_web_server.py` |
| Format check | `python -m py_compile src/text_stats.py web/server.py tests/test_web_server.py` |
| Build/package | NOT APPLICABLE |

### Browser-interface commands

| Purpose | Exact command |
|---|---|
| Start human verification Web UI | `TEXT_STATS_WEB_ENABLED=1 python web/server.py` |
| Stop human verification Web UI | `python web/server.py --stop` |
| Check human verification Web UI readiness | `python web/server.py --health` |

## Optional human verification Web interface deployment

| Item | Selected value |
|---|---|
| Supported | YES |
| Web runtime or entry point | `web/server.py` using Python standard-library HTTP facilities |
| Deployment selection time | startup |
| Supported topologies | same process and listener for the page, static assets, application API, and Web health endpoint |
| Default topology | one explicitly enabled loopback process bound to `127.0.0.1:4567` |
| Shared-listener support | YES |
| Separate-listener support | NO |
| External-origin model | same origin |
| Browser-visible MCP exposure capability | NOT SUPPORTED |
| Enablement configuration | Set `TEXT_STATS_WEB_ENABLED=1`; absence or any other value keeps the interface disabled. |

The port may be overridden for local testing, including port `0` for operating-system allocation. The bind address is fixed to `127.0.0.1`; non-loopback values are rejected before listener creation. The process writes a mode-0600 JSON PID record to `tmp/text-stats-web.pid` by default. The record includes the Linux process start identity; startup refuses an existing or symbolic-link record, and the documented stop command verifies that identity before sending TERM. TERM and INT stop the request loop, close the listener, and remove the owned record.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone or release archive |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | NOT SUPPORTED |
| Human Web interface distribution | same artifact as the skill source |
| Service integration | NONE |
| Version source of truth | `VERSION` in `src/text_stats.py` |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| `TEXT_STATS_WEB_ENABLED` | YES for startup | Must equal `1` to enable the browser interface. | NO |
| `TEXT_STATS_WEB_BIND` | NO | Defaults to and must remain `127.0.0.1`. | NO |
| `TEXT_STATS_WEB_PORT` | NO | Defaults to `4567`; accepts `0` only for local dynamic-port testing. | NO |
| `TEXT_STATS_WEB_PID_FILE` | NO | Overrides the default `tmp/text-stats-web.pid` lifecycle file. | NO |

## Decision rationale

CPython 3.12 provides the required HTTP, socket, JSON, signal, filesystem, and process-identity primitives without a framework or third-party runtime dependency. A same-process loopback listener is the smallest topology that can exercise browser routing, same-origin request policy, readiness, redaction, and process lifecycle. The interface uses a non-MCP application API because no MCP behavior is needed to establish the browser-interface contract. Explicit startup enablement and loopback-only binding keep this verification fixture out of production and remote-service scope.
