from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path('.').resolve()


def write(path: str, content: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf-8')


def replace_exact(path: str, old: str, new: str, count: int = 1) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f'{path}: expected {count} occurrence(s), found {actual}: {old!r}')
    p.write_text(text.replace(old, new), encoding='utf-8')


def replace_method(path: str, start_marker: str, end_marker: str, replacement: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    p.write_text(text[:start] + replacement + text[end:], encoding='utf-8')


service_component = {
    'schema_version': 1,
    'id': 'capability.service',
    'kind': 'capability',
    'version': 2,
    'summary': 'Independently reachable non-browser service contract.',
    'requires': ['capability.runtime', 'lifecycle.implementation-evidence'],
    'conflicts': [],
    'contract_registrations': [
        {
            'id': 'service_interface',
            'document': 'contracts/service-interface.json',
            'schema': 'schemas/service-interface.schema.json',
            'migration_slug': 'service-interface',
            'document_schema_version': 1,
            'version_history': [{'version': 1, 'change_type': 'initial'}],
            'purpose': 'Declare caller-visible independently reachable service operations and their protocol invocation contracts.',
        }
    ],
    'materials': [
        {'source': 'files/SERVICE_INTERFACE.md', 'destination': 'SERVICE_INTERFACE.md', 'ownership': 'seed'},
        {'source': 'files/contracts/service-interface.json', 'destination': 'contracts/service-interface.json', 'ownership': 'seed'},
        {'source': 'files/schemas/service-interface.schema.json', 'destination': 'schemas/service-interface.schema.json', 'ownership': 'managed'},
        {'source': 'files/.template-composition/validators/validate_service_interface.py', 'destination': '.template-composition/validators/validate_service_interface.py', 'ownership': 'managed'},
    ],
}
write('components/capability.service/component.json', json.dumps(service_component, indent=2) + '\n')

service_seed = {
    '$schema': '../schemas/service-interface.schema.json',
    'schemaVersion': 1,
    'mode': 'template',
    'operations': [],
}
write('components/capability.service/files/contracts/service-interface.json', json.dumps(service_seed, indent=2) + '\n')

schema = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    '$id': 'https://templates.moukaeritai.work/composition/schemas/service-interface.schema.json',
    'title': 'Service interface contract',
    'type': 'object',
    'additionalProperties': False,
    'required': ['$schema', 'schemaVersion', 'mode', 'operations'],
    'properties': {
        '$schema': {'const': '../schemas/service-interface.schema.json'},
        'schemaVersion': {'const': 1},
        'mode': {'enum': ['template', 'product']},
        'protocol': {'type': 'string', 'minLength': 1},
        'operations': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['id', 'invocation', 'success', 'negative'],
                'properties': {
                    'id': {'type': 'string', 'pattern': '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'},
                    'invocation': {'type': 'string', 'minLength': 1},
                    'success': {'type': 'string', 'minLength': 1},
                    'negative': {'type': 'string', 'minLength': 1},
                },
            },
        },
    },
    'allOf': [
        {
            'if': {'properties': {'mode': {'const': 'template'}}, 'required': ['mode']},
            'then': {'properties': {'operations': {'maxItems': 0}}, 'not': {'required': ['protocol']}},
        },
        {
            'if': {'properties': {'mode': {'const': 'product'}}, 'required': ['mode']},
            'then': {'required': ['protocol'], 'properties': {'operations': {'minItems': 1}}},
        },
    ],
}
write('components/capability.service/files/schemas/service-interface.schema.json', json.dumps(schema, indent=2) + '\n')

validator = r'''#!/usr/bin/env python3
"""Validate selected service contracts and executable implementation evidence."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SERVICE_CONTRACT = Path("contracts/service-interface.json")
IMPLEMENTATION_EVIDENCE = Path("contracts/implementation-evidence.json")
EXECUTABLE_PROOF_KINDS = frozenset({"integration-test", "end-to-end-test"})


def load_json(root: Path, relative: Path) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{relative} must contain a JSON object")
    return value


def target_key(target: object) -> tuple[object, ...]:
    if not isinstance(target, dict):
        return (None, None, None, None)
    return (
        target.get("kind"),
        target.get("contractId"),
        target.get("itemKind"),
        target.get("itemId"),
    )


def executable_proof_present(record: dict[str, Any], field: str) -> bool:
    proofs = record.get(field)
    return isinstance(proofs, list) and any(
        isinstance(proof, dict)
        and proof.get("status") == "verified"
        and proof.get("kind") in EXECUTABLE_PROOF_KINDS
        for proof in proofs
    )


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        contract = load_json(root, SERVICE_CONTRACT)
        evidence = load_json(root, IMPLEMENTATION_EVIDENCE)
    except (OSError, ValueError, TypeError) as exc:
        return [str(exc)]

    service_mode = contract.get("mode")
    evidence_mode = evidence.get("mode")
    if service_mode == "template":
        if evidence_mode == "product":
            errors.append(
                "capability.service is selected but contracts/service-interface.json remains in template mode while product implementation evidence is active; either remove capability.service from Composition intent or declare the service contract in product mode and add executable service evidence"
            )
        return errors
    if service_mode != "product":
        return ["contracts/service-interface.json mode must be template or product"]
    if evidence_mode != "product":
        return ["product service contract requires product implementation evidence"]

    operations = contract.get("operations")
    if not isinstance(operations, list):
        return ["product service contract operations must be a list"]
    operation_ids = [entry.get("id") for entry in operations if isinstance(entry, dict)]
    duplicates = sorted(key for key, count in Counter(operation_ids).items() if key is not None and count > 1)
    if duplicates:
        errors.append(f"duplicate service operation ids: {duplicates}")

    expected = {
        ("contract-item", "service_interface", "operation", operation_id)
        for operation_id in operation_ids
        if isinstance(operation_id, str)
    }
    records = evidence.get("records")
    requirements = evidence.get("requirements")
    if not isinstance(records, list):
        return errors + ["product implementation evidence records must be a list"]
    if not isinstance(requirements, list):
        return errors + ["product implementation evidence requirements must be a list"]

    service_records = [
        record
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("target"), dict)
        and record["target"].get("contractId") == "service_interface"
    ]
    by_target: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for record in service_records:
        by_target.setdefault(target_key(record.get("target")), []).append(record)

    actual = set(by_target)
    for missing in sorted(expected - actual, key=str):
        errors.append(f"missing service implementation-evidence target: {missing}")
    for unknown in sorted(actual - expected, key=str):
        errors.append(f"unknown service implementation-evidence target: {unknown}")

    requirement_records: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        for record_id in requirement.get("recordIds", []):
            if isinstance(record_id, str):
                requirement_records.setdefault(record_id, []).append(requirement)

    for key in sorted(expected, key=str):
        matches = by_target.get(key, [])
        if len(matches) != 1:
            if len(matches) > 1:
                errors.append(f"service target {key} must have exactly one record; found {len(matches)}")
            continue
        record = matches[0]
        record_id = record.get("id")
        for field, label in (("positiveEvidence", "positive"), ("negativeEvidence", "negative")):
            if not executable_proof_present(record, field):
                errors.append(
                    f"service record {record_id!r} requires verified {label} executable proof kind from {sorted(EXECUTABLE_PROOF_KINDS)}; static inspection or unit-only proof is insufficient"
                )
        linked = requirement_records.get(record_id, []) if isinstance(record_id, str) else []
        if not linked:
            errors.append(f"service record {record_id!r} must be linked from a product requirement")
            continue
        if not any(
            isinstance(requirement.get("requiredPositiveProofKinds"), list)
            and EXECUTABLE_PROOF_KINDS.intersection(requirement["requiredPositiveProofKinds"])
            for requirement in linked
        ):
            errors.append(
                f"service record {record_id!r} requires a linked requirement whose requiredPositiveProofKinds includes one of {sorted(EXECUTABLE_PROOF_KINDS)}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    errors = validate(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Service interface coverage and executable evidence strength: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
write('components/capability.service/files/.template-composition/validators/validate_service_interface.py', validator)

# Machine-readable authority guidance.
service_md = ROOT / 'components/capability.service/files/SERVICE_INTERFACE.md'
text = service_md.read_text(encoding='utf-8')
text = text.replace(
    '## Status\n\n```text\nSelection status: UNSELECTED\n```\n',
    '''## Machine-readable authority\n\n`contracts/service-interface.json` is the canonical machine-readable state for this selected capability. Its initial `template` mode makes no product service claim. Switch it to `product` only after every caller-visible operation is concrete and the shared implementation-evidence graph contains executable positive and negative proof for each operation.\n\nWhen `capability.service` is selected, product implementation evidence cannot remain valid while this contract is still in template mode. Static source inspection and unit-only proof do not satisfy the service executable-proof obligation. Use `integration-test` or `end-to-end-test` evidence that actually crosses the maintained service boundary.\n\nKeep this narrative contract aligned with the JSON authority. Runtime listener/deployment details remain in `RUNTIME.md`.\n'''
)
service_md.write_text(text, encoding='utf-8')

# Selected-component registry and component version.
registry_path = ROOT / 'components/lifecycle.composition-state/files/.template-composition/validation-registry.json'
registry = json.loads(registry_path.read_text(encoding='utf-8'))
entry = {
    'id': 'service-interface',
    'component': 'capability.service',
    'entrypoint': '.template-composition/validators/validate_service_interface.py',
    'arguments': ['.'],
    'purpose': 'Validate selected service operation coverage and require executable implementation-evidence proof strength.',
}
ids = [item['id'] for item in registry['validators']]
if 'service-interface' in ids:
    raise SystemExit('service-interface validator already registered')
insert_at = ids.index('cli-interface') + 1
registry['validators'].insert(insert_at, entry)
registry_path.write_text(json.dumps(registry, indent=2) + '\n', encoding='utf-8')

state_path = ROOT / 'components/lifecycle.composition-state/component.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
if state['version'] != 4:
    raise SystemExit(f'unexpected composition-state version {state["version"]}')
state['version'] = 5
state_path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')

# Catalog guidance and dependency closure tests.
replace_exact(
    'catalog/README.md',
    '| An independently reachable non-browser service | `capability.service` | `capability.runtime` | Service interface contract |',
    '| An independently reachable non-browser service | `capability.service` | `capability.runtime` + implementation evidence (and contract evolution) | Machine-readable service operation contract with executable-proof enforcement |',
)
replace_exact(
    'translations/ja/catalog/README.md',
    '| 独立して到達可能な non-browser service | `capability.service` | `capability.runtime` | service interface contract |',
    '| 独立して到達可能な non-browser service | `capability.service` | `capability.runtime` + implementation evidence（および contract evolution） | machine-readable service operation contract と executable-proof enforcement |',
)
replace_exact(
    'tests/test_production_catalog.py',
    '            ["capability.runtime", "capability.service"],\n',
    '            [\n                "capability.runtime",\n                "capability.service",\n                "lifecycle.contract-evolution",\n                "lifecycle.implementation-evidence",\n            ],\n',
)

catalog_test = ROOT / 'tests/test_catalog_consumer_selection_guide.py'
ctext = catalog_test.read_text(encoding='utf-8')
needle = '''        self.assertEqual(\n            dependency_closure("artifact.skill-core", "lifecycle.release-bundle"),\n'''
if ctext.count(needle) != 1:
    raise SystemExit('catalog dependency insertion point changed')
service_assert = '''        self.assertEqual(\n            dependency_closure("artifact.skill-core", "capability.service"),\n            {\n                "artifact.skill-core",\n                "capability.runtime",\n                "capability.service",\n                "lifecycle.composition-state",\n                "lifecycle.contract-evolution",\n                "lifecycle.implementation-evidence",\n            },\n        )\n\n'''
catalog_test.write_text(ctext.replace(needle, service_assert + needle), encoding='utf-8')

# Focused service contract tests.
service_test = r'''from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "components" / "capability.service"
SCHEMA = COMPONENT / "files" / "schemas" / "service-interface.schema.json"
SEED = COMPONENT / "files" / "contracts" / "service-interface.json"
VALIDATOR = COMPONENT / "files" / ".template-composition" / "validators" / "validate_service_interface.py"


class ServiceInterfaceContractTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def product_contract(self) -> dict:
        return {
            "$schema": "../schemas/service-interface.schema.json",
            "schemaVersion": 1,
            "mode": "product",
            "protocol": "http-json",
            "operations": [
                {
                    "id": "list-records",
                    "invocation": "GET /api/records",
                    "success": "200 JSON record array",
                    "negative": "400 JSON error for invalid query",
                }
            ],
        }

    def evidence(self, *, proof_kind: str = "integration-test", requirement_kind: str | None = None) -> dict:
        required_kind = requirement_kind or proof_kind
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 3,
            "mode": "product",
            "commands": [{"id": "service-proof", "command": "python -m unittest tests.test_service", "purpose": "Exercise the public service boundary."}],
            "releaseGates": [{"id": "release", "purpose": "Run executable service proof.", "commandIds": ["service-proof"]}],
            "requirements": [{"id": "REQ-SERVICE-LIST", "description": "The maintained service operation executes for callers.", "recordIds": ["service-interface-operation-list-records"], "requiredPositiveProofKinds": [required_kind]}],
            "records": [
                {
                    "id": "service-interface-operation-list-records",
                    "target": {"kind": "contract-item", "contractId": "service_interface", "itemKind": "operation", "itemId": "list-records"},
                    "implementationBoundary": {"status": "verified", "description": "HTTP service adapter.", "locator": "app/service.py"},
                    "positiveEvidence": [{"id": "service-positive", "status": "verified", "kind": proof_kind, "description": "Execute a valid service request.", "locator": "tests/test_service.py", "commandId": "service-proof", "expectedResult": "documented success response"}],
                    "negativeEvidence": [{"id": "service-negative", "status": "verified", "kind": proof_kind, "description": "Execute an invalid service request.", "locator": "tests/test_service.py", "commandId": "service-proof", "expectedResult": "documented error response"}],
                    "releaseGateIds": ["release"],
                }
            ],
        }

    def run_validator(self, contract: dict, evidence: dict) -> subprocess.CompletedProcess[str]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.write_json(root / "contracts/service-interface.json", contract)
        self.write_json(root / "contracts/implementation-evidence.json", evidence)
        return subprocess.run([sys.executable, str(VALIDATOR), str(root)], cwd=ROOT, text=True, capture_output=True, check=False)

    def test_seed_and_product_shape_are_schema_valid(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        validator.validate(json.loads(SEED.read_text(encoding="utf-8")))
        validator.validate(self.product_contract())

    def test_product_service_requires_executable_positive_negative_and_requirement_strength(self) -> None:
        result = self.run_validator(self.product_contract(), self.evidence())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("executable evidence strength: OK", result.stdout)

        weak_proof = self.run_validator(self.product_contract(), self.evidence(proof_kind="inspection", requirement_kind="integration-test"))
        self.assertNotEqual(weak_proof.returncode, 0)
        self.assertIn("executable proof kind", weak_proof.stderr)
        self.assertIn("static inspection or unit-only proof is insufficient", weak_proof.stderr)

        weak_requirement = self.run_validator(self.product_contract(), self.evidence(proof_kind="integration-test", requirement_kind="inspection"))
        self.assertNotEqual(weak_requirement.returncode, 0)
        self.assertIn("requiredPositiveProofKinds", weak_requirement.stderr)

    def test_product_evidence_cannot_hide_selected_service_in_template_mode(self) -> None:
        result = self.run_validator(json.loads(SEED.read_text(encoding="utf-8")), self.evidence())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("remains in template mode while product implementation evidence is active", result.stderr)

    def test_unknown_duplicate_and_missing_service_operation_targets_fail_closed(self) -> None:
        evidence = self.evidence()
        unknown = deepcopy(evidence)
        unknown["records"][0]["target"]["itemId"] = "other"
        result = self.run_validator(self.product_contract(), unknown)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing service implementation-evidence target", result.stderr)
        self.assertIn("unknown service implementation-evidence target", result.stderr)

        duplicate = deepcopy(evidence)
        second = deepcopy(duplicate["records"][0])
        second["id"] = "service-interface-operation-list-records-duplicate"
        duplicate["records"].append(second)
        result = self.run_validator(self.product_contract(), duplicate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must have exactly one record", result.stderr)


if __name__ == "__main__":
    unittest.main()
'''
write('tests/test_service_interface_contract.py', service_test)

# Materialized selected-service dispatch regression.
selected_path = ROOT / 'tests/test_selected_component_validation.py'
s = selected_path.read_text(encoding='utf-8')
insert = '\n\nif __name__ == "__main__":\n    unittest.main()\n'
if s.count(insert) != 1:
    raise SystemExit('selected-component test footer changed')
service_selected = r'''
    def test_service_selection_adds_machine_contract_evidence_lifecycle_and_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            self.apply(target, self.write_config(root, "skill", include=["capability.service"]))

            result, payload = self.run_consumer_validation(target)
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["status"], "valid")
            self.assertEqual(
                set(payload["resolved_components"]),
                {
                    "artifact.skill-core",
                    "capability.runtime",
                    "capability.service",
                    "lifecycle.composition-state",
                    "lifecycle.contract-evolution",
                    "lifecycle.implementation-evidence",
                },
            )
            checks = {check["id"]: check for check in payload["checks"]}
            self.assertIn("service-interface", checks)
            self.assertEqual(checks["service-interface"]["status"], "passed")
            self.assertIn("Service interface coverage", checks["service-interface"]["stdout"])
            self.assertEqual(checks["implementation-evidence"]["status"], "deferred")
            manifest = json.loads((target / "contracts/manifest.json").read_text(encoding="utf-8"))
            self.assertIn("service_interface", {entry["id"] for entry in manifest["contracts"]})
            service_contract = json.loads((target / "contracts/service-interface.json").read_text(encoding="utf-8"))
            self.assertEqual(service_contract["mode"], "template")
            self.assertEqual(service_contract["operations"], [])
'''
selected_path.write_text(s.replace(insert, '\n' + service_selected + insert), encoding='utf-8')

# Task Ledger walkthrough service machine contract and complete HTTP operation execution.
operations = [
    {'id': 'list-tasks', 'invocation': 'GET /api/tasks?status=all|open|completed', 'success': '200 JSON task array for a valid status filter', 'negative': '400 JSON error for an invalid status filter'},
    {'id': 'get-task', 'invocation': 'GET /api/tasks/{id}', 'success': '200 JSON task for an existing id', 'negative': '404 JSON error for a missing id'},
    {'id': 'create-task', 'invocation': 'POST /api/tasks', 'success': '201 JSON task for a non-empty title', 'negative': '400 JSON error for an empty title'},
    {'id': 'update-task', 'invocation': 'PATCH /api/tasks/{id}', 'success': '200 JSON updated task for an existing id', 'negative': '404 JSON error for a missing id'},
    {'id': 'delete-task', 'invocation': 'DELETE /api/tasks/{id}', 'success': '204 for an existing id', 'negative': '404 JSON error when the id no longer exists'},
    {'id': 'health', 'invocation': 'GET /healthz', 'success': '200 JSON status ok', 'negative': '404 JSON error for an unknown service path'},
]
service_contract = {'$schema': '../schemas/service-interface.schema.json', 'schemaVersion': 1, 'mode': 'product', 'protocol': 'http-json', 'operations': operations}
service_json = json.dumps(service_contract, indent=2)

for path in ('docs/guides/webapp-product-walkthrough.md', 'translations/ja/docs/guides/webapp-product-walkthrough.md'):
    p = ROOT / path
    t = p.read_text(encoding='utf-8')
    marker = '### CLI contract' if path.startswith('docs/') else '### CLI contract'
    before = '\n### CLI contract\n'
    if t.count(before) != 1:
        raise SystemExit(f'{path}: CLI section marker changed')
    if path.startswith('docs/'):
        service_guidance = f'''\nBecause `capability.service` is selected, replace the editable machine seed `contracts/service-interface.json` after these operations exist and are executable:\n\n```json\n{service_json}\n```\n\nDo not switch the service contract to `product` because a listener starts or because source routes exist. Section 12 executes every declared operation through the HTTP boundary, including a negative path for each operation, and Section 15 links each `service_interface/operation/<id>` target to `integration-test` evidence.\n'''
    else:
        service_guidance = f'''\n`capability.service` を選択しているため、これらの operation が実装され executable になった後、editable machine seed `contracts/service-interface.json` を置き換えます。\n\n```json\n{service_json}\n```\n\nlistener が起動したことや source route が存在することだけで service contract を `product` にしてはいけません。Section 12 では宣言した全 operation を HTTP boundary 越しに実行し、各 operation の negative path も検査します。Section 15 では各 `service_interface/operation/<id>` target を `integration-test` evidence に接続します。\n'''
    p.write_text(t.replace(before, service_guidance + before), encoding='utf-8')

# Replace the walkthrough HTTP API test method in EN + JA code blocks.
expanded_method = r'''    def test_http_api_positive_and_negative_paths(self) -> None:
        server = make_server(self.database, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def request(method: str, path: str, payload: dict | None = None):
            data = None if payload is None else json.dumps(payload).encode()
            headers = {} if payload is None else {"Content-Type": "application/json"}
            return urllib.request.urlopen(
                urllib.request.Request(base + path, data=data, headers=headers, method=method)
            )

        try:
            health = json.load(request("GET", "/healthz"))
            self.assertEqual(health, {"status": "ok"})
            with self.assertRaises(urllib.error.HTTPError) as missing_health:
                request("GET", "/not-a-service-route")
            self.assertEqual(missing_health.exception.code, 404)

            created = json.load(request("POST", "/api/tasks", {"title": "from api"}))
            with self.assertRaises(urllib.error.HTTPError) as invalid_create:
                request("POST", "/api/tasks", {"title": ""})
            self.assertEqual(invalid_create.exception.code, 400)

            open_tasks = json.load(request("GET", "/api/tasks?status=open"))
            self.assertEqual([task["id"] for task in open_tasks], [created["id"]])
            with self.assertRaises(urllib.error.HTTPError) as invalid_filter:
                request("GET", "/api/tasks?status=invalid")
            self.assertEqual(invalid_filter.exception.code, 400)

            fetched = json.load(request("GET", f"/api/tasks/{created['id']}"))
            self.assertEqual(fetched["title"], "from api")
            with self.assertRaises(urllib.error.HTTPError) as missing_get:
                request("GET", "/api/tasks/999999")
            self.assertEqual(missing_get.exception.code, 404)

            updated = json.load(request("PATCH", f"/api/tasks/{created['id']}", {"completed": True}))
            self.assertTrue(updated["completed"])
            with self.assertRaises(urllib.error.HTTPError) as missing_patch:
                request("PATCH", "/api/tasks/999999", {"completed": True})
            self.assertEqual(missing_patch.exception.code, 404)

            deleted = request("DELETE", f"/api/tasks/{created['id']}")
            self.assertEqual(deleted.status, 204)
            deleted.close()
            with self.assertRaises(urllib.error.HTTPError) as missing_delete:
                request("DELETE", f"/api/tasks/{created['id']}")
            self.assertEqual(missing_delete.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
'''
for path in ('docs/guides/webapp-product-walkthrough.md', 'translations/ja/docs/guides/webapp-product-walkthrough.md'):
    replace_method(path, '    def test_http_api_positive_and_negative_paths(self) -> None:\n', '\n\n\nif __name__ == "__main__":', expanded_method)

# Evidence guidance, EN + JA.
replace_exact(
    'docs/guides/webapp-product-walkthrough.md',
    'Because `capability.cli` is selected, add one further record whose target is `contract-item / cli_interface / entrypoint / task-ledger`.',
    'Because `capability.service` is selected, add one `contract-item / service_interface / operation / <id>` record for every operation declared in `contracts/service-interface.json`. Use `task_ledger/cli.py` as the implementation boundary, `tests/test_task_ledger.py` as positive/negative proof locator, and `integration-test` as the proof kind. Each operation gets a stable requirement whose `requiredPositiveProofKinds` contains `integration-test`; the expanded HTTP test above executes both the documented success and negative path for all six operations. A selected service contract left in `template` mode, or service records backed only by source inspection/unit-only proof, must keep Composition validation invalid.\n\nBecause `capability.cli` is selected, add one further record whose target is `contract-item / cli_interface / entrypoint / task-ledger`.',
)
replace_exact(
    'translations/ja/docs/guides/webapp-product-walkthrough.md',
    '`capability.cli` を選択しているため、さらに `contract-item / cli_interface / entrypoint / task-ledger` target の record を1件追加します。',
    '`capability.service` を選択しているため、`contracts/service-interface.json` に宣言した全 operation について `contract-item / service_interface / operation / <id>` record を追加します。implementation boundary は `task_ledger/cli.py`、positive / negative proof locator は `tests/test_task_ledger.py`、proof kind は `integration-test` とし、各 operation を `requiredPositiveProofKinds` に `integration-test` を持つ stable requirement から link します。上の expanded HTTP test は6 operationすべてについて documented success と negative path の両方を実行します。service contract が `template` のまま、または source inspection / unit-only proof しかない状態を valid product completion としてはいけません。\n\n`capability.cli` を選択しているため、さらに `contract-item / cli_interface / entrypoint / task-ledger` target の record を1件追加します。',
)

# Task Ledger acceptance contract + service records.
acceptance_path = ROOT / 'tests/test_task_ledger_walkthrough_browser_acceptance.py'
a = acceptance_path.read_text(encoding='utf-8')
needle = '    def productize_cli_contract(self, target: Path) -> None:\n'
if a.count(needle) != 1:
    raise SystemExit('Task Ledger service insertion point changed')
service_methods = f'''    def service_operations(self) -> list[dict[str, str]]:\n        return {repr(operations)}\n\n    def productize_service_contract(self, target: Path) -> None:\n        self.write_json(\n            target / "contracts" / "service-interface.json",\n            {{\n                "$schema": "../schemas/service-interface.schema.json",\n                "schemaVersion": 1,\n                "mode": "product",\n                "protocol": "http-json",\n                "operations": self.service_operations(),\n            }},\n        )\n\n'''
a = a.replace(needle, service_methods + needle)
insert_before_cli = '        cli_record_id = "task-ledger-cli"\n'
if a.count(insert_before_cli) != 1:
    raise SystemExit('Task Ledger service evidence insertion point changed')
service_evidence = '''        for operation in self.service_operations():\n            operation_id = operation["id"]\n            record_id = f"task-ledger-service-{operation_id}"\n            records.append(\n                {\n                    "id": record_id,\n                    "target": {\n                        "kind": "contract-item",\n                        "contractId": "service_interface",\n                        "itemKind": "operation",\n                        "itemId": operation_id,\n                    },\n                    "implementationBoundary": {\n                        "status": "verified",\n                        "description": "Task Ledger exposes this independently reachable HTTP service operation.",\n                        "locator": "task_ledger/cli.py",\n                    },\n                    "positiveEvidence": [\n                        {\n                            "id": f"{record_id}-positive",\n                            "status": "verified",\n                            "kind": "integration-test",\n                            "description": f"Execute the success path for {operation_id} through HTTP.",\n                            "locator": "tests/test_task_ledger.py",\n                            "commandId": "verify-product",\n                            "expectedResult": operation["success"],\n                        }\n                    ],\n                    "negativeEvidence": [\n                        {\n                            "id": f"{record_id}-negative",\n                            "status": "verified",\n                            "kind": "integration-test",\n                            "description": f"Execute the negative path for {operation_id} through HTTP.",\n                            "locator": "tests/test_task_ledger.py",\n                            "commandId": "verify-product",\n                            "expectedResult": operation["negative"],\n                        }\n                    ],\n                    "releaseGateIds": ["product-verification"],\n                }\n            )\n            requirements.append(\n                {\n                    "id": f"REQ-TASK-LEDGER-SERVICE-{operation_id.upper().replace('-', '_')}",\n                    "description": f"Task Ledger service operation {operation_id} executes its documented success and negative behavior.",\n                    "recordIds": [record_id],\n                    "requiredPositiveProofKinds": ["integration-test"],\n                }\n            )\n\n'''
a = a.replace(insert_before_cli, service_evidence + insert_before_cli)
call = '            self.productize_cli_contract(target)\n            self.productize_evidence(target)\n'
if a.count(call) != 1:
    raise SystemExit('Task Ledger productize calls changed')
a = a.replace(call, '            self.productize_service_contract(target)\n            self.productize_cli_contract(target)\n            self.productize_evidence(target)\n')
acceptance_path.write_text(a, encoding='utf-8')

# Translation bindings after EN doc changes.
manifest_path = ROOT / 'translations/manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
for entry in manifest['translations']:
    if entry['canonical'] in {'catalog/README.md', 'docs/guides/webapp-product-walkthrough.md'}:
        entry['canonical_blob_sha'] = subprocess.check_output(['git', 'hash-object', entry['canonical']], text=True).strip()
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

# Basic source compile without writing bytecode.
for path in (
    'components/capability.service/files/.template-composition/validators/validate_service_interface.py',
    'tests/test_service_interface_contract.py',
    'tests/test_selected_component_validation.py',
    'tests/test_task_ledger_walkthrough_browser_acceptance.py',
):
    compile((ROOT / path).read_text(encoding='utf-8'), path, 'exec')

print('service machine-evidence patch applied')
