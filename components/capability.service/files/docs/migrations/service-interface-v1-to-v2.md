# Service interface v1 to v2

Schema v2 adds `planning` mode so service operation identities and the caller-visible service protocol are authoritative before implementation begins.

For a plan, set `schemaVersion` to `2`, set `mode` to `planning`, declare the intended `protocol`, and list every planned operation using only `id` and non-empty `purpose`. The implementation-evidence planning ledger must target exactly those operation IDs and declare integration or end-to-end proof strength.

For implementation, change to `mode: product` and replace each planned operation with the complete invocation/success/negative product shape while keeping the planned IDs stable. Product evidence continues to require exact operation coverage.

Template documents move to `schemaVersion: 2`, omit `protocol`, and keep `operations: []`.
