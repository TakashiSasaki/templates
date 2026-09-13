from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one occurrence, found {count}: {old!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


build = Path(".github/workflows/build-pages.yml")
text = build.read_text(encoding="utf-8")
anchor = "      - 'feat/site-*'\n      - 'site-*'"
marker = "      - site-composition-audience-publication-staging\n"
if marker not in text:
    if text.count(anchor) != 1:
        raise SystemExit("build-pages branch anchor mismatch")
    text = text.replace(anchor, "      - 'feat/site-*'\n" + marker + "      - 'site-*'", 1)

old = '''      - name: Run site assembly tests
        if: ${{ steps.artifact.outputs.reused != 'true' }}
        run: PYTHONPATH=site-source python -m unittest discover --start-directory site-source/tests --verbose

      - name: Materialize staged publication mapping
        if: ${{ steps.artifact.outputs.reused != 'true' && (inputs.publication_staging_id != '' || inputs.publication_staging_ids != '') }}
        env:
          PUBLICATION_STAGING_ID: ${{ inputs.publication_staging_id }}
          PUBLICATION_STAGING_IDS: ${{ inputs.publication_staging_ids }}
        run: |
          staging_args=()
          if [ -n "$PUBLICATION_STAGING_IDS" ]; then
            staging_args+=(--staging-ids "$PUBLICATION_STAGING_IDS")
          else
            staging_args+=(--staging-id "$PUBLICATION_STAGING_ID")
          fi
          python site-source/scripts/materialize_publication_staging.py \\
            --site-root site-source \\
            "${staging_args[@]}"

'''
new = '''      - name: Materialize staged publication mapping
        if: ${{ steps.artifact.outputs.reused != 'true' && (inputs.publication_staging_id != '' || inputs.publication_staging_ids != '') }}
        env:
          PUBLICATION_STAGING_ID: ${{ inputs.publication_staging_id }}
          PUBLICATION_STAGING_IDS: ${{ inputs.publication_staging_ids }}
        run: |
          if [ -n "$PUBLICATION_STAGING_ID" ] && [ -n "$PUBLICATION_STAGING_IDS" ]; then
            echo "Select publication_staging_id or publication_staging_ids, not both" >&2
            exit 1
          fi
          staging_args=()
          if [ -n "$PUBLICATION_STAGING_IDS" ]; then
            staging_args+=(--staging-ids "$PUBLICATION_STAGING_IDS")
          else
            staging_args+=(--staging-id "$PUBLICATION_STAGING_ID")
          fi
          staged_root="$(python site-source/scripts/materialize_publication_staging.py \\
            --site-root site-source \\
            "${staging_args[@]}")"
          case "$staged_root" in
            "$GITHUB_WORKSPACE"/*) ;;
            *)
              echo "Staging materializer returned an unexpected root: $staged_root" >&2
              exit 1
              ;;
          esac
          test -f "$staged_root/site-manifest.json"
          test -f "$staged_root/reader-navigation-locales.json"
          echo "SITE_PUBLICATION_ROOT=$staged_root" >> "$GITHUB_ENV"

      - name: Run site assembly tests
        if: ${{ steps.artifact.outputs.reused != 'true' }}
        run: PYTHONPATH=site-source python -m unittest discover --start-directory site-source/tests --verbose

'''
if text.count(old) != 1:
    raise SystemExit(f"build-pages staging block mismatch: {text.count(old)}")
text = text.replace(old, new, 1)

old_root = '            --site-root site-source \\\n            --output-root site-publication'
new_root = '            --site-root "${SITE_PUBLICATION_ROOT:-site-source}" \\\n            --output-root site-publication'
if text.count(old_root) != 1:
    raise SystemExit(f"build-pages publication root mismatch: {text.count(old_root)}")
text = text.replace(old_root, new_root, 1)

old_translation = '          python site-source/scripts/publish_provider_translations.py \\\n            --publication site=site-publication'
new_translation = '          python site-source/scripts/publish_provider_translations.py \\\n            --reader-navigation-locales "${SITE_PUBLICATION_ROOT:-site-source}/reader-navigation-locales.json" \\\n            --publication site=site-publication'
if text.count(old_translation) != 1:
    raise SystemExit(f"build-pages translation root mismatch: {text.count(old_translation)}")
text = text.replace(old_translation, new_translation, 1)
build.write_text(text, encoding="utf-8")

for name in [
    ".github/workflows/check-publication-freshness.yml",
    ".github/workflows/provider-coexistence.yml",
    ".github/workflows/site-composition-materialization-cross-authority.yml",
    ".github/workflows/site-composition-playground-cross-authority.yml",
    ".github/workflows/site-full-qualification.yml",
]:
    p = Path(name)
    text = p.read_text(encoding="utf-8")
    marker = "      - site-composition-audience-publication-staging\n"
    if marker not in text:
        anchor = "      - 'feat/site-*'\n"
        if text.count(anchor) != 1:
            raise SystemExit(f"{name}: trigger anchor mismatch")
        p.write_text(text.replace(anchor, anchor + marker, 1), encoding="utf-8")

replace_once(
    "tests/test_composition_playground_cross_authority_workflow.py",
    '    "feat/site-*",\n}',
    '    "feat/site-*",\n    "site-composition-audience-publication-staging",\n}',
)
replace_once(
    "tests/test_publication_freshness_workflow.py",
    '["site", "feat/site-*", "codex/site-composition-playground-v1-shell"]',
    '["site", "feat/site-*", "site-composition-audience-publication-staging", "codex/site-composition-playground-v1-shell"]',
)

text = build.read_text(encoding="utf-8")
required = [
    "Resolve exact build inputs and reuse qualified PR artifact",
    "site-composition-audience-publication-staging",
    'staged_root="$(python site-source/scripts/materialize_publication_staging.py',
    "SITE_PUBLICATION_ROOT=$staged_root",
    '--site-root "${SITE_PUBLICATION_ROOT:-site-source}"',
    '--reader-navigation-locales "${SITE_PUBLICATION_ROOT:-site-source}/reader-navigation-locales.json"',
    "github.event.label.name == 'ci/browser'",
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit(f"missing integrated build semantics: {missing}")
if text.index("- name: Materialize staged publication mapping") > text.index("- name: Run site assembly tests"):
    raise SystemExit("staging must precede provider-dependent Site tests")
