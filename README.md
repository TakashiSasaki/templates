# Integration authority

Integration reads provider catalogs and publishes a self-contained semantic Bundle.
Site consumes successful Bundles independently. All authority histories remain unrelated.

Read [the design](docs/asynchronous-publication.md), [authority ownership](AUTHORITY.md)
and [AGENTS.md](AGENTS.md). Provider selection is a short branch map in
[publication-sources.json](publication-sources.json). Curated routes in
Site-owned presentation are optional; every catalog document is included automatically.

```sh
python -m pip install -r requirements-build.lock
python -m unittest discover -s tests -v
python scripts/publish.py --output /tmp/templates-publication
```

The output directory must not exist. A build resolves source branches once, materializes
private checkouts, validates the semantic models, checks deterministic regeneration and
records exact revisions and content hashes. To test committed local candidates, add
`--source composition=/path/to/checkout` (similarly for other configured providers).

Add another authority by adding its branch to `publication-sources.json` and providing
`docs/publication-catalog.json` there. A plain catalog needs no capability registry,
Site change, translated navigation, glossary or generated `index.md`. Source and asset
paths remain bounded to the provider checkout. Foreign Git ancestry is rejected.

The CI publication workflow uploads `integrated-publication` only after success.
It needs read permission and no Site checkout, secret, PR, promotion or deployment.
