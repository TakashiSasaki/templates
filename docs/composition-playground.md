# Composition Playground v1

Explore the initial composition that the canonical Composition provider has already computed for a production recipe and an explicit set of optional components.

This page consumes a published projection. It does not resolve dependencies, conflicts, ownership, or materialization rules in the browser.

<div id="composition-playground" class="composition-playground" data-projection-url="/composition/playground/composition-playground-v1.json.gz" data-provenance-url="/build-provenance.json">
  <p data-playground-status role="status" aria-live="polite">Loading the canonical Composition projection…</p>
  <div data-playground-app hidden>
    <section aria-labelledby="playground-selection-title">
      <h2 id="playground-selection-title">Selection</h2>
      <label for="playground-recipe">Production recipe</label>
      <select id="playground-recipe" data-playground-recipe></select>
      <fieldset>
        <legend>Optional components to include explicitly</legend>
        <div data-playground-optionals></div>
      </fieldset>
    </section>
    <section aria-labelledby="playground-result-title">
      <h2 id="playground-result-title">Canonical result</h2>
      <p data-playground-validity role="status" aria-live="polite" aria-atomic="true"></p>
      <dl class="composition-playground__provenance">
        <dt>Semantic source revision</dt>
        <dd><code data-playground-semantic-revision></code></dd>
        <dt>Published Composition provider revision</dt>
        <dd><code data-playground-provider-revision></code></dd>
        <dt>Projection identity</dt>
        <dd><code data-playground-projection-id></code></dd>
      </dl>
      <h3>Resolved components</h3>
      <ul data-playground-resolved></ul>
    </section>
    <section aria-labelledby="playground-config-title">
      <h2 id="playground-config-title">Canonical configuration</h2>
      <button type="button" data-playground-copy>Copy</button>
      <pre><code data-playground-config></code></pre>
    </section>
  </div>
</div>

## v1 scope

The v1 Playground fixes exclusions to an empty list, parameters to an empty object, mode to initial, and the target repository to empty. Existing-repository, update, and upgrade workflows are outside this page.

The canonical projection is published as deterministic gzip-compressed JSON. Compression is transport only; all Composition semantics and semantic provenance are contained in the decompressed provider projection. The displayed **semantic source revision** is the exact Composition revision recorded by that projection. The displayed **published Composition provider revision** comes separately from Site's `/build-provenance.json` and identifies the exact Composition checkout that supplied the asset to this Site build.

Those two revisions are not required to be equal. A publication-only Composition descendant may publish semantics computed at an equivalent ancestor. Composition publication CI authoritatively verifies that the semantic source revision is an ancestor of the provider revision and that Playground semantic inputs have not changed between them. The browser displays those identities but does not pretend to verify Git ancestry itself.

If either the canonical projection or Site build provenance is unavailable or malformed, the interactive result remains hidden and the page reports the failure. If the active Composition publication does not contain the Playground asset yet, the page itself remains available and reports that the provider asset is unavailable.
