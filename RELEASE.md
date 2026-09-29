# Publication operations

Run `python scripts/publish.py --output /tmp/publication` from a committed Integration
checkout. Outputs must be outside the source checkout. `--source NAME=CHECKOUT` selects
a committed local candidate; sources are copied to disposable checkouts before generation.

The `Integration publication` workflow publishes on Integration pushes and reusable
workflow calls. The default-branch `Refresh publication` workflow invokes it every six
hours and supports manual dispatch. The only success product is `publication.tar` in the
`integrated-publication` Actions artifact. Partial failures upload nothing.

Site selects a successful artifact and owns rendering and deployment. It can continue
using an older successful artifact while Integration fails or advances. There is no
promotion lock, adoption PR, controller activation, receipt approval or provider callback.
See [the design](docs/asynchronous-publication.md) for retention, validation and recovery.
