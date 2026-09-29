# Asynchronous publication

Policy validates its source and `docs/publication-catalog.json` locally. Integration
periodically snapshots the Policy branch, combines its exported documentation with
other providers and uploads a complete publication artifact. No Policy callback,
promotion receipt, downstream CI result or source pin update is required.

Site independently selects an available successful Integration publication, renders
its consumer and maintainer surfaces, and deploys the checked artifact to Pages.
An Integration failure leaves the previous publication available. A Site failure
leaves the current website deployed. Neither failure reverses a Policy change.

Change Policy documentation here, Integration semantics in Integration, and routes
or presentation in Site. Exact revisions and hashes are recorded in the built
artifacts for source attribution and integrity; they are not a coordinated release
transaction. See the [Integration design](https://github.com/TakashiSasaki/templates/blob/integration/docs/asynchronous-publication.md)
and [Site publishing guide](https://github.com/TakashiSasaki/templates/blob/site/PUBLISHING.md).
