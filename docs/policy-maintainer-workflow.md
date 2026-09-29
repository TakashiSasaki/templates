# Maintaining the Policy provider

The repository's handwritten `AGENTS.md` is the maintenance entry point. The reusable
Policy compiler, profiles and skills are products for consumers; editing this provider
does not require self-adopting a new runtime or generating its operating instructions.

1. Edit the owning source under `src/`, `policy/`, `profiles/`, `skills/` or `docs/`.
2. Run focused local tests, then the relevant compiler, consumer and documentation checks.
3. Commit the source and generated product outputs together where applicable.
4. Submit the change against the Policy branch. Keep its ancestry independent from
   Composition, Modeling, Integration and Site.

To publish a document, add its identity and source path to `docs/publication-catalog.json`.
Run `python scripts/publication_catalog.py --source-root .`. Integration snapshots the
Policy branch asynchronously and includes the catalog. A Site change or adoption pin
is not part of a Policy document edit. Site determines audience navigation and URLs.

Executable releases still record the source and dependency versions they distribute.
Those product identities do not govern unrelated repository maintenance or publication.
