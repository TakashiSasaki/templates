(function (globalScope, factory) {
  "use strict";
  const api = factory(globalScope);
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  globalScope.CompositionPlayground = api;
  if (globalScope.document) {
    const boot = () => {
      void api.ensureMounted(globalScope.document);
    };
    if (globalScope.document.readyState === "loading") {
      globalScope.document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
      boot();
    }
    const navigationDocument = globalScope.document$;
    if (navigationDocument && typeof navigationDocument.subscribe === "function") {
      navigationDocument.subscribe(() => {
        void api.ensureMounted(globalScope.document);
      });
    }
    if (typeof globalScope.addEventListener === "function") {
      globalScope.addEventListener("online", boot);
    }
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (scope) {
  "use strict";

  const SUPPORTED_SCHEMA_VERSION = 1;
  const PROJECTION_ID = "composition-playground-v1";
  const BUILD_PROVENANCE_SCHEMA_VERSION = 2;
  const FULL_SHA = /^[0-9a-f]{40}$/;
  const COMPONENT_ROLES = Object.freeze(["foundation", "artifact", "capability", "lifecycle"]);
  const EXPECTED_REASON_BITS = Object.freeze({
    recipe_artifact: 1,
    recipe_required: 2,
    recipe_default: 4,
    explicit_include: 8,
    dependency: 16
  });

  const labels = Object.freeze({
    loading: "Loading the canonical Composition projection…",
    loaded: "Canonical Composition projection loaded with exact Site publication provenance.",
    unavailable: "The canonical Composition Playground projection is not available in the active publication yet.",
    provenanceUnavailable: "The Site build provenance required to identify the published Composition provider is unavailable.",
    incompatible: "The published Composition Playground projection is incompatible with this Site consumer.",
    malformed: "The published Composition Playground projection or Site build provenance is malformed and was rejected.",
    invalidSelection: "The Playground selection in this URL is malformed and was rejected.",
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

  function exactObject(value, name, keys) {
    if (!isObject(value) || Object.keys(value).length !== keys.length || keys.some((key) => !Object.prototype.hasOwnProperty.call(value, key))) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} has an invalid shape`);
    }
    return value;
  }

  function nonEmptyString(value, name) {
    if (typeof value !== "string" || value.length === 0) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must be a non-empty string`);
    }
    return value;
  }

  function integerAtLeast(value, name, minimum = 0) {
    if (!Number.isSafeInteger(value) || value < minimum) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must be an integer >= ${minimum}`);
    }
    return value;
  }

  function relativePath(value, name) {
    if (typeof value !== "string" || !/^(?!\/)(?!.*(?:^|\/)\.\.?(?:\/|$))[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/.test(value)) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must be a safe relative path`);
    }
    return value;
  }

  function materialDestination(value, name) {
    const destination = relativePath(value, name);
    if (destination.split("/").includes(".git")) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must not contain a .git path segment`);
    }
    return destination;
  }

  function componentId(value, name) {
    if (typeof value !== "string" || !/^(foundation|artifact|capability|lifecycle)\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(value)) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must be a valid component id`);
    }
    return value;
  }

  function componentNamespace(value) {
    return value.slice(0, value.indexOf("."));
  }

  function componentIdArray(value, name) {
    const entries = requireUniqueStrings(value, name);
    entries.forEach((entry) => componentId(entry, name));
    return entries;
  }

  function integerArray(value, name) {
    const entries = requireArray(value, name);
    if (entries.some((entry) => !Number.isSafeInteger(entry) || entry < 0)) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must contain non-negative integers`);
    }
    if (new Set(entries).size !== entries.length) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name} must contain unique integers`);
    }
    return entries;
  }

  function errorObject(value, name) {
    exactObject(value, name, ["code", "message"]);
    if (typeof value.code !== "string" || !/^[A-Z][A-Z0-9_]*$/.test(value.code)) {
      throw new ProjectionError("MALFORMED_PROJECTION", `${name}.code is invalid`);
    }
    nonEmptyString(value.message, `${name}.message`);
    return value;
  }

  function validateProjection(raw) {
    exactObject(raw, "projection", [
      "schema_version", "projection_id", "source", "scope", "provenance_reason_bits",
      "recipes", "components", "contracts", "materials", "outcomes"
    ]);
    if (raw.schema_version !== SUPPORTED_SCHEMA_VERSION || raw.projection_id !== PROJECTION_ID) {
      throw new ProjectionError("UNSUPPORTED_PROJECTION", "unsupported Playground projection version");
    }
    exactObject(raw.source, "source", ["repository", "authority", "revision"]);
    if (raw.source.repository !== "TakashiSasaki/templates" || raw.source.authority !== "composition" || !FULL_SHA.test(raw.source.revision || "")) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection semantic source provenance is invalid");
    }
    exactObject(raw.scope, "scope", ["mode", "target", "configuration_schema_version", "components_exclude", "parameters"]);
    if (raw.scope.mode !== "initial" || raw.scope.target !== "empty" || raw.scope.configuration_schema_version !== 1 || JSON.stringify(raw.scope.components_exclude) !== "[]" || JSON.stringify(raw.scope.parameters) !== "{}") {
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
    if (!recipes.length || !components.length || !outcomes.length) {
      throw new ProjectionError("MALFORMED_PROJECTION", "projection inventories are empty");
    }

    const recipeById = new Map();
    const componentById = new Map();
    const contractById = new Map();
    const materialById = new Map();
    const outcomeById = new Map();

    for (const component of components) {
      exactObject(component, "component", ["id", "role", "version", "summary", "requires", "conflicts", "contract_ids", "material_declarations", "source_path"]);
      const id = componentId(component.id, "component.id");
      const namespace = componentNamespace(id);
      if (!COMPONENT_ROLES.includes(component.role) || namespace !== component.role || componentById.has(id)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "component inventory has an invalid or mismatched role namespace");
      }
      integerAtLeast(component.version, `component ${id}.version`, 1);
      nonEmptyString(component.summary, `component ${id}.summary`);
      componentIdArray(component.requires, `component ${id}.requires`);
      componentIdArray(component.conflicts, `component ${id}.conflicts`);
      integerArray(component.contract_ids, `component ${id}.contract_ids`);
      if (!Array.isArray(component.material_declarations) || component.material_declarations.some((entry) => !isObject(entry))) {
        throw new ProjectionError("MALFORMED_PROJECTION", `component ${id}.material_declarations is invalid`);
      }
      for (const declaration of component.material_declarations) {
        if (typeof declaration.destination === "string") {
          materialDestination(declaration.destination, `component ${id}.material_declarations.destination`);
        }
      }
      relativePath(component.source_path, `component ${id}.source_path`);
      componentById.set(id, component);
    }

    for (const contract of contracts) {
      exactObject(contract, "contract", ["index", "component", "id", "document", "schema", "document_schema_version", "purpose"]);
      const index = integerAtLeast(contract.index, "contract.index");
      if (contractById.has(index)) throw new ProjectionError("MALFORMED_PROJECTION", "contract inventory is invalid or duplicated");
      componentId(contract.component, `contract ${index}.component`);
      nonEmptyString(contract.id, `contract ${index}.id`);
      relativePath(contract.document, `contract ${index}.document`);
      relativePath(contract.schema, `contract ${index}.schema`);
      integerAtLeast(contract.document_schema_version, `contract ${index}.document_schema_version`, 1);
      nonEmptyString(contract.purpose, `contract ${index}.purpose`);
      contractById.set(index, contract);
    }

    for (const material of materials) {
      exactObject(material, "material", ["index", "component", "destination", "ownership", "sha256"]);
      const index = integerAtLeast(material.index, "material.index");
      if (materialById.has(index)) throw new ProjectionError("MALFORMED_PROJECTION", "material inventory is invalid or duplicated");
      componentId(material.component, `material ${index}.component`);
      materialDestination(material.destination, `material ${index}.destination`);
      if (!["managed", "generated", "seed"].includes(material.ownership) || !/^[0-9a-f]{64}$/.test(material.sha256 || "")) {
        throw new ProjectionError("MALFORMED_PROJECTION", `material ${index} is invalid`);
      }
      materialById.set(index, material);
    }

    for (const outcome of outcomes) {
      exactObject(outcome, "outcome", ["index", "resolved_components", "dependency_edges", "contract_ids", "material_ids", "initial_plan"]);
      const index = integerAtLeast(outcome.index, "outcome.index");
      if (outcomeById.has(index)) throw new ProjectionError("MALFORMED_PROJECTION", "outcome inventory is invalid or duplicated");
      const resolved = componentIdArray(outcome.resolved_components, `outcome ${index}.resolved_components`);
      const edges = requireArray(outcome.dependency_edges, `outcome ${index}.dependency_edges`);
      const seenEdges = new Set();
      for (const edge of edges) {
        if (!Array.isArray(edge) || edge.length !== 2 || edge.some((position) => !Number.isSafeInteger(position) || position < 0 || position >= resolved.length)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${index} has an invalid dependency edge`);
        }
        const key = JSON.stringify(edge);
        if (seenEdges.has(key)) throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${index} has duplicate dependency edges`);
        seenEdges.add(key);
      }
      integerArray(outcome.contract_ids, `outcome ${index}.contract_ids`);
      integerArray(outcome.material_ids, `outcome ${index}.material_ids`);
      exactObject(outcome.initial_plan, `outcome ${index}.initial_plan`, ["action_counts", "conflict_count"]);
      if (!isObject(outcome.initial_plan.action_counts) || Object.entries(outcome.initial_plan.action_counts).some(([action, count]) => !action || !Number.isSafeInteger(count) || count < 0) || outcome.initial_plan.conflict_count !== 0) {
        throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${index} has an invalid initial plan`);
      }
      outcomeById.set(index, outcome);
    }

    for (const component of components) {
      for (const dependency of [...component.requires, ...component.conflicts]) {
        if (!componentById.has(dependency)) throw new ProjectionError("MALFORMED_PROJECTION", `component ${component.id} references an unknown component`);
      }
      for (const id of component.contract_ids) {
        const contract = contractById.get(id);
        if (!contract) throw new ProjectionError("MALFORMED_PROJECTION", `component ${component.id} references an unknown contract`);
        if (contract.component !== component.id) {
          throw new ProjectionError("MALFORMED_PROJECTION", `component ${component.id} advertises a contract owned by ${contract.component}`);
        }
      }
    }

    for (const contract of contracts) {
      const owner = componentById.get(contract.component);
      if (!owner) throw new ProjectionError("MALFORMED_PROJECTION", `contract ${contract.index} references an unknown component`);
      if (!owner.contract_ids.includes(contract.index)) {
        throw new ProjectionError("MALFORMED_PROJECTION", `contract ${contract.index} is not registered by its owning component`);
      }
    }

    for (const material of materials) {
      if (!componentById.has(material.component)) throw new ProjectionError("MALFORMED_PROJECTION", `material ${material.index} references an unknown component`);
    }

    for (const outcome of outcomes) {
      const resolvedSet = new Set(outcome.resolved_components);
      const positionByComponent = new Map(outcome.resolved_components.map((id, position) => [id, position]));
      const edgeSet = new Set(outcome.dependency_edges.map((edge) => JSON.stringify(edge)));

      for (const componentIdValue of outcome.resolved_components) {
        if (!componentById.has(componentIdValue)) throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} references an unknown component`);
      }

      for (const componentIdValue of outcome.resolved_components) {
        const component = componentById.get(componentIdValue);
        for (const conflictId of component.conflicts) {
          if (resolvedSet.has(conflictId)) {
            throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} contains conflicting components ${componentIdValue} and ${conflictId}`);
          }
        }
      }

      for (const edge of outcome.dependency_edges) {
        const sourceId = outcome.resolved_components[edge[0]];
        const targetId = outcome.resolved_components[edge[1]];
        const source = componentById.get(sourceId);
        if (!source || !source.requires.includes(targetId)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} dependency edge disagrees with component metadata`);
        }
      }

      outcome.resolved_components.forEach((sourceId, sourceIndex) => {
        const source = componentById.get(sourceId);
        for (const targetId of source.requires) {
          if (!resolvedSet.has(targetId)) {
            throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} omits required component ${targetId}`);
          }
          const targetIndex = positionByComponent.get(targetId);
          if (!edgeSet.has(JSON.stringify([sourceIndex, targetIndex]))) {
            throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} omits a required dependency edge`);
          }
        }
      });

      for (const contractId of outcome.contract_ids) {
        const contract = contractById.get(contractId);
        if (!contract) throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} references an unknown contract`);
        const owner = componentById.get(contract.component);
        if (!resolvedSet.has(contract.component) || !owner || !owner.contract_ids.includes(contractId)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} has inconsistent contract ownership`);
        }
      }
      const expectedContracts = new Set(
        outcome.resolved_components.flatMap((componentIdValue) => componentById.get(componentIdValue).contract_ids)
      );
      if (expectedContracts.size !== outcome.contract_ids.length || outcome.contract_ids.some((contractId) => !expectedContracts.has(contractId))) {
        throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} contract registrations are incomplete or extraneous`);
      }

      const materialDestinations = new Set();
      for (const materialId of outcome.material_ids) {
        const material = materialById.get(materialId);
        if (!material) throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} references an unknown material`);
        if (!resolvedSet.has(material.component)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} has material owned by an unresolved component`);
        }
        for (const destination of materialDestinations) {
          if (material.destination.startsWith(`${destination}/`) || destination.startsWith(`${material.destination}/`)) {
            throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} has ancestor/descendant material destinations`);
          }
        }
        if (materialDestinations.has(material.destination)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} has duplicate material destinations`);
        }
        materialDestinations.add(material.destination);
      }
      const materialSlot = (componentIdValue, destination) => `${componentIdValue}\u0000${destination}`;
      const expectedMaterialSlots = new Set(
        materials
          .filter((material) => resolvedSet.has(material.component))
          .map((material) => materialSlot(material.component, material.destination))
      );
      for (const componentIdValue of outcome.resolved_components) {
        const declarations = componentById.get(componentIdValue).material_declarations;
        for (const declaration of declarations) {
          if (isObject(declaration) && typeof declaration.destination === "string") {
            expectedMaterialSlots.add(materialSlot(componentIdValue, declaration.destination));
          }
        }
      }
      const listedMaterialSlots = new Set(
        outcome.material_ids.map((materialId) => {
          const material = materialById.get(materialId);
          return materialSlot(material.component, material.destination);
        })
      );
      if (expectedMaterialSlots.size !== listedMaterialSlots.size || Array.from(expectedMaterialSlots).some((slot) => !listedMaterialSlots.has(slot))) {
        throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} material projection is incomplete, extraneous, or assigned to the wrong owner`);
      }
      const actionCounts = outcome.initial_plan.action_counts;
      if (Object.keys(actionCounts).length !== 1 || actionCounts.create !== outcome.material_ids.length) {
        throw new ProjectionError("MALFORMED_PROJECTION", `outcome ${outcome.index} initial plan does not match its projected materials`);
      }
    }

    for (const recipe of recipes) {
      exactObject(recipe, "recipe", ["id", "artifact", "required_components", "default_components", "optional_components", "case_count", "source_path", "cases"]);
      if (typeof recipe.id !== "string" || recipe.id.length === 0 || recipeById.has(recipe.id)) {
        throw new ProjectionError("MALFORMED_PROJECTION", "recipe inventory is invalid or duplicated");
      }
      componentId(recipe.artifact, `recipe ${recipe.id}.artifact`);
      const required = componentIdArray(recipe.required_components, `recipe ${recipe.id}.required_components`);
      const defaults = componentIdArray(recipe.default_components, `recipe ${recipe.id}.default_components`);
      const optionals = componentIdArray(recipe.optional_components, `recipe ${recipe.id}.optional_components`);
      relativePath(recipe.source_path, `recipe ${recipe.id}.source_path`);

      const artifact = componentById.get(recipe.artifact);
      if (!artifact || artifact.role !== "artifact") {
        throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} artifact is not an artifact component`);
      }
      for (const id of [...required, ...defaults, ...optionals]) {
        if (!componentById.has(id)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} references an unknown component`);
        }
      }

      const cases = requireArray(recipe.cases, `recipe ${recipe.id} cases`);
      const expectedCaseCount = 2 ** optionals.length;
      if (!Number.isSafeInteger(expectedCaseCount) || !Number.isSafeInteger(recipe.case_count) || recipe.case_count !== expectedCaseCount || cases.length !== expectedCaseCount) {
        throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} case table does not cover its optional-component domain`);
      }
      const requiredComponents = new Set(required);
      const defaultComponents = new Set(defaults);
      for (let mask = 0; mask < cases.length; mask += 1) {
        const item = cases[mask];
        exactObject(item, `recipe ${recipe.id} case ${mask}`, ["valid", "error", "outcome_id", "selection_reason_masks"]);
        if (typeof item.valid !== "boolean" || !Array.isArray(item.selection_reason_masks)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} case ${mask} is malformed`);
        }
        if (item.selection_reason_masks.some((reasonMask) => !Number.isSafeInteger(reasonMask) || reasonMask < 1 || reasonMask > 31)) {
          throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} case ${mask} has invalid selection provenance`);
        }
        if (item.valid) {
          const outcome = outcomeById.get(item.outcome_id);
          if (item.error !== null || !outcome || item.selection_reason_masks.length !== outcome.resolved_components.length) {
            throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} valid case ${mask} is inconsistent with its outcome`);
          }
          const explicitComponents = new Set(optionals.filter((_componentIdValue, position) => (mask & (2 ** position)) !== 0));
          const resolvedSet = new Set(outcome.resolved_components);
          const directlySelected = new Set([
            recipe.artifact,
            ...required,
            ...defaults,
            ...explicitComponents
          ]);
          for (const expectedComponent of directlySelected) {
            if (!resolvedSet.has(expectedComponent)) {
              throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} case ${mask} omits a directly selected component from its outcome`);
            }
          }

          const positionByComponent = new Map(
            outcome.resolved_components.map((componentIdValue, componentIndex) => [componentIdValue, componentIndex])
          );
          const outgoingDependencies = new Map();
          for (const [sourceIndex, targetIndex] of outcome.dependency_edges) {
            if (!outgoingDependencies.has(sourceIndex)) outgoingDependencies.set(sourceIndex, []);
            outgoingDependencies.get(sourceIndex).push(targetIndex);
          }
          const reachable = new Set(Array.from(directlySelected, (componentIdValue) => positionByComponent.get(componentIdValue)));
          const pending = Array.from(reachable);
          while (pending.length) {
            const sourceIndex = pending.pop();
            for (const targetIndex of outgoingDependencies.get(sourceIndex) || []) {
              if (reachable.has(targetIndex)) continue;
              reachable.add(targetIndex);
              pending.push(targetIndex);
            }
          }
          if (reachable.size !== outcome.resolved_components.length) {
            throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} case ${mask} has a resolved component that is not reachable from a directly selected root`);
          }

          const dependencyTargets = new Set(outcome.dependency_edges.map((edge) => edge[1]));
          item.selection_reason_masks.forEach((reasonMask, componentIndex) => {
            const componentIdValue = outcome.resolved_components[componentIndex];
            let expectedMask = 0;
            if (componentIdValue === recipe.artifact) expectedMask |= raw.provenance_reason_bits.recipe_artifact;
            if (requiredComponents.has(componentIdValue)) expectedMask |= raw.provenance_reason_bits.recipe_required;
            if (defaultComponents.has(componentIdValue)) expectedMask |= raw.provenance_reason_bits.recipe_default;
            if (explicitComponents.has(componentIdValue)) expectedMask |= raw.provenance_reason_bits.explicit_include;
            if (dependencyTargets.has(componentIndex)) expectedMask |= raw.provenance_reason_bits.dependency;
            if (reasonMask !== expectedMask) {
              throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} case ${mask} has inconsistent selection provenance`);
            }
          });
        } else if (item.outcome_id !== null || !isObject(item.error) || item.selection_reason_masks.length !== 0) {
          throw new ProjectionError("MALFORMED_PROJECTION", `recipe ${recipe.id} invalid case ${mask} is inconsistent`);
        } else {
          errorObject(item.error, `recipe ${recipe.id} case ${mask}.error`);
        }
      }
      recipeById.set(recipe.id, recipe);
    }
    if (recipeById.size === 0) throw new ProjectionError("MALFORMED_PROJECTION", "projection has no recipes");

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
    const topKeys = ["schema_version", "repository", "site_commit", "publication_commits"];
    if (!isObject(raw) || Object.keys(raw).length !== topKeys.length || topKeys.some((key) => !Object.prototype.hasOwnProperty.call(raw, key))) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site build provenance has an unsupported top-level shape");
    }
    if (raw.schema_version !== BUILD_PROVENANCE_SCHEMA_VERSION || raw.repository !== "TakashiSasaki/templates" || !FULL_SHA.test(raw.site_commit || "")) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site build provenance identity is invalid");
    }
    if (!isObject(raw.publication_commits)) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site build provenance publication_commits is invalid");
    }
    const providerKeys = Object.keys(raw.publication_commits);
    if (providerKeys.length !== 2 || !providerKeys.includes("composition") || !providerKeys.includes("policy")) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site build provenance provider set must be exactly composition and policy");
    }
    const providerRevision = raw.publication_commits.composition;
    const policyRevision = raw.publication_commits.policy;
    if (!FULL_SHA.test(providerRevision || "") || !FULL_SHA.test(policyRevision || "")) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site build provenance provider revisions must be exact lowercase SHAs");
    }
    return Object.freeze({
      raw,
      siteRevision: raw.site_commit,
      providerRevision,
      policyRevision
    });
  }

  function readDocumentSiteRevision(document) {
    if (!document || typeof document.querySelector !== "function") {
      throw new ProjectionError("MALFORMED_PROVENANCE", "loaded Site document has no revision metadata");
    }
    const revisionMeta = document.querySelector('meta[name="templates-site-revision"]');
    if (!revisionMeta) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "loaded Site document revision metadata is missing");
    }
    const value = typeof revisionMeta.getAttribute === "function"
      ? revisionMeta.getAttribute("content")
      : revisionMeta.content;
    const documentRevision = typeof value === "string" ? value.trim() : "";
    if (!FULL_SHA.test(documentRevision)) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site document revision metadata is invalid");
    }
    return documentRevision;
  }

  function validateDocumentBuildProvenance(document, provenance) {
    if (!isObject(provenance) || !FULL_SHA.test(provenance.siteRevision || "")) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "validated Site build provenance is required");
    }
    const documentRevision = readDocumentSiteRevision(document);
    if (documentRevision !== provenance.siteRevision) {
      throw new ProjectionError("MALFORMED_PROVENANCE", "Site document revision does not match build provenance");
    }
    return provenance;
  }

  function selectionMask(recipe, includes) {
    if (!isObject(recipe) || typeof recipe.id !== "string") {
      throw new ProjectionError("INVALID_SELECTION", "recipe is missing from the projection inventory");
    }
    const optionals = requireUniqueStrings(recipe.optional_components, `recipe ${recipe.id} optional_components`);
    const selected = requireUniqueStrings(Array.from(includes || []), "explicit includes");
    const index = new Map(optionals.map((componentIdValue, position) => [componentIdValue, position]));
    let mask = 0;
    for (const componentIdValue of selected) {
      if (!index.has(componentIdValue)) {
        throw new ProjectionError("INVALID_SELECTION", `component ${componentIdValue} is not exposed by recipe ${recipe.id}`);
      }
      mask += 2 ** index.get(componentIdValue);
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

  function defaultSelection(projection) {
    return { recipeId: projection.recipes[0].id, includes: [] };
  }

  function parseHashWithOwnership(hash, projection) {
    const text = typeof hash === "string" ? hash.replace(/^#/, "") : "";
    if (text === "") {
      return { kind: "empty", state: defaultSelection(projection) };
    }
    const params = new URLSearchParams(text);
    if (!params.has("recipe")) {
      return { kind: "document", state: defaultSelection(projection) };
    }
    const keys = Array.from(params.keys());
    const recipeValues = params.getAll("recipe");
    if (recipeValues.length !== 1 || !recipeValues[0] || keys.some((key) => key !== "recipe" && key !== "include")) {
      throw new ProjectionError("INVALID_SELECTION", "Playground URL hash is not a canonical selection-state shape");
    }
    const recipeId = recipeValues[0];
    const recipe = projection.recipeById.get(recipeId);
    if (!recipe) {
      throw new ProjectionError("INVALID_SELECTION", `unknown recipe in URL hash: ${recipeId}`);
    }
    const includes = params.getAll("include");
    selectionMask(recipe, includes);
    return { kind: "playground", state: { recipeId, includes: includes.slice().sort() } };
  }

  function parseHash(hash, projection) {
    return parseHashWithOwnership(hash, projection).state;
  }

  function stateHash(recipeId, includes) {
    const params = new URLSearchParams();
    params.set("recipe", recipeId);
    for (const componentIdValue of Array.from(includes || []).slice().sort()) {
      params.append("include", componentIdValue);
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
    const renderedOptionals = new Map();
    for (const componentIdValue of recipe.optional_components) {
      const label = document.createElement("label");
      label.className = "composition-playground__option";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = componentIdValue;
      checkbox.checked = selected.has(componentIdValue);
      checkbox.addEventListener("change", () => onChange(componentIdValue));
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(` ${componentIdValue}`));
      nodes.optionals.appendChild(label);
      renderedOptionals.set(componentIdValue, checkbox);
    }
    return renderedOptionals;
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
      for (const componentIdValue of item.resolved_components) {
        nodes.resolved.appendChild(textNode(document, "li", componentIdValue));
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
    return validateProjection(await decodeProjectionResponse(response, url));
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
      if (error.code === "INVALID_SELECTION") return labels.invalidSelection;
      return `${labels.malformed} ${error.message}`;
    }
    return labels.malformed;
  }

  let runtimeState = {
    root: null,
    promise: null,
    context: null,
    error: null,
    listeners: new Set()
  };
  let hashListenerBound = false;
  let activeHashHandler = null;

  function notify(event) {
    for (const listener of runtimeState.listeners) {
      try {
        listener(event);
      } catch (error) {
        if (scope.console && typeof scope.console.warn === "function") {
          scope.console.warn("Composition Playground subscriber failed", error);
        }
      }
    }
  }

  function subscribe(listener) {
    if (typeof listener !== "function") throw new TypeError("Composition Playground subscriber must be a function");
    runtimeState.listeners.add(listener);
    if (runtimeState.context) {
      const context = runtimeState.context;
      Promise.resolve().then(() => {
        if (runtimeState.context === context) listener({ type: "ready", context });
      });
    } else if (runtimeState.error && runtimeState.root) {
      const root = runtimeState.root;
      const error = runtimeState.error;
      Promise.resolve().then(() => {
        if (runtimeState.root === root && runtimeState.error === error) listener({ type: "error", root, error });
      });
    }
    return () => runtimeState.listeners.delete(listener);
  }

  function bindHashListener() {
    if (scope.addEventListener && !hashListenerBound) {
      scope.addEventListener("hashchange", () => {
        if (activeHashHandler) activeHashHandler();
      });
      hashListenerBound = true;
    }
  }

  function isRetryableAvailabilityError(error) {
    return error instanceof ProjectionError && (
      error.code === "PROJECTION_UNAVAILABLE" || error.code === "PROVENANCE_UNAVAILABLE"
    );
  }

  async function mountRoot(document, root, current) {
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
    root.dataset.playgroundMounted = "true";
    status.textContent = labels.loading;

    try {
      const [projection, loadedProvenance] = await Promise.all([
        loadProjection(root.dataset.projectionUrl),
        loadBuildProvenance(root.dataset.provenanceUrl || "/build-provenance.json")
      ]);
      const provenance = validateDocumentBuildProvenance(document, loadedProvenance);
      if (runtimeState !== current || root.isConnected === false) return null;
      current.error = null;
      runtimeState.error = null;

      let initialHash;
      let initialHashError = null;
      try {
        initialHash = parseHashWithOwnership(scope.location ? scope.location.hash : "", projection);
      } catch (error) {
        initialHashError = error;
        initialHash = { kind: "playground", state: defaultSelection(projection) };
      }
      let state = initialHash.state;
      let currentCase = null;
      let copyAttemptGeneration = 0;

      const updateContext = () => {
        currentCase = lookupCase(projection, state.recipeId, state.includes);
        current.context = Object.freeze({
          document,
          root,
          projection,
          provenance,
          state: { recipeId: state.recipeId, includes: state.includes.slice() },
          currentCase
        });
        runtimeState.context = current.context;
        notify({ type: "selection", context: current.context });
      };

      const readControlState = () => ({
        recipeId: nodes.recipe.value,
        includes: Array.from(nodes.optionals.querySelectorAll("input[type=checkbox]:checked"), (node) => node.value)
      });

      const clearRuntimeError = () => {
        delete root.dataset.playgroundError;
        current.error = null;
        runtimeState.error = null;
      };

      const failClosed = (error) => {
        app.hidden = true;
        status.textContent = statusForError(error);
        root.dataset.playgroundError = error instanceof ProjectionError ? error.code : "UNKNOWN";
        current.context = null;
        current.error = error;
        runtimeState.context = null;
        runtimeState.error = error;
        notify({ type: "error", root, error });
      };

      const apply = (nextState, hashMode, focusComponentId = null) => {
        if (runtimeState !== current || root.isConnected === false) return;
        state = nextState;
        clearRuntimeError();
        const renderedOptionals = renderSelection(
          document,
          nodes,
          projection,
          state,
          (componentIdValue) => apply(readControlState(), "push", componentIdValue)
        );
        updateContext();
        renderCase(document, nodes, projection, provenance, currentCase);
        if (hashMode !== "preserve" && scope.history && scope.location) {
          const nextHash = stateHash(state.recipeId, state.includes);
          const url = `${scope.location.pathname}${scope.location.search}${nextHash}`;
          if (hashMode === "replace") scope.history.replaceState(null, "", url);
          else scope.history.pushState(null, "", url);
        }
        app.hidden = false;
        status.textContent = labels.loaded;
        if (focusComponentId) {
          const focusTarget = renderedOptionals.get(focusComponentId);
          if (focusTarget && typeof focusTarget.focus === "function") focusTarget.focus();
        }
      };

      nodes.recipe.addEventListener("change", () => apply({ recipeId: nodes.recipe.value, includes: [] }, "push"));
      nodes.copy.addEventListener("click", async () => {
        const initiatingContext = current.context;
        const initiatingCase = currentCase;
        const initiatingCopyAttempt = ++copyAttemptGeneration;
        const text = configurationText(initiatingCase);
        const isStillCurrent = () => (
          runtimeState === current &&
          root.isConnected !== false &&
          current.context === initiatingContext &&
          runtimeState.context === initiatingContext &&
          currentCase === initiatingCase &&
          copyAttemptGeneration === initiatingCopyAttempt
        );
        try {
          await scope.navigator.clipboard.writeText(text);
          if (isStillCurrent()) status.textContent = labels.copied;
        } catch (_error) {
          if (isStillCurrent()) status.textContent = labels.copyFailed;
        }
      });

      activeHashHandler = () => {
        if (runtimeState !== current || root.isConnected === false) return;
        try {
          const parsed = parseHashWithOwnership(scope.location ? scope.location.hash : "", projection);
          if (parsed.kind === "document") {
            if (current.error) apply(state, "preserve");
            return;
          }
          apply(parsed.state, "replace");
        } catch (error) {
          failClosed(error);
        }
      };
      bindHashListener();

      if (initialHashError) {
        failClosed(initialHashError);
        return null;
      }
      apply(state, initialHash.kind === "document" ? "preserve" : "replace");
      notify({ type: "ready", context: current.context });
      return current.context;
    } catch (error) {
      if (runtimeState !== current || root.isConnected === false) return null;
      app.hidden = true;
      status.textContent = statusForError(error);
      root.dataset.playgroundError = error instanceof ProjectionError ? error.code : "UNKNOWN";
      current.context = null;
      current.error = error;
      runtimeState.context = null;
      runtimeState.error = error;
      notify({ type: "error", root, error });
      return null;
    }
  }

  function startMount(document, root, current) {
    const mountPromise = mountRoot(document, root, current);
    current.promise = mountPromise;
    void mountPromise.finally(() => {
      if (runtimeState === current && current.promise === mountPromise) current.promise = null;
    });
    return mountPromise;
  }

  function ensureMounted(document) {
    const root = document && document.getElementById("composition-playground");
    if (!root) {
      if (runtimeState.root) {
        const previousRoot = runtimeState.root;
        const listeners = runtimeState.listeners;
        runtimeState = { root: null, promise: null, context: null, error: null, listeners };
        activeHashHandler = null;
        notify({ type: "unmounted", root: previousRoot });
      }
      return Promise.resolve(null);
    }
    if (runtimeState.root === root) {
      if (runtimeState.promise) return runtimeState.promise;
      if (runtimeState.context) return Promise.resolve(runtimeState.context);
      if (isRetryableAvailabilityError(runtimeState.error)) {
        const listeners = runtimeState.listeners;
        const current = { root, promise: null, context: null, error: null, listeners };
        runtimeState = current;
        activeHashHandler = null;
        return startMount(document, root, current);
      }
      return Promise.resolve(null);
    }

    const previousRoot = runtimeState.root;
    const listeners = runtimeState.listeners;
    if (previousRoot) {
      runtimeState = { root: null, promise: null, context: null, error: null, listeners };
      activeHashHandler = null;
      notify({ type: "unmounted", root: previousRoot });
    }
    const current = { root, promise: null, context: null, error: null, listeners };
    runtimeState = current;
    return startMount(document, root, current);
  }

  function mount(document) {
    return ensureMounted(document);
  }

  return Object.freeze({
    SUPPORTED_SCHEMA_VERSION,
    BUILD_PROVENANCE_SCHEMA_VERSION,
    EXPECTED_REASON_BITS,
    ProjectionError,
    labels,
    validateProjection,
    validateBuildProvenance,
    validateDocumentBuildProvenance,
    readDocumentSiteRevision,
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
    isRetryableAvailabilityError,
    ensureMounted,
    subscribe,
    mount
  });
});
