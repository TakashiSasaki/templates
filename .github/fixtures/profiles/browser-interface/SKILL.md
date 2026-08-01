---
name: text-stat-web
description: Verify deterministic text statistics through an explicitly enabled, loopback-only browser interface.
---

# Text statistics Web verification skill

## Purpose

Provide a small browser page that computes deterministic byte, line, and word counts without retaining or echoing the submitted text.

## Use this skill when

Use this skill when a local human operator needs to verify the text-statistics behavior through a browser and an explicitly enabled loopback Web interface is acceptable.

## Workflow

1. From the skill root, install dependencies with `bundle install`.
2. Start the interface with `TEXT_STATS_WEB_ENABLED=1 bundle exec ruby web/server.rb`.
3. Open `http://127.0.0.1:4567/` from the same host.
4. Submit text through the page and inspect the normalized byte, line, and word counts.
5. Check readiness with `bundle exec ruby web/server.rb --health` when operational verification is needed.
6. Stop the process with `bundle exec ruby web/server.rb --stop`.

## Public Web interface

Default URL: http://127.0.0.1:4567/
Browser contract: WEB_INTERFACE.md
Runtime and deployment authority: RUNTIME.md

The page uses the same-process non-MCP application API at `/api/text-stats`. `/healthz` reports only Web-interface readiness and does not prove that an MCP interface exists or is healthy.

## Output requirements

Display only the computed `bytes`, `lines`, and `words` integers. The API response includes `contractVersion`, `ok`, and `result`; it never includes the submitted text.

## Validation

Run `bundle exec ruby tests/test_web_server.rb` and the repository validator. Confirm disabled-by-default behavior, loopback-only binding, same-origin request enforcement, deterministic API results, redaction, health isolation, startup, readiness, and bounded shutdown.

## Safety and approval

The interface is read-only, binds only to `127.0.0.1`, rejects unapproved Host and Origin values, logs no request body, and is disabled unless `TEXT_STATS_WEB_ENABLED=1` is set. It is not a production service and must not be exposed through a non-loopback listener or external reverse proxy.

Selected profiles: browser-interface
