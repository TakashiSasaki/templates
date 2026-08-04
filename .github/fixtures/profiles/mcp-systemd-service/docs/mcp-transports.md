# MCP transport implementation guidance

## Selected transport

This fixture selects only authenticated loopback Streamable HTTP at `/mcp`. The official Ruby MCP SDK owns JSON-RPC framing, initialization, sessions, schemas, and a defense-in-depth request-size check. Rack and WEBrick provide the HTTP adapter, while a custom WEBrick request class enforces the 65,536-byte limit during declared-length and chunked body reads before Rack or the SDK consumes the body.

## systemd lifecycle boundary

systemd is the sole deployed process owner. The committed unit is a template, not an installed unit. `deployment/systemd/render_unit.rb` substitutes only a validated non-root user and non-root group, canonical absolute paths, one port, and fixed runtime paths into a no-shell unit. It writes one new output file with exclusive creation and never invokes `systemctl`.

The renderer preserves account-lookup diagnostics, verifies that the selected Ruby can execute the supplied Bundler launcher, and rejects a skill tree, path component, runtime directory, interpreter, or Bundler executable that the service identity owns or can modify through group or other write access. Symlinks in the selected skill tree may resolve only inside that same immutable tree. These checks establish the read-only input boundary before the unit is emitted; they do not make a mutable installation safe after rendering.

Use `Type=notify` and send `READY=1` only after the listener is created. Do not treat process creation as readiness. Use `LoadCredential=` for the Bearer token and let the application read only the fixed credential name from `CREDENTIALS_DIRECTORY`; do not place the secret in `Environment=`, argv, the rendered unit, readiness payloads, or journal diagnostics. Validate the external source file before rendering, but treat systemd's per-unit read-only credential directory—not copied-file owner or mode bits—as the application-side access-control authority.

The unit owns TERM, stop timeout, final KILL, control-group cleanup, explicit restart, and bounded `Restart=on-failure`; pair permanent application configuration failures with a distinct exit status and `RestartPreventExitStatus=` so they do not consume the restart budget. Wait for the unit to return to active notify readiness after an automatic restart rather than treating a replacement PID as readiness. The application must not write or interpret a private PID record in this topology. A bundled lifecycle controller and systemd must never own the same process simultaneously.

## Request boundary

Keep the application bound to `127.0.0.1`. Validate Host and Origin on every request before authentication, session lookup, or MCP dispatch, including requests reused on one HTTP/1.1 connection. Reject an oversized declared body before reading it and stop a chunked or streaming body as soon as the cumulative read exceeds 65,536 bytes. Check the exact Bearer token on every `/mcp` request with constant-time comparison. Keep readiness and liveness minimal and unauthenticated only because the listener is loopback-only.

The process-local session cap is 16. Executable tests must fill the cap, require HTTP 503 for another initialization, delete one session through `DELETE /mcp`, and prove that a replacement session can then initialize.

## Hardening boundary

The unit removes capabilities, enables `NoNewPrivileges`, restricts address families, makes system and home views read-only, isolates temporary files and devices, protects kernel and cgroup settings, and uses mode `0077`. The systemd smoke checks the effective unit properties and relevant `/proc` process state after startup, rather than relying only on unit text or `systemd-analyze verify`. Treat any directive relaxation as a separate reviewed deployment change with executable evidence.

## Validation

Proportionate evidence includes renderer account, privilege, runtime, Bundler, immutability, injection, ownership, permission, and symlink rejection; declared-length and chunked body rejection at the server read boundary; session-cap exhaustion, DELETE cleanup, and recovery; `systemd-analyze verify`; real unit start with notify readiness; live hardening properties and process state; authenticated MCP initialization and tool invocation; explicit restart; KILL-triggered on-failure restart through active readiness; a TERM-resistant process and child forced out of the complete unit control group after the stop timeout; configuration-exit restart prevention; inactive state; and token absence from the journal. These tests establish only the local systemd topology.

Non-loopback exposure, reverse-proxy headers, TLS, socket activation, multiple workers, containers, persistence, metrics, backup, and orchestrated rollout remain unsupported and require separate contracts and fixtures.
