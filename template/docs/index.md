# Skill template documentation

## Core Skill model

* [Architecture](architecture.md) - Defines the overall structure and responsibility boundaries of a generated Skill repository.
* [Skill profiles](skill-profiles.md) - Defines supported capability profiles and their composition rules, including extension activation.
* [Profile contract map](profile-contract-map.md) - Maps profiles and selected MCP extensions to their required contract surfaces.
* [Runtime selection](runtime-selection.md) - Defines how runtime choices are recorded without making the template runtime-specific.
* [MCP transports](mcp-transports.md) - Defines core MCP transport choices and boundaries for Skills that expose MCP interfaces.
* [MCP Apps](mcp-apps.md) - Defines implementation guidance for the optional `io.modelcontextprotocol/ui` extension.

## Top-level contracts

* [SKILL.md](../SKILL.md) - Provides the primary Skill contract and usage entry point.
* [INTERFACES.md](../INTERFACES.md) - Routes responsibilities across supported interface contracts.
* [RUNTIME.md](../RUNTIME.md) - Records runtime requirements, the core MCP revision, and selected MCP extension identifiers.
* [CLI interface](../CLI_INTERFACE.md) - Defines the packaged command-line interface when present.
* [MCP interface](../MCP_INTERFACE.md) - Defines core MCP behavior when present.
* [MCP Apps interface](../MCP_APPS.md) - Defines Apps-extension behavior when `io.modelcontextprotocol/ui` is selected.
* [Web interface](../WEB_INTERFACE.md) - Defines the standalone human-facing browser interface when present.
