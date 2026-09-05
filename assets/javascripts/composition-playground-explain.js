(function (globalScope, factory) {
  "use strict";
  const api = factory(globalScope, globalScope.CompositionPlayground);
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  globalScope.CompositionPlaygroundExplain = api;
  if (globalScope.document) {
    const boot = () => {
      void api.mount(globalScope.document);
    };
    if (globalScope.document.readyState === "loading") {
      globalScope.document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
      boot();
    }
    const navigationDocument = globalScope.document$;
    if (navigationDocument && typeof navigationDocument.subscribe === "function") {
      navigationDocument.subscribe(() => {
        void api.mount(globalScope.document);
      });
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (globalScope, core) {
  "use strict";

  const text = Object.freeze({
    foundation: "Foundation",
    artifact: "Artifact",
    capability: "Capability",
    lifecycle: "Lifecycle",
    noContracts: "No contracts are registered by this composition.",
    noMaterials: "No initial material destinations are projected for this case.",
    recipeArtifact: "Selected as the recipe artifact.",
    recipeRequired: "Required by the selected recipe.",
    recipeDefault: "Selected by the recipe default set.",
    explicitInclude: "Explicitly included in this Playground selection.",
    dependency: "Required directly by",
    version: "version",
    directDependencies: "Direct dependencies",
    none: "none",
    ownership: "ownership",
    destination: "destination"
  });

  function requireCore() {
    if (!core) throw new Error("Composition Playground core consumer is not loaded");
    return core;
  }

  function sourceUrl(revision, path) {
    return `https://github.com/TakashiSasaki/templates/blob/${revision}/${path}`;
  }

  function reasonText(reason) {
    switch (reason.kind) {
      case "recipe-artifact": return text.recipeArtifact;
      case "recipe-required": return text.recipeRequired;
      case "recipe-default": return text.recipeDefault;
      case "explicit-include": return text.explicitInclude;
      case "dependency": return `${text.dependency} ${reason.from_component}.`;
      default: return `Selection provenance: ${reason.kind}.`;
    }
  }

  function reasonsForComponent(projection, item, componentIndex) {
    const mask = item.selection_reason_masks[componentIndex];
    if (!Number.isInteger(mask) || mask < 1) {
      throw new core.ProjectionError("MALFORMED_PROJECTION", "selection provenance mask is missing");
    }
    const bits = projection.reasonBits;
    const reasons = [];
    if (mask & bits.recipe_artifact) reasons.push({ kind: "recipe-artifact" });
    if (mask & bits.recipe_required) reasons.push({ kind: "recipe-required" });
    if (mask & bits.recipe_default) reasons.push({ kind: "recipe-default" });
    if (mask & bits.explicit_include) reasons.push({ kind: "explicit-include" });
    if (mask & bits.dependency) {
      const parents = item.dependency_edges
        .filter((edge) => edge[1] === componentIndex)
        .map((edge) => item.resolved_components[edge[0]]);
      if (parents.length === 0) {
        throw new core.ProjectionError("MALFORMED_PROJECTION", "dependency provenance has no projected direct parent");
      }
      for (const parent of parents) reasons.push({ kind: "dependency", from_component: parent });
    }
    return reasons;
  }

  function directDependenciesForComponent(item, componentIndex) {
    return item.dependency_edges
      .filter((edge) => edge[0] === componentIndex)
      .map((edge) => item.resolved_components[edge[1]]);
  }

  function componentGroups(projection, item) {
    const groups = new Map(["foundation", "artifact", "capability", "lifecycle"].map((role) => [role, []]));
    item.resolved_components.forEach((componentId, componentIndex) => {
      const component = projection.componentById.get(componentId);
      if (!component) throw new core.ProjectionError("MALFORMED_PROJECTION", `missing component metadata for ${componentId}`);
      const role = component.role;
      if (!groups.has(role)) throw new core.ProjectionError("MALFORMED_PROJECTION", `unsupported component role ${role}`);
      groups.get(role).push({
        id: component.id,
        role,
        version: component.version,
        summary: component.summary,
        directDependencies: directDependenciesForComponent(item, componentIndex),
        reasons: reasonsForComponent(projection, item, componentIndex),
        sourcePath: component.source_path,
        sourceUrl: sourceUrl(projection.semanticRevision, component.source_path)
      });
    });
    return Array.from(groups, ([role, components]) => ({ role, components }));
  }

  function contractsForCase(projection, item) {
    return item.contract_ids.map((index) => {
      const contract = projection.contractById.get(index);
      if (!contract) throw new core.ProjectionError("MALFORMED_PROJECTION", `missing contract metadata at index ${index}`);
      return contract;
    });
  }

  function materialsForCase(projection, item) {
    return item.material_ids.map((index) => {
      const material = projection.materialById.get(index);
      if (!material) throw new core.ProjectionError("MALFORMED_PROJECTION", `missing material metadata at index ${index}`);
      return material;
    }).slice().sort((left, right) => left.destination.localeCompare(right.destination));
  }

  function planSummary(item) {
    if (!item.initial_plan) return "No initial plan is available for this invalid case.";
    const counts = Object.entries(item.initial_plan.action_counts || {}).sort(([left], [right]) => left.localeCompare(right));
    if (counts.length === 0) return "The canonical empty-target initial plan contains no actions.";
    return `Canonical empty-target initial plan: ${counts.map(([action, count]) => `${count} ${action}`).join(", ")}.`;
  }

  function materialTree(materials) {
    const root = { children: new Map(), material: null };
    for (const material of materials) {
      const segments = material.destination.split("/").filter(Boolean);
      let node = root;
      segments.forEach((segment, position) => {
        if (!node.children.has(segment)) node.children.set(segment, { children: new Map(), material: null });
        node = node.children.get(segment);
        if (position === segments.length - 1) node.material = material;
      });
    }
    return root;
  }

  function appendTextList(document, parent, values) {
    const list = document.createElement("ul");
    for (const value of values) {
      const item = document.createElement("li");
      item.textContent = value;
      list.appendChild(item);
    }
    parent.appendChild(list);
  }

  function renderGroups(document, container, projection, item) {
    container.replaceChildren();
    for (const group of componentGroups(projection, item)) {
      if (group.components.length === 0) continue;
      const section = document.createElement("section");
      section.className = "composition-playground__component-group";
      const heading = document.createElement("h3");
      heading.textContent = text[group.role] || group.role;
      section.appendChild(heading);
      for (const component of group.components) {
        const details = document.createElement("details");
        details.className = "composition-playground__component";
        const summary = document.createElement("summary");
        summary.textContent = `${component.id} · ${text.version} ${component.version}`;
        details.appendChild(summary);
        const description = document.createElement("p");
        description.textContent = component.summary;
        details.appendChild(description);

        const whyHeading = document.createElement("h4");
        whyHeading.textContent = "Why selected?";
        details.appendChild(whyHeading);
        appendTextList(document, details, component.reasons.map(reasonText));

        const dependencies = document.createElement("p");
        dependencies.textContent = `${text.directDependencies}: ${component.directDependencies.length ? component.directDependencies.join(", ") : text.none}.`;
        details.appendChild(dependencies);

        const link = document.createElement("a");
        link.href = component.sourceUrl;
        link.textContent = "Open provider component descriptor";
        link.rel = "noopener";
        details.appendChild(link);
        section.appendChild(details);
      }
      container.appendChild(section);
    }
  }

  function renderContracts(document, container, projection, item) {
    container.replaceChildren();
    const contracts = contractsForCase(projection, item);
    if (contracts.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = text.noContracts;
      container.appendChild(empty);
      return;
    }
    const list = document.createElement("ul");
    for (const contract of contracts) {
      const row = document.createElement("li");
      const name = document.createElement("strong");
      name.textContent = contract.id;
      row.appendChild(name);
      row.appendChild(document.createTextNode(` — ${contract.purpose} (${contract.component})`));
      const paths = document.createElement("div");
      paths.className = "composition-playground__contract-paths";
      paths.textContent = `document: ${contract.document} · schema: ${contract.schema} · document schema v${contract.document_schema_version}`;
      row.appendChild(paths);
      list.appendChild(row);
    }
    container.appendChild(list);
  }

  function renderTreeNodes(document, parent, node) {
    const entries = Array.from(node.children.entries()).sort(([left], [right]) => left.localeCompare(right));
    const group = document.createElement("ul");
    for (const [segment, child] of entries) {
      const item = document.createElement("li");
      const label = document.createElement("span");
      if (child.material) {
        label.textContent = `${segment} — ${child.material.component}; ${text.ownership}: ${child.material.ownership}`;
      } else {
        label.textContent = segment;
      }
      item.appendChild(label);
      if (child.children.size) renderTreeNodes(document, item, child);
      group.appendChild(item);
    }
    parent.appendChild(group);
  }

  function renderMaterials(document, container, projection, item) {
    container.replaceChildren();
    const materials = materialsForCase(projection, item);
    if (materials.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = text.noMaterials;
      container.appendChild(empty);
      return;
    }
    renderTreeNodes(document, container, materialTree(materials));
  }

  function render(document, root, projection, item) {
    const explain = root.querySelector("[data-playground-explain]");
    const groups = root.querySelector("[data-playground-groups]");
    const contracts = root.querySelector("[data-playground-contracts]");
    const materialTreeNode = root.querySelector("[data-playground-material-tree]");
    const plan = root.querySelector("[data-playground-plan-summary]");
    if (!explain || !groups || !contracts || !materialTreeNode || !plan) return;
    renderGroups(document, groups, projection, item);
    renderContracts(document, contracts, projection, item);
    renderMaterials(document, materialTreeNode, projection, item);
    plan.textContent = planSummary(item);
    explain.hidden = false;
  }

  let coreUnsubscribe;
  let mountGeneration = 0;

  function hide(root) {
    const explain = root && root.querySelector("[data-playground-explain]");
    if (explain) explain.hidden = true;
  }

  function renderContext(event) {
    const context = event.context;
    const root = event.root || context?.root;
    if (!root || root !== globalScope.document?.getElementById("composition-playground")) return;
    if (event.type === "unmounted" || event.type === "error") {
      hide(root);
      return;
    }
    if (event.type !== "ready" && event.type !== "selection") return;
    try {
      render(globalScope.document, root, context.projection, context.currentCase);
    } catch (error) {
      hide(root);
      if (globalScope.console && typeof globalScope.console.warn === "function") {
        globalScope.console.warn("Composition Playground explainability rendering failed", error);
      }
    }
  }

  async function mount(document) {
    const c = requireCore();
    const invocationRoot = document && document.getElementById("composition-playground");
    const generation = ++mountGeneration;
    if (!coreUnsubscribe) {
      coreUnsubscribe = c.subscribe(renderContext);
    }
    const context = await c.ensureMounted(document);
    const activeRoot = document && document.getElementById("composition-playground");
    if (generation !== mountGeneration || activeRoot !== invocationRoot) {
      return null;
    }
    if (!context || context.root !== invocationRoot) {
      hide(invocationRoot);
      return null;
    }
    renderContext({ type: "ready", context });
    return { projection: context.projection, provenance: context.provenance, context };
  }

  return Object.freeze({
    text,
    sourceUrl,
    reasonText,
    reasonsForComponent,
    directDependenciesForComponent,
    componentGroups,
    contractsForCase,
    materialsForCase,
    planSummary,
    materialTree,
    render,
    mount
  });
});
