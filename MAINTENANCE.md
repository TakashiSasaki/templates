# Documentation site maintenance

This file applies only to the unrelated `site` branch.

## Branch responsibilities

- `skill`, `policy`, and `webapp` own their canonical documentation and their own `docs/publication-catalog.json` files. They do not own or initiate GitHub Pages deployment.
- `site` is the repository default branch and owns the integrated portal home, cross-publication navigation, source locking, assembly, generated repository-tree inventories, generated-site validation, build provenance, and the only Pages deployment workflow.
- Generated Markdown and HTML are temporary build artifacts and must not be committed.

The four major branches have unrelated histories. Do not merge, rebase, or cherry-pick between them merely to publish documentation. The site build checks out each publication independently at the full commit recorded in `publication-sources.json`.

## Change process

1. Make canonical documentation and catalog changes on the provider branch that owns them.
2. Merge the provider pull request and record its actual merge commit SHA.
3. Branch the coordinated portal change from `site` and open a pull request whose base is `site`.
4. Update `publication-sources.json` to the reviewed provider merge commit using a lowercase full 40-character SHA.
5. Update `site-manifest.json` whenever a publication document is added or removed, or when reader-facing titles, hierarchy, ordering, or generated destinations change.
6. Require the integrated documentation build, repository-tree generation, and generated-link validation to succeed against the exact locked commits before merging the site pull request.

Provider catalog and site navigation coverage must be exact. A coordinated change can therefore fail intentionally between the provider merge and the corresponding site update.

## Publication catalogs

Each publication root contains `docs/publication-catalog.json`.

Catalog schema version 1 contains:

- `schema_version`, the integer `1`;
- a non-empty `documents` array.

Catalog schema version 2 additionally permits an `assets` array for explicit non-Markdown asset roots.

Each document entry contains exactly:

- `id`, a stable lowercase kebab-case identifier within that publication;
- `source`, a safe relative POSIX Markdown path;
- `optional`, a boolean;
- `home`, a boolean.

Each catalog defines exactly one non-optional home document. Document IDs and source paths are unique within the publication. Catalog paths reject absolute paths, backslashes, colon-bearing Windows or NTFS-ambiguous forms, empty or dot components, parent traversal, `.git` components in any case, and symlink traversal.

Schema version 2 asset entries contain exactly `source`, `destination`, and `optional`. Asset source and destination roots must be unique and non-overlapping. Asset trees may not contain symlinks, `.git` subtrees, or Markdown files. Schema version 1 retains the legacy top-level `assets/` convention for non-Markdown files only; Markdown under that directory is not published implicitly.

## Navigation manifest

`site-manifest.json` uses schema version 2 and contains exactly:

- `schema_version`, the integer `2`;
- `home`, identifying one `publication` and `document` pair;
- `navigation`, a non-empty array.

Each navigation node is exactly one of:

- a page with `title`, `publication`, `document`, and `destination`;
- a section with `title` and a non-empty `children` array.

A page is identified by the namespaced pair `publication:document`, such as `skill:overview`. Page nodes do not duplicate catalog-owned source paths, optionality, or home flags.

The assembler enforces these invariants before publication:

- page and section fields may not be mixed;
- unsupported fields are rejected;
- every `publication:document` pair and generated destination is unique;
- every catalog document appears exactly once in navigation;
- unknown or omitted catalog documents are rejected;
- destination values are safe relative POSIX Markdown paths;
- the first page is the declared global home and generates `index.md`;
- a missing source is omitted only when its catalog entry is optional;
- an empty section after optional-document filtering is omitted.

Page and section order are public information architecture and must be reviewed as such.

## Repository-tree publication preparation

Repository trees are generated pages, not canonical provider documents.
`scripts/prepare_repository_tree_publication.py` creates a temporary site
publication root before assembly. It copies the site-owned documentation
templates and assets without following symlinks, then adds exactly four generated
document declarations and one `Repository trees` navigation section:

- `repository-trees/index.md`;
- `repository-trees/skill.md`;
- `repository-trees/policy.md`;
- `repository-trees/webapp.md`.

The canonical `docs/publication-catalog.json` and `site-manifest.json` are not
modified in place. The temporary declarations are passed through the ordinary
assembler, so exact catalog-to-navigation coverage and destination validation
still apply.

The preparation output root may not be a symlink, filesystem root, or a path
overlapping the canonical site source. A non-empty output directory is replaced
only when it contains the exact tool-owned marker.

## Repository-tree generation

`scripts/generate_repository_trees.py` runs after assembly and before static-site
generation. It uses `git ls-tree --full-tree -r -t -z HEAD` for each checked-out
provider repository. This has the following consequences:

- only tracked Git entries are listed;
- untracked working-tree files and `.git` administration data are excluded;
- directory, regular-file, symlink, and gitlink types come from Git metadata;
- symlinks and gitlinks are displayed but never followed;
- path text is HTML-escaped and path bytes are percent-encoded in GitHub URLs;
- directories precede files and each group is sorted deterministically;
- all GitHub links use the exact full commit returned by `git rev-parse HEAD`;
- cataloged Markdown receives a Pages link plus an immutable source link;
- uncataloged files link only to GitHub and their contents are not copied.

Workflow-call revision overrides are reflected in the generated links because
the generator reads the actual checked-out commit rather than the normal lock
file value.

## Assembly output boundary

`scripts/assemble_publications.py` assembles the prepared site publication and all locked provider publications into one temporary Zensical project.

The output root may not be a symlink, filesystem root, current working directory or its ancestor, a regular file, or a path that overlaps any publication root. A pre-existing non-empty output directory is removed only when it contains the assembler-owned `.publication-assembly-root` marker with the expected value. This prevents a mistyped `--output-root` from deleting unrelated data.

Asset traversal explicitly rejects file and directory symlinks before descending and never follows them.

## Generated link integrity

The build validates links after Zensical generates final HTML. `scripts/validate_site_links.py` reads `project.site_url`, checks generated pages and assets, validates same-site paths and fragments, and rejects links that escape the configured Pages path or target missing generated content.

External origins, non-HTTP schemes, same-origin URLs outside the configured project path, and browser text fragments are outside the generated artifact and are not validated as local content. Repository-tree source links are external immutable GitHub links; their URL construction is covered by unit tests rather than network requests during the build.

## Build provenance

Every uploaded Pages artifact contains `/build-provenance.json` with deterministic schema version 2:

- `schema_version`, the integer `2`;
- `repository`, currently `TakashiSasaki/templates`;
- `site_commit`, the full commit checked out into `site-source`;
- `publication_commits`, an object mapping publication names such as `skill`, `policy`, and `webapp` to their checked-out full commits.

`scripts/write_publication_provenance.py` receives provider commits through repeated `--publication-commit NAME=SHA` arguments. Names are lowercase kebab-case. Commit values are lowercase full 40-character SHAs. Duplicate publication names, mutable refs, abbreviated SHAs, invalid repository identifiers, missing output directories, and symbolic-link outputs are rejected.

The file excludes timestamps, workflow run IDs, and mutable refs. It identifies build inputs but is not a cryptographic signature or artifact attestation.

## Published deployment metadata

The deployment workflow captures a timestamp with `TZ=Asia/Tokyo` before invoking the reusable build. The accepted format is exactly `YYYY-MM-DD HH:MM:SS JST`. An empty timestamp produces the stable footer text `Preview build (not deployed)`.

`project.site_url` must remain `https://takashisasaki.github.io/templates/`. `scripts/finalize_site_metadata.py` normalizes the canonical link in every generated HTML page and rejects duplicate canonical links.

## Build and deployment policy

`.github/workflows/build-pages.yml` is build-only. It may run for pull requests targeting `site` or through `workflow_call`. It has `contents: read`, pins Python before executing repository Python code, resolves the locked publication revisions, checks out all publications, runs tests, prepares the temporary tree-page publication, assembles the portal, generates repository trees, strictly builds the site, records provenance, validates links, and uploads a Pages artifact. It contains no deployment job or Pages write authority.

`.github/workflows/deploy-pages.yml` is the sole deployment authority. Its only trigger is a push to `site`, and its deployment job additionally requires:

```text
github.repository == TakashiSasaki/templates
github.event_name == push
github.ref == refs/heads/site
```

Default-branch status is not an authorization input. Changing the default branch therefore cannot authorize deployment from `skill`, `policy`, `webapp`, or another ref.

Expected behavior:

| Event | Build artifact | Footer metadata | Pages deployment |
|---|---:|---|---:|
| pull request targeting `site` | yes | preview | no |
| push to `site` | yes | JST deployment timestamp | yes |
| `workflow_call` | yes | preview unless explicitly supplied | no |
| workflow on a provider branch | branch-local only | not applicable | no |
| push to any other branch | no site deployment workflow | not applicable | no |

## Dependency updates

`requirements.txt` pins the Zensical version. Update it intentionally, run the full integrated build, and review generated navigation, repository trees, canonical URLs, and link-validation results before merging.

## Local validation

Check out the four unrelated branches into separate directories at the commits recorded in `publication-sources.json`, then run:

```sh
python -m unittest discover --start-directory site/tests --verbose
python site/scripts/prepare_repository_tree_publication.py \
  --site-root site \
  --output-root site-publication
python site/scripts/assemble_publications.py \
  --publication site=site-publication \
  --publication skill=sources/skill \
  --publication policy=sources/policy \
  --publication webapp=sources/webapp \
  --site-root site-publication \
  --output-root build
python site/scripts/generate_repository_trees.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --publication skill=sources/skill \
  --publication policy=sources/policy \
  --publication webapp=sources/webapp
zensical build --config-file build/zensical.toml --clean --strict
python site/scripts/validate_site_links.py \
  --site-root build/site \
  --config-file build/zensical.toml
```

Use workflow-call revision overrides only for deliberate compatibility testing. Normal builds use the reviewed full-SHA lock file.
