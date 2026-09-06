# Composition Playground v1

Explore the initial composition that the canonical Composition provider has already computed for a production recipe and explicit optional-component intent.

This page consumes published provider projections. It does not resolve dependencies, conflicts, ownership, or materialization rules in the browser.

<div id="composition-playground" class="composition-playground" data-projection-url="/composition/playground/composition-playground-v1.json" data-intent-projection-url="/composition/playground/composition-playground-intent-v1.json" data-provenance-url="/build-provenance.json">
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
      <fieldset data-playground-webmcp-intent>
        <legend>WebMCP intent</legend>
        <label><input type="radio" name="playground-webmcp-intent" value="default" checked> Default</label>
        <label><input type="radio" name="playground-webmcp-intent" value="adopt"> Adopt</label>
        <label><input type="radio" name="playground-webmcp-intent" value="exclude"> Explicitly exclude</label>
        <p data-playground-webmcp-status role="status" aria-live="polite">Loading WebMCP intent projection…</p>
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
    <section data-playground-webmcp-result hidden aria-labelledby="playground-webmcp-result-title">
      <h2 id="playground-webmcp-result-title">Explicit WebMCP exclusion result</h2>
      <p data-playground-webmcp-validity></p>
      <h3>Canonical configuration</h3>
      <pre><code data-playground-webmcp-config></code></pre>
      <h3>Resolved components</h3><ul data-playground-webmcp-resolved></ul>
      <h3>Registered contracts</h3><ul data-playground-webmcp-contracts></ul>
      <h3>Resulting materials</h3><ul data-playground-webmcp-materials></ul>
      <p>This section is a lookup of a Composition-provider transition and outcome. Site does not calculate dependency closure.</p>
    </section>
    <section aria-labelledby="playground-config-title">
      <h2 id="playground-config-title">Canonical configuration</h2>
      <button type="button" data-playground-copy>Copy</button>
      <pre><code data-playground-config></code></pre>
    </section>

    <section class="composition-playground__explain" aria-labelledby="playground-explain-title" data-playground-explain hidden>
      <h2 id="playground-explain-title">Explain the result</h2>
      <p>These views render provenance and repository impact already contained in the Composition projection.</p>
      <details open><summary>Components and why they were selected</summary><div data-playground-groups></div></details>
      <details><summary>Registered contracts</summary><div data-playground-contracts></div></details>
      <details><summary>Initial repository impact</summary><p data-playground-plan-summary></p><div data-playground-material-tree></div></details>
    </section>
  </div>
</div>

## v1 scope

The canonical include projection retains the bounded `2^N` include-case table. Explicit exclusion is represented separately as provider-resolved single-component transitions rather than enumerating a `3^N` state space. For WebMCP the UI therefore distinguishes **Default**, **Adopt**, and **Explicitly exclude** while preserving the Composer's existing include/exclude authority.

Parameters remain an empty object, mode remains initial, and the target repository remains empty. Existing-repository, update, and upgrade workflows are outside this page.

Both canonical projections are published by the exact Composition provider revision as JSON assets. The intent projection uses an indexed encoding: non-negative values reference canonical resolution outcomes; negative values reference provider-supplied canonical errors. This encoding is transport only and does not move resolution logic into Site.

The displayed **semantic source revision** is the exact Composition revision recorded by the resolution projection. The displayed **published Composition provider revision** comes separately from Site's `/build-provenance.json`. The intent projection is accepted only when its semantic source revision and resolution projection identity match the loaded canonical resolution projection.

If a projection or Site build provenance is unavailable or malformed, the relevant interactive result fails closed instead of attempting browser-side dependency resolution.
