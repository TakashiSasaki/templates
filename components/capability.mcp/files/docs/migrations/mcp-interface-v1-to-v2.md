# MCP interface v1 to v2

Schema v2 adds `planning` mode so MCP transport and operation identities, kinds, and transport bindings are authoritative before implementation begins.

For a plan, set `schemaVersion` to `2`, set `mode` to `planning`, declare the supported `protocolRevision`, list planned transports with `id`, `kind`, and `purpose`, and list planned operations with `id`, `kind`, `transportId`, and `purpose`. Every operation must reference a declared planned transport. Do not invent protocol probes, exported names, or success/negative execution details at this stage.

The implementation-evidence planning ledger must target every planned transport and operation ID and declare integration or end-to-end proof strength. When implementation is ready, change to `mode: product` and enrich the same IDs with the existing complete product fields.

Template documents move to `schemaVersion: 2` and keep both item arrays empty.
