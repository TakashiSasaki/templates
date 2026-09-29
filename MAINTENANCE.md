# Site maintenance

Read [AGENTS.md](AGENTS.md). Presentation and browser changes belong entirely to Site.
The source tests need no provider checkout, provider revision update or network request:

```sh
python -m unittest discover -s tests -v
node --test tests/*.test.mjs
```

Download one publication and keep it outside the checkout. While editing, preview the
current working tree without making a commit:

```sh
python scripts/fetch_publication.py --output /tmp/templates-publication
python scripts/preview_site.py --bundle /tmp/templates-publication --output /tmp/templates-preview
python -m http.server --directory /tmp/templates-preview/site
```

The preview copies tracked and non-ignored files to a disposable Git snapshot. It does
not alter source, refs or the downloaded publication. Choose a new output path for each
build. Run the relevant browser regression scripts against that artifact for changes to
navigation, search, accessibility, PWA or layout. Final deployment builds use committed
source with exact build provenance; preview SHAs are temporary and never pushed.

Provider content lives in the Bundle. Site-local documents, CSS, JavaScript and templates
live here. Update generated files through their local generator. The installed reference
Composition/Policy products are examples, not a mandatory external maintenance workflow.

PR preparation uses local skills. Review scope follows the affected behavior; a visual
change does not require an upstream provider review or a publication adoption PR.
