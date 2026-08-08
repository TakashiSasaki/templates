# Skill template documentation

This directory contains documentation copied into repositories created from the Skill template. Maintainer-only publication, fixture, and distribution-boundary material remains outside `template/`.

This file is a navigation index following the `index.md` conventions in OKF v0.2 section 8. It does not declare this directory or generated repository to be a formal OKF bundle.

## Core Skill model

- [Architecture](architecture.md) — Defines the overall structure and responsibility boundaries of a generated Skill repository.
- [Skill profiles](skill-profiles.md) — Defines the supported capability profiles and their composition rules.
- [Profile contract map](profile-contract-map.md) — Maps profiles to their required contract surfaces.
- [Runtime selection](runtime-selection.md) — Defines how runtime choices are recorded without making the template runtime-specific.
- [MCP transports](mcp-transports.md) — Defines transport choices and boundaries for Skills that expose MCP interfaces.

## Top-level contracts

- [SKILL.md](../SKILL.md) — Primary Skill contract and usage entry point.
- [INTERFACES.md](../INTERFACES.md) — Routes responsibilities across the supported interface contracts.
- [RUNTIME.md](../RUNTIME.md) — Records runtime requirements and decisions.
- [CLI interface](../CLI_INTERFACE.md) — Defines the packaged command-line interface when present.
- [MCP interface](../MCP_INTERFACE.md) — Defines the MCP interface when present.
- [Web interface](../WEB_INTERFACE.md) — Defines the human-facing browser interface when present.
