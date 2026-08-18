from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
LOCK_DESTINATION = ".template-composition/lock.json"
SCHEMAS = {
    "component": ROOT / "schemas" / "component.schema.json",
    "recipe": ROOT / "schemas" / "recipe.schema.json",
    "config": ROOT / "schemas" / "composition-config.schema.json",
    "lock": ROOT / "schemas" / "composition-lock.schema.json",
}
EXAMPLES = {
    "component": ROOT / "examples" / "component.mcp.json",
    "recipe": ROOT / "examples" / "recipe.webapp.json",
    "config": ROOT / "examples" / "composition-config.webapp-mcp.json",
    "lock": ROOT / "examples" / "composition-lock.webapp-mcp.json",
}


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def normalized_path(path: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in path.split("/"))


def validate_portable_path(path: str) -> None:
    if any(part == ".git" for part in normalized_path(path)):
        raise ValueError(f"path must not traverse Git administration data: {path!r}")


def validate_portable_destinations(destinations: list[str]) -> None:
    lock_path = normalized_path(LOCK_DESTINATION)
    normalized = [(destination, normalized_path(destination)) for destination in destinations]
    for destination, path in normalized:
        validate_portable_path(destination)
        if path == lock_path[: len(path)] or lock_path == path[: len(lock_path)]:
            raise ValueError(f"materialized destination conflicts with reserved lock path: {destination!r}")
    for index, (left_text, left) in enumerate(normalized):
        for right_text, right in normalized[index + 1 :]:
            if left == right:
                raise ValueError(f"materialized destinations collide case-insensitively: {left_text!r}, {right_text!r}")
            if left == right[: len(left)] or right == left[: len(right)]:
                raise ValueError(f"materialized file/directory destinations conflict: {left_text!r}, {right_text!r}")


def validate_component_semantics(value: dict) -> None:
    component_id = value["id"]
    required = set(value["requires"])
    conflicts = set(value["conflicts"])
    if component_id in required:
        raise ValueError("component must not require itself")
    if component_id in conflicts:
        raise ValueError("component must not conflict with itself")
    overlap = required & conflicts
    if overlap:
        raise ValueError(f"required/conflicting component overlap: {sorted(overlap)}")
    if value["kind"] != "artifact":
        artifact_relations = sorted(relation for relation in required | conflicts if relation.startswith("artifact."))
        if artifact_relations:
            raise ValueError(f"capability/lifecycle components must not depend on or conflict with artifact components: {artifact_relations}")
    for material in value["materials"]:
        if "source" in material:
            validate_portable_path(material["source"])
    validate_portable_destinations([item["destination"] for item in value["materials"]])


def validate_recipe_semantics(value: dict) -> None:
    groups = [set(value["required_components"]), set(value["default_components"]), set(value["optional_components"])]
    for left_index, left in enumerate(groups):
        for right in groups[left_index + 1 :]:
            if left & right:
                raise ValueError("recipe component selection classes must be disjoint")


def validate_config_semantics(value: dict) -> None:
    include = set(value["components"]["include"])
    exclude = set(value["components"]["exclude"])
    if include & exclude:
        raise ValueError("configuration include/exclude sets must be disjoint")


def validate_lock_semantics(value: dict) -> None:
    component_ids = [item["id"] for item in value["resolved_components"]]
    if len(component_ids) != len(set(component_ids)):
        raise ValueError("lock resolved component IDs must be unique")
    if component_ids != sorted(component_ids):
        raise ValueError("lock resolved component IDs must be lexically ordered")
    artifact_ids = [component_id for component_id in component_ids if component_id.startswith("artifact.")]
    if len(artifact_ids) != 1:
        raise ValueError("lock must resolve exactly one artifact component")
    resolved = set(component_ids)
    destinations = [item["destination"] for item in value["files"]]
    if destinations != sorted(destinations):
        raise ValueError("lock file destinations must be lexically ordered")
    validate_portable_destinations(destinations)
    owners = {item["component"] for item in value["files"]}
    unknown_owners = sorted(owners - resolved)
    if unknown_owners:
        raise ValueError(f"lock file owner is not resolved: {unknown_owners}")
    missing_owners = sorted(resolved - owners)
    if missing_owners:
        raise ValueError(f"resolved component owns no materialized file: {missing_owners}")


SEMANTIC_VALIDATORS = {"component": validate_component_semantics, "recipe": validate_recipe_semantics, "config": validate_config_semantics, "lock": validate_lock_semantics}


class CompositionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = {name: load(path) for name, path in SCHEMAS.items()}
        cls.examples = {name: load(path) for name, path in EXAMPLES.items()}
        for schema in cls.schemas.values():
            Draft202012Validator.check_schema(schema)

    def assert_schema_valid(self, name: str, value: dict) -> None:
        Draft202012Validator(self.schemas[name]).validate(value)
        SEMANTIC_VALIDATORS[name](value)

    def test_positive_examples_are_valid(self) -> None:
        for name, value in self.examples.items():
            with self.subTest(name=name):
                self.assert_schema_valid(name, value)

    def test_component_kind_must_match_id_namespace(self) -> None:
        value = copy.deepcopy(self.examples["component"]); value["kind"] = "artifact"
        with self.assertRaises(ValidationError): self.assert_schema_valid("component", value)

    def test_generic_component_cannot_reference_artifact_component(self) -> None:
        for field in ("requires", "conflicts"):
            value = copy.deepcopy(self.examples["component"]); value[field].append("artifact.webapp-core")
            with self.subTest(field=field):
                with self.assertRaises(ValueError): self.assert_schema_valid("component", value)

    def test_component_rejects_unsafe_destination(self) -> None:
        for destination in ("../outside", "/absolute", "C:/windows", "a/../b", ".git/config", ".Git/config", "sub/.GIT/hooks/pre-commit", "contracts/", "-option/file", "contracts/-option", LOCK_DESTINATION):
            value = copy.deepcopy(self.examples["component"]); value["materials"][0]["destination"] = destination
            with self.subTest(destination=destination):
                with self.assertRaises((ValidationError, ValueError)): self.assert_schema_valid("component", value)

    def test_component_rejects_reserved_lock_path_structural_conflicts(self) -> None:
        for destination in (".Template-Composition/LOCK.json", ".template-composition", ".template-composition/lock.json/nested", ".TEMPLATE-COMPOSITION/LOCK.JSON/nested"):
            value = copy.deepcopy(self.examples["component"]); value["materials"][0]["destination"] = destination
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError): self.assert_schema_valid("component", value)

    def test_component_rejects_unsafe_source(self) -> None:
        for source in ("../outside", "/absolute", "C:/windows", "a/../b", ".git/config", ".Git/config", "sub/.GIT/hooks/pre-commit", "contracts/", "-option/file"):
            value = copy.deepcopy(self.examples["component"]); value["materials"][0]["source"] = source
            with self.subTest(source=source):
                with self.assertRaises((ValidationError, ValueError)): self.assert_schema_valid("component", value)

    def test_component_rejects_self_dependency(self) -> None:
        value = copy.deepcopy(self.examples["component"]); value["requires"].append(value["id"])
        with self.assertRaises(ValueError): self.assert_schema_valid("component", value)

    def test_component_rejects_required_conflict_overlap(self) -> None:
        value = copy.deepcopy(self.examples["component"]); value["conflicts"].append(value["requires"][0])
        with self.assertRaises(ValueError): self.assert_schema_valid("component", value)

    def test_component_rejects_portability_destination_collisions(self) -> None:
        for destination in ("Contracts/interfaces/mcp.md", "contracts"):
            value = copy.deepcopy(self.examples["component"]); value["materials"][1]["destination"] = destination
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError): self.assert_schema_valid("component", value)

    def test_copied_material_requires_source(self) -> None:
        value = copy.deepcopy(self.examples["component"]); del value["materials"][0]["source"]
        with self.assertRaises(ValidationError): self.assert_schema_valid("component", value)

    def test_generated_material_requires_generator_and_has_no_source(self) -> None:
        value = copy.deepcopy(self.examples["component"])
        value["materials"][0] = {"destination": ".template-composition/registry.json", "ownership": "generated", "generator": "contract-manifest-v1"}
        self.assert_schema_valid("component", value)
        del value["materials"][0]["generator"]
        with self.assertRaises(ValidationError): self.assert_schema_valid("component", value)
        value["materials"][0]["generator"] = "contract-manifest-v1"
        value["materials"][0]["source"] = "registry-source.json"
        with self.assertRaises(ValidationError): self.assert_schema_valid("component", value)

    def test_descriptors_cannot_add_execution_hooks(self) -> None:
        for field in ("hooks", "commands", "post_install", "executable"):
            value = copy.deepcopy(self.examples["component"]); value[field] = ["echo unsafe"]
            with self.subTest(field=field):
                with self.assertRaises(ValidationError): self.assert_schema_valid("component", value)

    def test_config_rejects_include_exclude_overlap(self) -> None:
        value = copy.deepcopy(self.examples["config"]); value["components"]["exclude"] = [value["components"]["include"][0]]
        with self.assertRaises(ValueError): self.assert_schema_valid("config", value)

    def test_config_cannot_select_artifact_component(self) -> None:
        for field in ("include", "exclude"):
            value = copy.deepcopy(self.examples["config"]); value["components"][field].append("artifact.skill-core")
            with self.subTest(field=field):
                with self.assertRaises(ValidationError): self.assert_schema_valid("config", value)

    def test_recipe_rejects_selection_class_overlap(self) -> None:
        value = copy.deepcopy(self.examples["recipe"]); value["optional_components"].append(value["default_components"][0])
        with self.assertRaises(ValueError): self.assert_schema_valid("recipe", value)

    def test_lock_requires_full_lowercase_revision(self) -> None:
        for revision in ("abc123", "A" * 40, "0" * 40):
            value = copy.deepcopy(self.examples["lock"]); value["source"]["revision"] = revision
            with self.subTest(revision=revision):
                with self.assertRaises(ValidationError): self.assert_schema_valid("lock", value)

    def test_lock_requires_canonical_source_repository(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); value["source"]["repository"] = "other/repository"
        with self.assertRaises(ValidationError): self.assert_schema_valid("lock", value)

    def test_lock_requires_lowercase_full_sha256_fields(self) -> None:
        mutations = [("configuration_sha256", None), ("resolved_components", "descriptor_sha256"), ("files", "materialized_sha256")]
        for collection, field in mutations:
            value = copy.deepcopy(self.examples["lock"])
            if field is None: value[collection] = "A" * 64
            else: value[collection][0][field] = "A" * 64
            with self.subTest(collection=collection, field=field):
                with self.assertRaises(ValidationError): self.assert_schema_valid("lock", value)

    def test_lock_requires_lexically_ordered_components(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); value["resolved_components"] = list(reversed(value["resolved_components"]))
        with self.assertRaises(ValueError): self.assert_schema_valid("lock", value)

    def test_lock_rejects_duplicate_resolved_component_ids(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); duplicate = copy.deepcopy(value["resolved_components"][0]); duplicate["version"] += 1; value["resolved_components"].append(duplicate); value["resolved_components"].sort(key=lambda item: item["id"])
        with self.assertRaises((ValidationError, ValueError)): self.assert_schema_valid("lock", value)

    def test_lock_requires_exactly_one_artifact_component(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); duplicate = copy.deepcopy(value["resolved_components"][0]); duplicate["id"] = "artifact.skill-core"; value["resolved_components"].append(duplicate); value["resolved_components"].sort(key=lambda item: item["id"])
        with self.assertRaises((ValidationError, ValueError)): self.assert_schema_valid("lock", value)

    def test_lock_requires_lexically_ordered_destinations(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); value["files"] = list(reversed(value["files"]))
        with self.assertRaises(ValueError): self.assert_schema_valid("lock", value)

    def test_lock_rejects_duplicate_destination_owners(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); duplicate = copy.deepcopy(value["files"][0]); duplicate["component"] = value["files"][1]["component"]; value["files"].append(duplicate); value["files"].sort(key=lambda item: item["destination"])
        with self.assertRaises(ValueError): self.assert_schema_valid("lock", value)

    def test_lock_rejects_portability_destination_collisions(self) -> None:
        for destination in ("Contracts/runtime.md", "contracts"):
            value = copy.deepcopy(self.examples["lock"]); value["files"][0]["destination"] = destination; value["files"].sort(key=lambda item: item["destination"])
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError): self.assert_schema_valid("lock", value)

    def test_lock_rejects_case_variant_git_destination(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); value["files"][0]["destination"] = ".Git/config"; value["files"].sort(key=lambda item: item["destination"])
        with self.assertRaises((ValidationError, ValueError)): self.assert_schema_valid("lock", value)

    def test_lock_rejects_its_reserved_destination(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); value["files"][0]["destination"] = LOCK_DESTINATION; value["files"].sort(key=lambda item: item["destination"])
        with self.assertRaises((ValidationError, ValueError)): self.assert_schema_valid("lock", value)

    def test_lock_rejects_unresolved_file_owner(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); value["files"][0]["component"] = "capability.unknown"
        with self.assertRaises(ValueError): self.assert_schema_valid("lock", value)

    def test_lock_requires_every_resolved_component_to_own_material(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); removed_owner = value["resolved_components"][-1]["id"]; value["files"] = [item for item in value["files"] if item["component"] != removed_owner]
        with self.assertRaises(ValueError): self.assert_schema_valid("lock", value)

    def test_lock_requires_nonempty_file_inventory(self) -> None:
        value = copy.deepcopy(self.examples["lock"]); value["files"] = []
        with self.assertRaises(ValidationError): self.assert_schema_valid("lock", value)


if __name__ == "__main__":
    unittest.main()
