# WebMCP optional capability

`capability.webmcp` is an independent optional capability for Website and Webapp recipes.

The selection state is authoritative consumer intent:

- neither include nor exclude: unspecified/default intent;
- include `capability.webmcp`: explicit adoption;
- exclude `capability.webmcp`: explicit non-adoption.

Website or Webapp selection never implies WebMCP. WebMCP selection never implies MCP, MCP Apps, runtime, service, or `capability.web-interface`.

The v1 capability contract is imperative WebMCP through `document.modelContext`. It deliberately does not add an upstream-spec revision parameter: immutable Composition revision, component version, contract schema history, and lifecycle evidence own evolution.

See `components/capability.webmcp/files/WEBMCP.md` for normative qualitative semantics, and the tool-design, security, and testing materials delivered by the component for implementation guidance.

## Examples

The examples under `examples/webmcp/` demonstrate normal supported intent states rather than different product kinds. Explicit exclusion is a durable consumer choice, not missing configuration.
