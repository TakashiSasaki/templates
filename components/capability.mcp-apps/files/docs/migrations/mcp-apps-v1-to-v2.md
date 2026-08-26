# MCP Apps v1 to v2

Schema v2 adds `planning` mode so the MCP Apps extension, View identities, and tool-to-View associations are authoritative before implementation begins.

For a plan, set `schemaVersion` to `2` and `mode` to `planning`. Declare the canonical extension identity, list planned Views with `id` and `purpose`, and list planned associations with `id`, `operationId`, `viewId`, and `purpose`. Each association must reference a planned View and a planned core MCP tool operation.

The implementation-evidence planning ledger must target the canonical `mcp-apps` extension, every planned View, and every planned association with the proof strength required by each item family. When implementation is ready, switch to `mode: product` and enrich the same identities with resource URI and executable success/negative details.

Template documents move to `schemaVersion: 2` and keep Views and associations empty.
