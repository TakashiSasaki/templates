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
    destinations = [item["destination"] for item in value["materials"]]
    if len(destinations) != len(set(destinations)):
        raise ValueError("one component must not declare the same destination twice")


def validate_recipe_semantics(value: dict) -> None:
    groups = [
        set(value["required_components"]),
        set(value["default_components"]),
        set(value["optional_components"]),
    ]
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
    resolved = set(component_ids)
    destinations = [item["destination"] for item in value["files"]]
    if len(destinations) != len(set(destinations)):
        raise ValueError("a materialized destination must have one owner")
    if LOCK_DESTINATION in destinations:
        raise ValueError("lock must not include its own reserved destination")
    unknown_owners = sorted(
        {item["component"] for item in value["files"] if item["component"] not in resolved}
    )
    if unknown_owners:
        raise ValueError(f"lock file owner is not resolved: {unknown_owners}")


SEMANTIC_VALIDATORS = {
    "component": validate_component_semantics,
    "recipe": validate_recipe_semantics,
    "config": validate_config_semantics,
    "lock": validate_lock_semantics,
}


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
        value = copy.deepcopy(self.examples["component"])
        value["kind"] = "artifact"
        with self.assertRaises(ValidationError):
            self.assert_schema_valid("component", value)

    def test_component_rejects_unsafe_destination(self) -> None:
        for destination in (
            "../outside",
            "/absolute",
            "C:/windows",
            "a/../b",
            ".git/config",
            "contracts/",
            "-option/file",
            "contracts/-option",
            LOCK_DESTINATION,
        ):
            value = copy.deepcopy(self.examples["component"])
            value["materials"][0]["destination"] = destination
            with self.subTest(destination=destination):
                with self.assertRaises(ValidationError):
                    self.assert_schema_valid("component", value)

    def test_component_rejects_unsafe_source(self) -> None:
        for source in ("../outside", "/absolute", "C:/windows", "a/../b", ".git/config", "contracts/", "-option/file"):
            value = copy.deepcopy(self.examples["component"])
            value["materials"][0]["source"] = source
            with self.subTest(source=source):
                with self.assertRaises(ValidationError):
                    self.assert_schema_valid("component", value)

    def test_component_rejects_self_dependency(self) -> None:
        value = copy.deepcopy(self.examples["component"])
        value["requires"].append(value["id"])
        with self.assertRaises(ValueError):
            self.assert_schema_valid("component", value)

    def test_component_rejects_required_conflict_overlap(self) -> None:
        value = copy.deepcopy(self.examples["component"])
        value["conflicts"].append(value["requires"][0])
        with self.assertRaises(ValueError):
            self.assert_schema_valid("component", value)

    def test_component_rejects_duplicate_destination(self) -> None:
        value = copy.deepcopy(self.examples["component"])
        value["materials"][1]["destination"] = value["materials"][0]["destination"]
        with self.assertRaises(ValueError):
            self.assert_schema_valid("component", value)

    def test_copied_material_requires_source(self) -> None:
        value = copy.deepcopy(self.examples["component"])
        del value["materials"][0]["source"]
        with self.assertRaises(ValidationError):
            self.assert_schema_valid("component", value)

    def test_generated_material_has_no_source(self) -> None:
        value = copy.deepcopy(self.examples["component"])
        value["materials"][0] = {
            "destination": ".template-composition/registry.json",
            "ownership": "generated",
        }
        self.assert_schema_valid("component", value)
        value["materials"][0]["source"] = "registry-source.json"
        with self.assertRaises(ValidationError):
            self.assert_schema_valid("component", value)

    def test_recipe_rejects_selection_class_overlap(self) -> None:
        value = copy.deepcopy(self.examples["recipe"])
        value["optional_components"].append(value["default_components"][0])
        with self.assertRaises(ValueError):
            self.assert_schema_valid("recipe", value)

    def test_config_rejects_include_exclude_overlap(self) -> None:
        value = copy.deepcopy(self.examples["config"])
        value["components"]["exclude"].append(value["components"]["include"][0])
        with self.assertRaises(ValueError):
            self.assert_schema_valid("config", value)

    def test_config_cannot_select_artifact_component(self) -> None:
        for field in ("include", "exclude"):
            value = copy.deepcopy(self.examples["config"])
            value["components"][field].append("artifact.skill-core")
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    self.assert_schema_valid("config", value)

    def test_lock_requires_canonical_source_repository(self) -> None:
        value = copy.deepcopy(self.examples["lock"])
        value["source"]["repository"] = "example/other"
        with self.assertRaises(ValidationError):
            self.assert_schema_valid("lock", value)

    def test_lock_requires_full_lowercase_revision(self) -> None:
        for revision in ("abc123", "A" * 40, "0" * 39, "0" * 41):
            value = copy.deepcopy(self.examples["lock"])
            value["source"]["revision"] = revision
            with self.subTest(revision=revision):
                with self.assertRaises(ValidationError):
                    self.assert_schema_valid("lock", value)

    def test_lock_rejects_duplicate_resolved_component_ids(self) -> None:
        value = copy.deepcopy(self.examples["lock"])
        value["resolved_components"].append(copy.deepcopy(value["resolved_components"][0]))
        with self.assertRaises(ValueError):
            self.assert_schema_valid("lock", value)

    def test_lock_requires_lexically_ordered_components(self) -> None:
        value = copy.deepcopy(self.examples["lock"])
        value["resolved_components"][0], value["resolved_components"][1] = (
            value["resolved_components"][1],
            value["resolved_components"][0],
        )
        with self.assertRaises(ValueError):
            self.assert_schema_valid("lock", value)

    def test_lock_rejects_its_reserved_destination(self) -> None:
        value = copy.deepcopy(self.examples["lock"])
        value["files"][0]["destination"] = LOCK_DESTINATION
        with self.assertRaises(ValidationError):
            self.assert_schema_valid("lock", value)

    def test_lock_rejects_duplicate_destination_owners(self) -> None:
        value = copy.deepcopy(self.examples["lock"])
        duplicate = copy.deepcopy(value["files"][0])
        duplicate["component"] = "capability.runtime"
        value["files"].append(duplicate)
        with self.assertRaises(ValueError):
            self.assert_schema_valid("lock", value)

    def test_lock_rejects_unresolved_file_owner(self) -> None:
        value = copy.deepcopy(self.examples["lock"])
        value["files"][0]["component"] = "capability.unknown"
        with self.assertRaises(ValueError):
            self.assert_schema_valid("lock", value)

    def test_descriptors_cannot_add_execution_hooks(self) -> None:
        value = copy.deepcopy(self.examples["component"])
        value["post_install"] = "echo unsafe"
        with self.assertRaises(ValidationError):
            self.assert_schema_valid("component", value)


if __name__ == "__main__":
    unittest.main()
