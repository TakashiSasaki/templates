# MCP transport implementation guidance

## Selected transport

This fixture selects only authenticated loopback Streamable HTTP at `/mcp`. The official Ruby MCP SDK owns JSON-RPC framing, initialization, sessions, schemas, and request-size enforcement. Rack and WEBrick provide the HTTP adapter.

## systemd lifecycle boundary

systemd is the sole deployed process owner. The committed unit is a template, not an installed unit. `deployment/systemd/render_unit.rb` substitutes only validated service identity, canonical absolute paths, one port, and fixed runtime paths into a no-shell unit. It writes one new output file with exclusive creation and never invokes `systemctl`.

Use `Type=notify` and send `READY=1` only after the listener callback. Do not treat process creation as readiness. Use `LoadCredential=` for the Bearer token and let the application read only the fixed credential name from `CREDENTIALS_DIRECTORY`; do not place the secret in `Environment=`, argv, the rendered unit, readiness payloads, or journal diagnostics. Validate the external source file before rendering, but treat systemd's per-unit read-only credential directory—not copied-file owner or mode bits—as the application-side access-control authority.

The unit owns TERM, stop timeout, final KILL, control-group cleanup, explicit restart, and bounded `Restart=on-failure`; pair permanent application configuration failures with a distinct exit status and `RestartPreventExitStatus=` so they do not consume the restart budget. Wait for the unit to return to active notify readiness after an automatic restart rather than treating a replacement PID as readiness. The application must not write or interpret a private PID record in this topology. A bundled lifecycle controller and systemd must never own the same process simultaneously.

## Request boundary

Keep the application bound to `127.0.0.1`. Validate Host and Origin on every request before authentication, session lookup, or MCP dispatch, including requests reused on one HTTP/1.1 connection. Check the exact Bearer token on every `/mcp` request with constant-time comparison. Keep readiness and liveness minimal and unauthenticated only because the listener is loopback-only.

## Hardening boundary

The unit removes capabilities, enables `NoNewPrivileges`, restricts address families, makes system and home views read-only, isolates temporary files and devices, protects kernel and cgroup settings, and uses mode `0077`. Treat any directive relaxation as a separate reviewed deployment change with executable evidence.

## Validation

Proportionate evidence includes renderer identity, runtime, injection, ownership, permission, and symlink rejection; `systemd-analyze verify`; real unit start with notify readiness; authenticated MCP initialization and tool invocation; explicit restart; KILL-triggered on-failure restart through active readiness; configuration-exit restart prevention; stop and inactive state; and token absence from the journal. These tests establish only the local systemd topology.

Non-loopback exposure, reverse-proxy headers, TLS, socket activation, multiple workers, containers, persistence, metrics, backup, and orchestrated rollout remain unsupported and require separate contracts and fixtures.
