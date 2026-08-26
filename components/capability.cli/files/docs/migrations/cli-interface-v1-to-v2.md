# CLI interface v1 to v2

Schema v2 adds a pre-implementation `planning` mode so caller-visible CLI entrypoint identities exist in the capability contract before coding starts.

For a new plan, set `schemaVersion` to `2`, set `mode` to `planning`, and list every intended entrypoint as an object containing only `id` and non-empty `purpose`. The implementation-evidence planning ledger must target exactly those entrypoint IDs and must declare executable CLI proof strength.

When implementation is ready to be described, change the contract to `mode: product` and replace each planned entrypoint object with the existing complete product entrypoint shape. Keep the planned IDs stable. Product mode continues to require exact implementation-evidence coverage for every entrypoint.

Template documents also move to `schemaVersion: 2` and keep `entrypoints: []`.
