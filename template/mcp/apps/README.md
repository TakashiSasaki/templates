# MCP Apps implementation area

Retain this directory only when a concrete `mcp-enabled` Skill selects `io.modelcontextprotocol/ui` and bundles App View implementation sources or generated resources here.

`MCP_APPS.md` owns caller-, Host-, and View-visible extension behavior. `RUNTIME.md` owns build commands, source layout, generated assets, package dependencies, and distribution. `mcp/apps/` is an implementation location, not the source of truth for protocol resource URIs.

Use stable `ui://` resource identifiers in the public contract and map them explicitly to bundled or generated content. Do not derive public resource identifiers from filenames.

Keep App code sandbox-compatible and minimize CSP origins, browser permissions, network access, and Host bridge authority. A bundled App does not require a standalone `browser-interface` unless the Skill separately exposes an ordinary browser-facing page.
