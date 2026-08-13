---
name: text-stat-service
description: Serve deterministic text statistics through a bounded, authenticated, loopback-only headless JSON service.
---

# Text statistics headless service skill

## Purpose

Provide deterministic byte, line, and word counts to local non-browser automation through an independently reachable JSON service.

## Use this skill when

Use this skill when a local process needs a stable authenticated HTTP endpoint for read-only text statistics and a loopback-only service boundary is appropriate.

## Workflow

1. Confirm CPython 3.12 or newer is available; the service has no third-party runtime dependency.
2. Create an external Bearer token file containing 32 to 128 visible ASCII characters and restrict it to the owning user, for example mode `0600`.
3. Start the service with `TEXT_STATS_SERVICE_TOKEN_FILE=/path/to/token python service/server.py`.
4. Check readiness with `python service/server.py --health` and liveness with `python service/server.py --live`.
5. Send authenticated JSON requests to `POST http://127.0.0.1:4568/v1/text-stats` with exactly one string field named `text`.
6. Stop the process with `python service/server.py --stop`.

The complete endpoint, security, request-limit, health, lifecycle, environment, and deployment authority is `RUNTIME.md`.

## Output requirements

A successful API response must contain integer `contractVersion`, Boolean `ok`, and a `result` object containing only integer `bytes`, `lines`, and `words` values. The response and diagnostics must not contain the submitted text or Bearer token.

## Validation

Run `python tests/test_service_server.py` and the repository validator. Confirm token-file protection, authentication and authorization, loopback and Host restrictions, rejection of browser Origin requests, deterministic results, bounded request bodies and concurrency, readiness/liveness separation, port-collision failure, restrictive-umask PID creation, atomic PID publication, and identity-verified shutdown.

## Safety and approval

The service is read-only and stateless. It binds only to `127.0.0.1`, rejects non-loopback configuration, accepts no browser-origin request, and requires a permission-checked external token for the application API. Do not commit the token, place it in a command-line argument, expose the listener through a reverse proxy, or treat this fixture as a production service.

Selected profiles: headless-service
