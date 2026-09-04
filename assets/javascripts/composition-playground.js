(function (globalScope, factory) {
  "use strict";
  const api = factory();
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
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SUPPORTED_SCHEMA_VERSION = 1;
  const PROJECTION_ID = "composition-playground-v1";
  const FULL_SHA = /^[0-9a-f]{40}$/;

  const labels = Object.freeze({
    loading: "Loading the canonical Composition projection…",
    unavailable: "The canonical Composition Playground projection is not available in the active publication yet.",
    incompatible: "The published Composition Playground projection is incompatible with this Site consumer.",
    malformed: "The published Composition Playground projection is malformed and was rejected.",
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

  function validateProjection(raw, options) {
    const expectedRevision = options && options.expectedRevision ? options.expectedRevision : null;
    if (!isObject(raw)) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection must be an object");
    }
    if (raw.schema_version !== SUPPORTED_SCHEMA_VERSION || raw.projection_id !== PROJECTION_ID) {
      throw new ProjectionError("UNSUPPORTED_PROJECTION", "unsupported Playground projection version");
    }
    if (!isObject(raw.source) || raw.source.repository !== "TakashiSasaki/templates" || raw.source.authority !== "composition" || !FULL_SHA.test(raw.source.revision || "")) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection source provenance is invalid");
    }
    if (expectedRevision !== null) {
      if (!FULL_SHA.test(expectedRevision) || raw.source.revision !== expectedRevision) {
        throw new ProjectionError("SOURCE_REVISION_MISMATCH", "projection source revision does not match the expected Composition revision");
      }
    }
    if (!isObject(raw.scope) || raw.scope.mode !== "initial" || raw.scope.target !== "empty" || JSON.stringify(raw.scope.components_exclude) !== "[]" || JSON.stringify(raw.scope.parameters) !== "{}") {
      throw new ProjectionError("UNSUPPORTED_PROJECTION", "projection scope is outside Playground v1");
    }

    const recipes = requireArray(raw.recipes, "recipes");
    const components = requireArray(raw.components, "components");
    const contracts = requireArray(raw.contracts, "contracts");
    const materials = requireArray(raw.materials, "materials");
    const cases = requireArray(raw.cases, "cases");
    const recipeById = new Map();
    const componentById = new Map();
    const caseByKey = new Map();
    const contractById = new Map();
    const materialById = new Map();

    for (const recipe of recipes) {
      if (!isObject(recipe) || typeof recipe.id !== "string" || recipeById.has(recipe.id)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "recipe inventory is invalid or duplicated");
      }
      requireUniqueStrings(recipe.optional_components, `recipe ${recipe.id} optional_components`);
      recipeById.set(recipe.id, recipe);
    }
    if (recipeById.size === 0) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection has no recipes");
    }

    for (const component of components) {
      if (!isObject(component) || typeof component.id !== "string" || componentById.has(component.id)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "component inventory is invalid or duplicated");
      }
      requireUniqueStrings(component.requires, `component ${component.id} requires`);
      componentById.set(component.id, component);
    }

    for (const contract of contracts) {
      if (!isObject(contract) || !Number.isInteger(contract.index) || contractById.has(contract.index)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "contract inventory is invalid or duplicated");
      }
      contractById.set(contract.index, contract);
    }
    for (const material of materials) {
      if (!isObject(material) || !Number.isInteger(material.index) || materialById.has(material.index)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "material inventory is invalid or duplicated");
      }
      materialById.set(material.index, material);
    }

    for (const item of cases) {
      if (!isObject(item) || typeof item.key !== "string" || caseByKey.has(item.key) || !recipeById.has(item.recipe) || typeof item.valid !== "boolean" || !isObject(item.configuration)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "case inventory is invalid or duplicated");
      }
      requireUniqueStrings(item.explicit_includes, `case ${item.key} explicit_includes`);
      requireUniqueStrings(item.resolved_components, `case ${item.key} resolved_components`);
      caseByKey.set(item.key, item);
    }

    return Object.freeze({
      raw,
      sourceRevision: raw.source.revision,
      recipes,
      components,
      contracts,
      materials,
      cases,
      recipeById,
      componentById,
      contractById,
      materialById,
      caseByKey
    });
  }

  function caseKey(recipe, includes) {
    if (!isObject(recipe) || typeof recipe.id !== "string") {
      throw new ProjectionError("INVALID_SELECTION", "recipe is missing from the projection inventory");
    }
    const optionals = requireUniqueStrings(recipe.optional_components, `recipe ${recipe.id} optional_components`);
    const selected = requireUniqueStrings(Array.from(includes || []), "explicit includes");
    const index = new Map(optionals.map((componentId, position) => [componentId, position]));
    let mask = 0n;
    for (const componentId of selected) {
      if (!index.has(componentId)) {
        throw new ProjectionError("INVALID_SELECTION", `component ${componentId} is not exposed by recipe ${recipe.id}`);
      }
      mask |= 1n << BigInt(index.get(componentId));
    }
    return `${recipe.id}:${mask.toString(16)}`;
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
    caseKey(recipe, includes);
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

  function lookupCase(projection, recipeId, includes) {
    const recipe = projection.recipeById.get(recipeId);
    if (!recipe) {
      throw new ProjectionError("INVALID_SELECTION", `unknown recipe: ${recipeId}`);
    }
    const key = caseKey(recipe, includes);
    const item = projection.caseByKey.get(key);
    if (!item) {
      throw new ProjectionError("MALFORMED_PROJECTION", `projection does not contain canonical case ${key}`);
    }
    return item;
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

  function renderCase(document, nodes, projection, item) {
    nodes.revision.textContent = projection.sourceRevision;
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

  async function loadProjection(url, options) {
    let response;
    try {
      response = await fetch(url, { credentials: "same-origin", cache: "no-cache" });
    } catch (error) {
      throw new ProjectionError("PROJECTION_UNAVAILABLE", error instanceof Error ? error.message : String(error));
    }
    if (!response.ok) {
      throw new ProjectionError("PROJECTION_UNAVAILABLE", `projection request failed with HTTP ${response.status}`);
    }
    let raw;
    try {
      raw = await response.json();
    } catch (error) {
      throw new ProjectionError("MALFORMED_PROJECTION", error instanceof Error ? error.message : String(error));
    }
    return validateProjection(raw, options);
  }

  function statusForError(error) {
    if (error instanceof ProjectionError) {
      if (error.code === "PROJECTION_UNAVAILABLE") return labels.unavailable;
      if (error.code === "UNSUPPORTED_PROJECTION" || error.code === "SOURCE_REVISION_MISMATCH") return `${labels.incompatible} ${error.message}`;
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
      revision: root.querySelector("[data-playground-revision]"),
      resolved: root.querySelector("[data-playground-resolved]"),
      config: root.querySelector("[data-playground-config]"),
      copy: root.querySelector("[data-playground-copy]")
    };
    if (!status || !app || Object.values(nodes).some((node) => !node)) return null;
    status.textContent = labels.loading;

    try {
      const projection = await loadProjection(root.dataset.projectionUrl);
      let state = parseHash(globalScope.location ? globalScope.location.hash : "", projection);
      let currentCase = null;

      const readControlState = () => ({
        recipeId: nodes.recipe.value,
        includes: Array.from(nodes.optionals.querySelectorAll("input[type=checkbox]:checked"), (node) => node.value)
      });
      const apply = (nextState, replaceHash) => {
        state = nextState;
        renderSelection(document, nodes, projection, state, () => apply(readControlState(), false));
        currentCase = lookupCase(projection, state.recipeId, state.includes);
        renderCase(document, nodes, projection, currentCase);
        if (globalScope.history && globalScope.location) {
          const nextHash = stateHash(state.recipeId, state.includes);
          const url = `${globalScope.location.pathname}${globalScope.location.search}${nextHash}`;
          if (replaceHash) globalScope.history.replaceState(null, "", url);
          else globalScope.history.pushState(null, "", url);
        }
      };

      nodes.recipe.addEventListener("change", () => apply({ recipeId: nodes.recipe.value, includes: [] }, false));
      nodes.copy.addEventListener("click", async () => {
        try {
          await globalScope.navigator.clipboard.writeText(configurationText(currentCase));
          status.textContent = labels.copied;
        } catch (_error) {
          status.textContent = labels.copyFailed;
        }
      });
      if (globalScope.addEventListener) {
        globalScope.addEventListener("hashchange", () => {
          try {
            apply(parseHash(globalScope.location.hash, projection), true);
          } catch (error) {
            status.textContent = statusForError(error);
          }
        });
      }

      apply(state, true);
      app.hidden = false;
      status.textContent = "Canonical Composition projection loaded.";
      return { projection, state, currentCase };
    } catch (error) {
      app.hidden = true;
      status.textContent = statusForError(error);
      root.dataset.playgroundError = error instanceof ProjectionError ? error.code : "UNKNOWN";
      return null;
    }
  }

  return Object.freeze({
    SUPPORTED_SCHEMA_VERSION,
    ProjectionError,
    labels,
    validateProjection,
    caseKey,
    parseHash,
    stateHash,
    lookupCase,
    configurationText,
    loadProjection,
    statusForError,
    mount
  });
});
