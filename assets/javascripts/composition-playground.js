(function (globalScope, factory) {
  "use strict";
  const api = factory(globalScope);
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  globalScope.CompositionPlayground = api;
  if (globalScope.document) {
    const boot = () => api.mount(globalScope.document);
    if (globalScope.document.readyState === "loading") {
      globalScope.document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
      boot();
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (scope) {
  "use strict";

  const SUPPORTED_SCHEMA_VERSION = 1;
  const PROJECTION_ID = "composition-playground-v1";
  const BUILD_PROVENANCE_SCHEMA_VERSION = 2;
  const FULL_SHA = /^[0-9a-f]{40}$/;
  const EXPECTED_REASON_BITS = Object.freeze({
    recipe_artifact: 1,
    recipe_required: 2,
    recipe_default: 4,
    explicit_include: 8,
    dependency: 16
  });

  const labels = Object.freeze({
    loading: "Loading the canonical Composition projection…",
    unavailable: "The canonical Composition Playground projection is not available in the active publication yet.",
    provenanceUnavailable: "The Site build provenance required to identify the published Composition provider is unavailable.",
    incompatible: "The published Composition Playground projection is incompatible with this Site consumer.",
    malformed: "The published Composition Playground projection or Site build provenance is malformed and was rejected.",
    valid: "This selection is valid for canonical initial composition.",
    invalid: "This selection is invalid according to the canonical Composition provider.",
    copied: "Canonical configuration copied.",
    copyFailed: "Could not copy the canonical configuration."
  });

  class ProjectionError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "ProjectionError";
      this.code = code;
    }
  }

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function requireArray(value, name) {
    if (!Array.isArray(value)) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must be an array`);
    }
    return value;
  }

  function requireUniqueStrings(value, name) {
    const entries = requireArray(value, name);
    if (entries.some((entry) => typeof entry !== "string") || new Set(entries).size !== entries.length) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must contain unique strings`);
    }
    return entries;
  }

  function sameReasonBits(value) {
    return isObject(value) && Object.keys(EXPECTED_REASON_BITS).every(
      (name) => value[name] === EXPECTED_REASON_BITS[name]
    ) && Object.keys(value).length === Object.keys(EXPECTED_REASON_BITS).length;
  }

  function validateProjection(raw) {
    if (!isObject(raw)) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection must be an object");
    }
    if (raw.schema_version !== SUPPORTED_SCHEMA_VERSION || raw.projection_id !== PROJECTION_ID) {
      throw new ProjectionError("UNSUPPORTED_PROJECTION", "unsupported Playground projection version");
    }
    if (!isObject(raw.source) || raw.source.repository !== "TakashiSasaki/templates" || raw.source.authority !== "composition" || !FULL_SHA.test(raw.source.revision || "")) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection semantic source provenance is invalid");
    }
    if (!isObject(raw.scope) || raw.scope.mode !== "initial" || raw.scope.target !== "empty" || raw.scope.configuration_schema_version !== 1 || JSON.stringify(raw.scope.components_exclude) !== "[]" || JSON.stringify(raw.scope.parameters) !== "{}") {
      throw new ProjectionError("UNSUPPORTED_PROJECTION", "projection scope is outside Playground v1");
    }
    if (!sameReasonBits(raw.provenance_reason_bits)) {
      throw new ProjectionError("UNSUPPORTED_PROJECTION", "projection provenance encoding is incompatible with this Site consumer");
    }

    const recipes = requireArray(raw.recipes, "recipes");
    const components = requireArray(raw.components, "components");
    const contracts = requireArray(raw.contracts, "contracts");
    const materials = requireArray(raw.materials, "materials");
    const outcomes = requireArray(raw.outcomes, "outcomes");
    const recipeById = new Map();
    const componentById = new Map();
    const contractById = new Map();
    const materialById = new Map();
    const outcomeById = new Map();

    for (const component of components) {
      if (!isObject(component) || typeof component.id !== "string" || componentById.has(component.id)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "component inventory is invalid or duplicated");
      }
      requireUniqueStrings(component.requires, `component ${component.id} requires`);
      componentById.set(component.id, component);
    }

    for (const contract of contracts) {
      if (!isObject(contract) || !Number.isInteger(contract.index) || contract.index < 0 || contractById.has(contract.index)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "contract inventory is invalid or duplicated");
      }
      contractById.set(contract.index, contract);
    }
    for (const material of materials) {
      if (!isObject(material) || !Number.isInteger(material.index) || material.index < 0 || materialById.has(material.index)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "material inventory is invalid or duplicated");
      }
      materialById.set(material.index, material);
    }

    for (const outcome of outcomes) {
      if (!isObject(outcome) || !Number.isInteger(outcome.index) || outcome.index < 0 || outcomeById.has(outcome.index)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "outcome inventory is invalid or duplicated");
      }
      const resolved = requireUniqueStrings(outcome.resolved_components, `outcome ${outcome.index} resolved_components`);
      for (const componentId of resolved) {
        if (!componentById.has(componentId)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} references an unknown component`);
        }
      }
      for (const edge of requireArray(outcome.dependency_edges, `outcome ${outcome.index} dependency_edges`)) {
        if (!Array.isArray(edge) || edge.length !== 2 || edge.some((position) => !Number.isInteger(position) || position < 0 || position >= resolved.length)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} has an invalid dependency edge`);
        }
      }
      for (const contractId of requireArray(outcome.contract_ids, `outcome ${outcome.index} contract_ids`)) {
        if (!contractById.has(contractId)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} references an unknown contract`);
        }
      }
      for (const materialId of requireArray(outcome.material_ids, `outcome ${outcome.index} material_ids`)) {
        if (!materialById.has(materialId)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} references an unknown material`);
        }
      }
      if (!isObject(outcome.initial_plan) || !isObject(outcome.initial_plan.action_counts) || outcome.initial_plan.conflict_count !== 0) {
        throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} has an invalid initial plan`);
      }
      outcomeById.set(outcome.index, outcome);
    }
    if (outcomeById.size === 0) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection has no canonical outcomes");
    }

    for (const recipe of recipes) {
      if (!isObject(recipe) || typeof recipe.id !== "string" || recipeById.has(recipe.id)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "recipe inventory is invalid or duplicated");
      }
      const optionals = requireUniqueStrings(recipe.optional_components, `recipe ${recipe.id} optional_components`);
      const cases = requireArray(recipe.cases, `recipe ${recipe.id} cases`);
      const expectedCaseCount = 2 ** optionals.length;
      if (!Number.isSafeInteger(expectedCaseCount) || recipe.case_count !== expectedCaseCount || cases.length !== expectedCaseCount) {
        throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} case table does not cover its optional-component domain`);
      }
      for (let mask = 0; mask < cases.length; mask += 1) {
        const item = cases[mask];
        if (!isObject(item) || typeof item.valid !== "boolean" || !Array.isArray(item.selection_reason_masks)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} case ${mask} is malformed`);
        }
        if (item.valid) {
          const outcome = outcomeById.get(item.outcome_id);
          if (item.error !== null || !outcome || item.selection_reason_masks.length !== outcome.resolved_components.length || item.selection_reason_masks.some((reasonMask) => !Number.isInteger(reasonMask) || reasonMask < 1 || reasonMask > 31)) {
            throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} valid case ${mask} is inconsistent with its outcome`);
          }
        } else if (item.outcome_id !== null || !isObject(item.error) || typeof item.error.code !== "string" || item.selection_reason_masks.length !== 0) {
          throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} invalid case ${mask} is inconsistent`);
        }
      }
      recipeById.set(recipe.id, recipe);
    }
    if (recipeById.size === 0) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection has no recipes");
    }

    return Object.freeze({
      raw,
      semanticRevision: raw.source.revision,
      projectionId: raw.projection_id,
      scope: raw.scope,
      reasonBits: raw.provenance_reason_bits,
      recipes,
      components,
      contracts,
      materials,
      outcomes,
      recipeById,
      componentById,
      contractById,
      materialById,
      outcomeById
    });
  }

  function validateBuildProvenance(raw) {
    if (!isObject(raw) || raw.schema_version !== BUILD_PROVENANCE_SCHEMA_VERSION || raw.repository !== "TakashiSasaki/templates" || !isObject(raw.publication_commits)) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site build provenance has an unsupported shape");
    }
    const providerRevision = raw.publication_commits.composition;
    if (!FULL_SHA.test(providerRevision || "")) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site build provenance has no exact Composition provider revision");
    }
    return Object.freeze({ raw, providerRevision });
  }

  function selectionMask(recipe, includes) {
    if (!isObject(recipe) || typeof recipe.id !== "string") {
      throw new ProjectionError("INVALID_SELECTION", "recipe is missing from the projection inventory");
    }
    const optionals = requireUniqueStrings(recipe.optional_components, `recipe ${recipe.id} optional_components`);
    const selected = requireUniqueStrings(Array.from(includes || []), "explicit includes");
    const index = new Map(optionals.map((componentId, position) => [componentId, position]));
    let mask = 0;
    for (const componentId of selected) {
      if (!index.has(componentId)) {
        throw new ProjectionError("INVALID_SELECTION", `component ${componentId} is not exposed by recipe ${recipe.id}`);
      }
      mask += 2 ** index.get(componentId);
    }
    if (!Number.isSafeInteger(mask)) {
      throw new ProjectionError("INVALID_SELECTION", "selection mask exceeds the supported integer range");
    }
    return mask;
  }

  function caseKey(recipe, includes) {
    return `${recipe.id}:${selectionMask(recipe, includes).toString(16)}`;
  }

  function explicitIncludes(recipe, mask) {
    return recipe.optional_components.filter((_componentId, position) => (mask & (2 ** position)) !== 0);
  }

  function parseHash(hash, projection) {
    const text = typeof hash === "string" ? hash.replace(/^#/, "") : "";
    const params = new URLSearchParams(text);
    const recipeId = params.get("recipe") || projection.recipes[0].id;
    const recipe = projection.recipeById.get(recipeId);
    if (!recipe) {
      throw new ProjectionError("INVALID_SELECTION", `unknown recipe in URL hash: ${recipeId}`);
    }
    const includes = params.getAll("include");
    selectionMask(recipe, includes);
    return { recipeId, includes: includes.slice().sort() };
  }

  function stateHash(recipeId, includes) {
    const params = new URLSearchParams();
    params.set("recipe", recipeId);
    for (const componentId of Array.from(includes || []).slice().sort()) {
      params.append("include", componentId);
    }
    return `#${params.toString()}`;
  }

  function configurationForSelection(projection, recipeId, includes) {
    const recipe = projection.recipeById.get(recipeId);
    if (!recipe) {
      throw new ProjectionError("INVALID_SELECTION", `unknown recipe: ${recipeId}`);
    }
    const mask = selectionMask(recipe, includes);
    const normalizedIncludes = explicitIncludes(recipe, mask);
    return {
      schema_version: projection.scope.configuration_schema_version,
      recipe: recipeId,
      components: {
        include: normalizedIncludes,
        exclude: projection.scope.components_exclude.slice()
      },
      parameters: { ...projection.scope.parameters }
    };
  }

  function lookupCase(projection, recipeId, includes) {
    const recipe = projection.recipeById.get(recipeId);
    if (!recipe) {
      throw new ProjectionError("INVALID_SELECTION", `unknown recipe: ${recipeId}`);
    }
    const mask = selectionMask(recipe, includes);
    const compactCase = recipe.cases[mask];
    if (!compactCase) {
      throw new ProjectionError("MALFORMED_PROJECTION", `projection does not contain canonical case ${recipeId}:${mask.toString(16)}`);
    }
    const normalizedIncludes = explicitIncludes(recipe, mask);
    const outcome = compactCase.valid ? projection.outcomeById.get(compactCase.outcome_id) : null;
    return Object.freeze({
      key: `${recipeId}:${mask.toString(16)}`,
      recipe: recipeId,
      include_mask: mask,
      explicit_includes: normalizedIncludes,
      configuration: configurationForSelection(projection, recipeId, normalizedIncludes),
      valid: compactCase.valid,
      error: compactCase.error,
      outcome_id: compactCase.outcome_id,
      selection_reason_masks: compactCase.selection_reason_masks.slice(),
      resolved_components: outcome ? outcome.resolved_components : [],
      dependency_edges: outcome ? outcome.dependency_edges : [],
      contract_ids: outcome ? outcome.contract_ids : [],
      material_ids: outcome ? outcome.material_ids : [],
      initial_plan: outcome ? outcome.initial_plan : null
    });
  }

  function configurationText(item) {
    return `${JSON.stringify(item.configuration, null, 2)}\n`;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function textNode(document, tagName, text) {
    const node = document.createElement(tagName);
    node.textContent = text;
    return node;
  }

  function renderSelection(document, nodes, projection, state, onChange) {
    clear(nodes.recipe);
    for (const recipe of projection.recipes) {
      const option = document.createElement("option");
      option.value = recipe.id;
      option.textContent = recipe.id;
      option.selected = recipe.id === state.recipeId;
      nodes.recipe.appendChild(option);
    }

    clear(nodes.optionals);
    const recipe = projection.recipeById.get(state.recipeId);
    const selected = new Set(state.includes);
    for (const componentId of recipe.optional_components) {
      const label = document.createElement("label");
      label.className = "composition-playground__option";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = componentId;
      checkbox.checked = selected.has(componentId);
      checkbox.addEventListener("change", onChange);
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(` ${componentId}`));
      nodes.optionals.appendChild(label);
    }
  }

  function renderCase(document, nodes, projection, provenance, item) {
    nodes.semanticRevision.textContent = projection.semanticRevision;
    nodes.providerRevision.textContent = provenance.providerRevision;
    nodes.projectionId.textContent = projection.projectionId;
    nodes.validity.textContent = item.valid
      ? labels.valid
      : `${labels.invalid}${item.error && item.error.code ? ` (${item.error.code})` : ""}`;
    clear(nodes.resolved);
    if (item.resolved_components.length === 0) {
      nodes.resolved.appendChild(textNode(document, "li", "No resolved components are available for this invalid case."));
    } else {
      for (const componentId of item.resolved_components) {
        nodes.resolved.appendChild(textNode(document, "li", componentId));
      }
    }
    nodes.config.textContent = configurationText(item);
  }

  async function decodeProjectionResponse(response, url) {
    try {
      if (typeof url === "string" && url.endsWith(".gz")) {
        if (typeof scope.DecompressionStream !== "function" || !response.body) {
          throw new ProjectionError("UNSUPPORTED_PROJECTION", "gzip projection decoding is not supported by this browser");
        }
        const stream = response.body.pipeThrough(new scope.DecompressionStream("gzip"));
        const text = await new scope.Response(stream).text();
        return JSON.parse(text);
      }
      return await response.json();
    } catch (error) {
      if (error instanceof ProjectionError) throw error;
      throw new ProjectionError("MALFORMED_PROJECTION", error instanceof Error ? error.message : String(error));
    }
  }

  async function loadProjection(url) {
    let response;
    try {
      response = await scope.fetch(url, { credentials: "same-origin", cache: "no-cache" });
    } catch (error) {
      throw new ProjectionError("PROJECTION_UNAVAILABLE", error instanceof Error ? error.message : String(error));
    }
    if (!response.ok) {
      throw new ProjectionError("PROJECTION_UNAVAILABLE", `projection request failed with HTTP ${response.status}`);
    }
    const raw = await decodeProjectionResponse(response, url);
    return validateProjection(raw);
  }

  async function loadBuildProvenance(url) {
    let response;
    try {
      response = await scope.fetch(url, { credentials: "same-origin", cache: "no-cache" });
    } catch (error) {
      throw new ProjectionError("PROVENANCE_UNAVAILABLE", error instanceof Error ? error.message : String(error));
    }
    if (!response.ok) {
      throw new ProjectionError("PROVENANCE_UNAVAILABLE", `build provenance request failed with HTTP ${response.status}`);
    }
    try {
      return validateBuildProvenance(await response.json());
    } catch (error) {
      if (error instanceof ProjectionError) throw error;
      throw new ProjectionError("MALFORMED_PROVENANCE", error instanceof Error ? error.message : String(error));
    }
  }

  function statusForError(error) {
    if (error instanceof ProjectionError) {
      if (error.code === "PROJECTION_UNAVAILABLE") return labels.unavailable;
      if (error.code === "PROVENANCE_UNAVAILABLE") return labels.provenanceUnavailable;
      if (error.code === "UNSUPPORTED_PROJECTION") return `${labels.incompatible} ${error.message}`;
      return `${labels.malformed} ${error.message}`;
    }
    return labels.malformed;
  }

  async function mount(document) {
    const root = document.getElementById("composition-playground");
    if (!root || root.dataset.playgroundMounted === "true") return null;
    root.dataset.playgroundMounted = "true";
    const status = root.querySelector("[data-playground-status]");
    const app = root.querySelector("[data-playground-app]");
    const nodes = {
      recipe: root.querySelector("[data-playground-recipe]"),
      optionals: root.querySelector("[data-playground-optionals]"),
      validity: root.querySelector("[data-playground-validity]"),
      semanticRevision: root.querySelector("[data-playground-semantic-revision]"),
      providerRevision: root.querySelector("[data-playground-provider-revision]"),
      projectionId: root.querySelector("[data-playground-projection-id]"),
      resolved: root.querySelector("[data-playground-resolved]"),
      config: root.querySelector("[data-playground-config]"),
      copy: root.querySelector("[data-playground-copy]")
    };
    if (!status || !app || Object.values(nodes).some((node) => !node)) return null;
    status.textContent = labels.loading;

    try {
      const [projection, provenance] = await Promise.all([
        loadProjection(root.dataset.projectionUrl),
        loadBuildProvenance(root.dataset.provenanceUrl || "/build-provenance.json")
      ]);
      let state = parseHash(scope.location ? scope.location.hash : "", projection);
      let currentCase = null;

      const readControlState = () => ({
        recipeId: nodes.recipe.value,
        includes: Array.from(nodes.optionals.querySelectorAll("input[type=checkbox]:checked"), (node) => node.value)
      });
      const apply = (nextState, replaceHash) => {
        state = nextState;
        renderSelection(document, nodes, projection, state, () => apply(readControlState(), false));
        currentCase = lookupCase(projection, state.recipeId, state.includes);
        renderCase(document, nodes, projection, provenance, currentCase);
        if (scope.history && scope.location) {
          const nextHash = stateHash(state.recipeId, state.includes);
          const url = `${scope.location.pathname}${scope.location.search}${nextHash}`;
          if (replaceHash) scope.history.replaceState(null, "", url);
          else scope.history.pushState(null, "", url);
        }
      };

      nodes.recipe.addEventListener("change", () => apply({ recipeId: nodes.recipe.value, includes: [] }, false));
      nodes.copy.addEventListener("click", async () => {
        try {
          await scope.navigator.clipboard.writeText(configurationText(currentCase));
          status.textContent = labels.copied;
        } catch (_error) {
          status.textContent = labels.copyFailed;
        }
      });
      if (scope.addEventListener) {
        scope.addEventListener("hashchange", () => {
          try {
            apply(parseHash(scope.location.hash, projection), true);
          } catch (error) {
            status.textContent = statusForError(error);
          }
        });
      }

      apply(state, true);
      app.hidden = false;
      status.textContent = "Canonical Composition projection loaded with exact Site publication provenance.";
      return { projection, provenance, state, currentCase };
    } catch (error) {
      app.hidden = true;
      status.textContent = statusForError(error);
      root.dataset.playgroundError = error instanceof ProjectionError ? error.code : "UNKNOWN";
      return null;
    }
  }

  return Object.freeze({
    SUPPORTED_SCHEMA_VERSION,
    BUILD_PROVENANCE_SCHEMA_VERSION,
    EXPECTED_REASON_BITS,
    ProjectionError,
    labels,
    validateProjection,
    validateBuildProvenance,
    selectionMask,
    caseKey,
    explicitIncludes,
    parseHash,
    stateHash,
    configurationForSelection,
    lookupCase,
    configurationText,
    decodeProjectionResponse,
    loadProjection,
    loadBuildProvenance,
    statusForError,
    mount
  });
});
