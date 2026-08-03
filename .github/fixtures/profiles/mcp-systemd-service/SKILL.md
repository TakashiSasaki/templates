---
name: text-stats-mcp-systemd
description: Operate a loopback-only authenticated Streamable HTTP MCP service under a rendered systemd system unit.
---

# Text statistics MCP systemd service skill

## Purpose

Provide deterministic byte, line, and word counts through one authenticated loopback Streamable HTTP MCP endpoint whose process lifecycle is owned by systemd.

## Use this skill when

Use this skill when a Linux operator needs the MCP endpoint to start as a system service, publish readiness through `sd_notify`, restart after unexpected process failure, stop as one control group, and keep credentials outside the skill artifact.

## Workflow

1. From the skill root, install the pinned dependencies with `bundle install`.
2. Create an external Bearer token containing 32 to 128 visible ASCII characters in a regular mode-`0600` file owned by the selected service user.
3. Render `deployment/systemd/text-stats-mcp.service.in` with `bundle exec ruby deployment/systemd/render_unit.rb`, supplying the fixed skill root, service identity, token source, Ruby runtime directory, Bundler executable, port, and a new output path.
4. Inspect the rendered unit with `systemd-analyze verify`, install it under `/etc/systemd/system/text-stats-mcp.service`, and run `sudo systemctl daemon-reload`.
5. Start the unit with `sudo systemctl start text-stats-mcp.service` and require both `systemctl is-active` and the configured readiness endpoint from `RUNTIME.md` to succeed before MCP initialization.
6. Invoke the configured Streamable HTTP MCP endpoint from `RUNTIME.md` with the exact Bearer token and the selected MCP revision.
7. Use `sudo systemctl restart text-stats-mcp.service` only for an explicit operator restart and `sudo systemctl stop text-stats-mcp.service` for shutdown.

## Public execution interfaces

Streamable HTTP endpoint: see RUNTIME.md
Preferred agent route: see INTERFACES.md
Detailed interface contract: MCP_INTERFACE.md

`RUNTIME.md` is authoritative for runtime, systemd ownership, credential loading, restart, shutdown, exposure, and unsupported topology decisions. `MCP_INTERFACE.md` is authoritative for caller-visible MCP behavior.

## Output requirements

The `text_stats` tool returns a complete MCP tool result whose `structuredContent` contains integer `bytes`, `lines`, and `words` values. No response, unit, journal message, command argument, or readiness payload may contain the submitted text or Bearer token.

## Validation

Run `bundle exec ruby tests/test_unit_renderer.rb`, `bundle exec ruby tests/test_http_server.rb`, and the repository profile validator. In an isolated Linux systemd environment, also run `bundle exec bash tests/systemd_smoke.sh` to verify unit syntax, notify readiness, authenticated MCP calls, explicit restart, automatic on-failure restart, configuration-exit restart prevention, control-group shutdown, and journal redaction.

## Safety and approval

The renderer writes only a new caller-selected output file and never installs or starts a unit. Installing, enabling, starting, restarting, or stopping the system unit requires explicit operator action with appropriate privileges. The service remains bound to `127.0.0.1`; do not add non-loopback exposure, reverse-proxy trust, TLS termination, socket activation, containers, persistence, or orchestration under this contract.

Selected profiles: mcp-enabled, headless-service
