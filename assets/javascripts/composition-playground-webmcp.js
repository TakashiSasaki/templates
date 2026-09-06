(function (scope) {
  "use strict";

  const COMPONENT = "capability.webmcp";
  const INTENT_ID = "composition-playground-intent-v1";
  const STRATEGY = "indexed-single-explicit-exclusion-transitions";
  const MODES = new Set(["default", "adopt", "exclude"]);
  let state = { root: null, intent: null, mode: "default", context: null, generation: 0 };

  function exactSha(value) { return typeof value === "string" && /^[0-9a-f]{40}$/.test(value); }
  function fail(root, message) {
    const node = root.querySelector("[data-playground-webmcp-status]");
    if (node) node.textContent = message;
    root.dataset.playgroundWebmcpError = "true";
  }

  function validateIntent(raw, context) {
    if (!raw || raw.schema_version !== 1 || raw.projection_id !== INTENT_ID || raw.resolution_projection_id !== context.projection.projectionId || raw.strategy !== STRATEGY) {
      throw new Error("unsupported WebMCP intent projection");
    }
    if (!raw.source || raw.source.repository !== "TakashiSasaki/templates" || raw.source.authority !== "composition" || !exactSha(raw.source.revision)) {
      throw new Error("invalid WebMCP intent projection provenance");
    }
    if (raw.source.revision !== context.projection.semanticRevision) {
      throw new Error("WebMCP intent and resolution projections have different semantic revisions");
    }
    if (!raw.encoding || raw.encoding.nonnegative !== "canonical outcome id" || raw.encoding.negative !== "-(error index + 1)" || !Array.isArray(raw.errors) || !Array.isArray(raw.recipes)) {
      throw new Error("invalid WebMCP intent projection encoding");
    }
    return raw;
  }

  async function loadIntent(root, context, generation) {
    const url = root.dataset.intentProjectionUrl;
    if (!url) throw new Error("WebMCP intent projection URL is missing");
    const response = await scope.fetch(url, { credentials: "same-origin", cache: "no-cache" });
    if (!response.ok) throw new Error(`WebMCP intent projection request failed with HTTP ${response.status}`);
    const raw = await response.json();
    if (generation !== state.generation || root !== state.root) return null;
    return validateIntent(raw, context);
  }

  function recipeIntent(intent, recipeId) {
    return intent.recipes.find((entry) => entry && entry.id === recipeId) || null;
  }

  function decodeTransition(intent, encoded) {
    if (!Number.isSafeInteger(encoded)) throw new Error("invalid WebMCP exclusion transition encoding");
    if (encoded >= 0) return { valid: true, error: null, outcome_id: encoded };
    const error = intent.errors[-encoded - 1];
    if (!error || typeof error.code !== "string" || typeof error.message !== "string") throw new Error("WebMCP exclusion error index is out of range");
    return { valid: false, error, outcome_id: null };
  }

  function transitionFor(context) {
    const recipe = recipeIntent(state.intent, context.state.recipeId);
    if (!recipe || !Array.isArray(recipe.optional_components) || !recipe.optional_components.includes(COMPONENT)) return null;
    const position = recipe.optional_components.indexOf(COMPONENT);
    const row = recipe.cases && recipe.cases[context.currentCase.include_mask];
    if (!Array.isArray(row) || row.length !== recipe.optional_components.length) throw new Error("WebMCP exclusion case is absent from provider projection");
    return decodeTransition(state.intent, row[position]);
  }

  function setModeControls(root, mode, available) {
    root.querySelectorAll('[name="playground-webmcp-intent"]').forEach((radio) => {
      radio.disabled = !available;
      radio.checked = available && radio.value === mode;
    });
  }

  function coreCheckbox(root) {
    return Array.from(root.querySelectorAll('[data-playground-optionals] input[type="checkbox"]')).find((node) => node.value === COMPONENT) || null;
  }

  function renderList(document, node, values) {
    while (node.firstChild) node.removeChild(node.firstChild);
    for (const value of values) {
      const li = document.createElement("li");
      li.textContent = value;
      node.appendChild(li);
    }
  }

  function render(context) {
    const root = state.root;
    if (!root || !state.intent || !context) return;
    const checkbox = coreCheckbox(root);
    const recipe = recipeIntent(state.intent, context.state.recipeId);
    const available = Boolean(checkbox && recipe && recipe.optional_components.includes(COMPONENT));
    if (!available) state.mode = "default";
    if (state.mode === "adopt" && checkbox && !checkbox.checked) state.mode = "default";
    if (state.mode === "default" && checkbox && checkbox.checked) state.mode = "adopt";
    setModeControls(root, state.mode, available);

    const panel = root.querySelector("[data-playground-webmcp-result]");
    const status = root.querySelector("[data-playground-webmcp-status]");
    if (!panel || !status) return;
    panel.hidden = state.mode !== "exclude" || !available;
    if (!available) { status.textContent = "WebMCP is not optional for this recipe."; return; }
    if (state.mode === "default") { status.textContent = "Default: WebMCP intent is unspecified; the canonical include-only case is shown above."; return; }
    if (state.mode === "adopt") { status.textContent = "Adopt: capability.webmcp is an explicit include in the canonical case shown above."; return; }

    try {
      const transition = transitionFor(context);
      if (!transition) throw new Error("WebMCP exclusion transition is absent");
      const validity = root.querySelector("[data-playground-webmcp-validity]");
      const config = root.querySelector("[data-playground-webmcp-config]");
      const resolved = root.querySelector("[data-playground-webmcp-resolved]");
      const contracts = root.querySelector("[data-playground-webmcp-contracts]");
      const materials = root.querySelector("[data-playground-webmcp-materials]");
      config.textContent = JSON.stringify({ schema_version: 1, recipe: context.state.recipeId, components: { include: context.state.includes, exclude: [COMPONENT] }, parameters: {} }, null, 2) + "\n";
      if (!transition.valid) {
        validity.textContent = `Explicit exclusion is invalid (${transition.error.code}): ${transition.error.message}`;
        renderList(scope.document, resolved, []); renderList(scope.document, contracts, []); renderList(scope.document, materials, []);
        status.textContent = "Explicitly exclude: provider rejected this selection.";
        return;
      }
      const outcome = context.projection.outcomeById.get(transition.outcome_id);
      if (!outcome) throw new Error("WebMCP exclusion outcome is absent from resolution projection");
      validity.textContent = "Explicit exclusion is valid according to the canonical Composition provider.";
      renderList(scope.document, resolved, outcome.resolved_components);
      renderList(scope.document, contracts, outcome.contract_ids.map((id) => { const item = context.projection.contractById.get(id); return item ? `${item.component}: ${item.id}` : `contract ${id}`; }));
      renderList(scope.document, materials, outcome.material_ids.map((id) => { const item = context.projection.materialById.get(id); return item ? `${item.destination} (${item.component}, ${item.ownership})` : `material ${id}`; }));
      status.textContent = "Explicitly exclude: result is a provider-resolved transition; Site performed no dependency resolution.";
    } catch (error) {
      fail(root, error instanceof Error ? error.message : String(error));
      panel.hidden = true;
    }
  }

  function chooseMode(root, mode) {
    if (!MODES.has(mode) || !state.context) return;
    const checkbox = coreCheckbox(root);
    if (!checkbox) return;
    state.mode = mode;
    if (mode === "adopt" && !checkbox.checked) checkbox.click();
    else if ((mode === "default" || mode === "exclude") && checkbox.checked) checkbox.click();
    else render(state.context);
  }

  function mount(context) {
    const root = context.root;
    if (state.root !== root) {
      state = { root, intent: null, mode: "default", context, generation: state.generation + 1 };
      root.querySelectorAll('[name="playground-webmcp-intent"]').forEach((radio) => radio.addEventListener("change", () => { if (radio.checked) chooseMode(root, radio.value); }));
      const generation = state.generation;
      void loadIntent(root, context, generation).then((intent) => {
        if (!intent) return;
        state.intent = intent;
        render(state.context);
      }).catch((error) => fail(root, error instanceof Error ? error.message : String(error)));
    } else {
      state.context = context;
      render(context);
    }
  }

  const core = scope.CompositionPlayground;
  if (!core || typeof core.subscribe !== "function") return;
  core.subscribe((event) => {
    if ((event.type === "ready" || event.type === "selection") && event.context) mount(event.context);
    if (event.type === "unmounted") state = { root: null, intent: null, mode: "default", context: null, generation: state.generation + 1 };
  });
})(typeof globalThis !== "undefined" ? globalThis : this);
