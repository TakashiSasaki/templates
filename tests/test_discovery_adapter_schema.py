"""P1 structural contract; does not claim runtime or adoption qualification."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/progressive-discovery-adapter.schema.json").read_text())
VALID = {"schema_version": 2, "entries": [{"path": "README.md", "kind": "file"}]}


def test_schemas_are_valid_202012():
    for name in ("progressive-discovery-adapter", "discovery-projection"):
        Draft202012Validator.check_schema(
            json.loads((ROOT / f"schemas/{name}.schema.json").read_text())
        )
    Draft202012Validator(SCHEMA).validate(VALID)


@pytest.mark.parametrize(
    "patch",
    [
        {"schema_version": 1},
        {"schema_version": 3},
        {"schema_version": "2"},
        {"unknown": 1},
        {"entries": []},
        {"entries": [VALID["entries"][0]] * 2},
        {"entries": [{"path": "../README.md", "kind": "file"}]},
        {"entries": [{"path": "https://host/a", "kind": "file"}]},
        {"entries": [{"path": "a", "kind": "file", "extra": True}]},
        {"exclude": [{"path": "tests", "reason": " "}]},
        {"inventories": [{"path": "a.json", "format": "xml", "select": []}]},
        {"generated": [{"path": "a/index.md", "title": "A"}]},
    ],
)
def test_rejects_malformed_structure(patch):
    assert list(Draft202012Validator(SCHEMA).iter_errors({**VALID, **patch}))


@pytest.mark.parametrize("missing", ["schema_version", "entries"])
def test_required(missing):
    value = copy.deepcopy(VALID)
    del value[missing]
    assert list(Draft202012Validator(SCHEMA).iter_errors(value))


def test_semantic_conflict_is_structurally_valid():
    # P2 must reject this; schema does not claim filesystem/relational guarantees.
    Draft202012Validator(SCHEMA).validate(
        {**VALID, "exclude": [{"path": "README.md", "reason": "Deliberate contradictory example"}]}
    )
