# Consuming Integrated Publication Bundle 5

Site reads a complete successful publication through `publication-channel.json`.
The channel names canonical workflows, branches and the artifact name. It contains
no producer revision, provider tuple or Bundle identity. Selection is resolved once
per build; a downloaded artifact can be reused offline indefinitely.

`scripts/fetch_publication.py` selects the newest available successful publication,
or a requested successful run. It checks the workflow, repository, branch, run,
archive digest and extraction boundaries before validating the Bundle. It neither
regenerates Integration output nor writes an adoption commit. Failed, in-progress
or expired newer runs leave earlier available successful publications selectable.

The [Integration contract](https://github.com/TakashiSasaki/templates/blob/integration/contracts/publication-bundle/README.md)
supplies document IDs, publication content, translations, optional glossary/source
navigation and exact source provenance. Provider names are data. This branch owns
its reader in `publication_bundle/` and `site_renderer/`; it does not import or pin
the producer implementation.

`surfaces.json` assigns Site-owned routes and consumer/maintainer navigation. Every
provider catalog document appears automatically; an unfamiliar provider gets a
normal documentation section. Site-local documents come from its local catalog.
`template:<provider>/<document-id>#fragment` links resolve after route assignment.
Changing presentation requires no upstream source or publication change.

`scripts/build_site.py` renders and checks the completed website from one Bundle
and one Site checkout. `build-provenance.json` records both identities. Deployment
receives that checked artifact in a separate Pages-write job. For uncommitted CSS
or content edits, use `scripts/preview_site.py` with the same downloaded Bundle.

The live channel accepts only Bundle 5. Old schema fixtures exercise retained
reader behavior; they are not supported publication channels or migration gates.
