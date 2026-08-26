# Web interface v1 to v2

Schema v2 adds `planning` mode so endpoint identities and browser/API classification exist before coding starts.

For a plan, set `schemaVersion` to `2`, set `mode` to `planning`, and declare every intended endpoint with `id`, `kind`, and non-empty `purpose`. Do not invent a method or path before they are decided. `kind` is required because it determines the pre-coding proof floor: `browser-page` requires browser-level proof, while `backend-api` and `health` require executable service-boundary proof.

The implementation-evidence planning ledger must target exactly the planned endpoint IDs. When implementation is ready to be described, change to `mode: product` and enrich each endpoint with its method and path while keeping its planned ID and caller-visible kind stable.

Template documents move to `schemaVersion: 2` and keep `endpoints: []`.
