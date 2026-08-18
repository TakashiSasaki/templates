from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
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
    resolved = set(component_ids)
    destinations = [item["destination"] for item in value["files"]]
    if len(destinations) != len(set(destinations)):
        raise ValueError("a materialized destination must have one owner")
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
        with self.assertRaises(Exception):
            self.assert_schema_valid("component", value)

    def test_component_rejects_unsafe_destination(self) -> None:
        for destination in ("../outside", "/absolute", "C:/windows", "a/../b", ".git/config"):
            value = copy.deepcopy(self.examples["component"])
            value["materials"][0]["destination"] = destination
            with self.subTest(destination=destination):
                with self.assertRaises(Exception):
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

    def test_lock_requires_full_lowercase_revision(self) -> None:
        for revision in ("abc123", "A" * 40, "0" * 39, "0" * 41):
            value = copy.deepcopy(self.examples["lock"])
            value["source"]["revision"] = revision
            with self.subTest(revision=revision):
                with self.assertRaises(Exception):
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
        with self.assertRaises(Exception):
            self.assert_schema_valid("component", value)


if __name__ == "__main__":
    unittest.main()
