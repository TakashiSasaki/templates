from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path('.')


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def dump(path: str, value, *, compact: bool = False):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(value, separators=(',', ':')) + '\n'
    else:
        text = json.dumps(value, indent=2) + '\n'
    target.write_text(text, encoding='utf-8')


def replace_exact(path: str, old: str, new: str):
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise SystemExit(f'{path}: expected exactly one occurrence of {old!r}, got {text.count(old)}')
    target.write_text(text.replace(old, new), encoding='utf-8')


def replace_block(path: str, start: str, end: str, replacement: str):
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if text.count(start) != 1 or text.count(end) < 1:
        raise SystemExit(f'{path}: block markers changed: {start!r} / {end!r}')
    begin = text.index(start)
    finish = text.index(end, begin)
    target.write_text(text[:begin] + replacement.rstrip() + '\n\n' + text[finish:], encoding='utf-8')


# implementation-evidence component v8 / document schema v4.
component_path = 'components/lifecycle.implementation-evidence/component.json'
component = load(component_path)
component['version'] = 8
registration = next(item for item in component['contract_registrations'] if item['id'] == 'implementation_evidence')
registration['document_schema_version'] = 4
registration['version_history'].append({
    'version': 4,
    'change_type': 'breaking',
    'migration': 'docs/migrations/implementation-evidence-v3-to-v4.md',
})
migration_material = {
    'source': 'files/docs/migrations/implementation-evidence-v3-to-v4.md',
    'destination': 'docs/migrations/implementation-evidence-v3-to-v4.md',
    'ownership': 'managed',
}
if migration_material not in component['materials']:
    component['materials'].append(migration_material)
dump(component_path, component)

schema_path = 'components/lifecycle.implementation-evidence/files/schemas/implementation-evidence.schema.json'
schema = load(schema_path)
schema['properties']['schemaVersion']['const'] = 4
schema['properties']['mode']['enum'] = ['template', 'planning', 'product']
record_ids = schema['$defs']['requirement']['properties']['recordIds']
record_ids.pop('minItems', None)
schema['allOf'] = [
    {
        'if': {'properties': {'mode': {'const': 'template'}}, 'required': ['mode']},
        'then': {'properties': {
            'commands': {'maxItems': 0},
            'releaseGates': {'maxItems': 0},
            'records': {'maxItems': 0},
            'requirements': {'maxItems': 0},
        }},
    },
    {
        'if': {'properties': {'mode': {'const': 'planning'}}, 'required': ['mode']},
        'then': {'properties': {
            'commands': {'maxItems': 0},
            'releaseGates': {'maxItems': 0},
            'records': {'maxItems': 0},
            'requirements': {
                'minItems': 1,
                'items': {'properties': {'recordIds': {'maxItems': 0}}},
            },
        }},
    },
    {
        'if': {'properties': {'mode': {'const': 'product'}}, 'required': ['mode']},
        'then': {'properties': {
            'commands': {'minItems': 1},
            'releaseGates': {'minItems': 1},
            'requirements': {
                'minItems': 1,
                'items': {'properties': {'recordIds': {'minItems': 1}}},
            },
            'records': {'items': {'properties': {
                'implementationBoundary': {
                    'required': ['locator'],
                    'properties': {'status': {'const': 'verified'}},
                },
                'positiveEvidence': {'items': {
                    'required': ['kind', 'locator', 'commandId', 'expectedResult'],
                    'properties': {'status': {'enum': ['verified', 'deferred']}},
                }},
                'negativeEvidence': {'items': {
                    'required': ['kind', 'locator', 'commandId', 'expectedResult'],
                    'properties': {'status': {'enum': ['verified', 'deferred']}},
                }},
                'releaseGateIds': {'minItems': 1},
            }}},
        }},
    },
]
dump(schema_path, schema, compact=True)

seed_path = 'components/lifecycle.implementation-evidence/files/contracts/implementation-evidence.json'
seed = load(seed_path)
seed['schemaVersion'] = 4
dump(seed_path, seed)

migration = '''# implementation-evidence v3 to v4\n\nv4 adds a truthful `planning` state for capturing the stable product requirement ledger before implementation exists.\n\nMigration from an existing v3 document is deterministic:\n\n1. Change `schemaVersion` from `3` to `4`.\n2. Keep an existing `template` document otherwise unchanged.\n3. Keep an existing `product` document otherwise unchanged.\n\nUse the new `planning` mode only when product requirements are known but implementation records do not yet exist. In planning mode `commands`, `releaseGates`, and `records` are empty; `requirements` is non-empty; every requirement has a stable ID, description, non-empty `requiredPositiveProofKinds`, and an empty `recordIds` array. Preserve those requirement IDs when moving to product mode and connect them to the implemented records instead of replacing them with new IDs.\n\n`planning` is intentionally not release-ready. Release readiness accepts only `product` mode with fully verified required evidence.\n'''
(ROOT / 'components/lifecycle.implementation-evidence/files/docs/migrations/implementation-evidence-v3-to-v4.md').write_text(migration, encoding='utf-8')

# Generic implementation-evidence semantics.
validator_path = 'components/lifecycle.implementation-evidence/files/.template-composition/validators/validate_implementation_evidence.py'
new_traceability = r'''def requirement_traceability_errors(evidence: dict[str, Any]) -> list[str]:
    """Validate the stable requirement ledger and product requirement -> record edges."""

    mode = evidence.get("mode")
    requirements = evidence.get("requirements")
    if requirements is None:
        if mode in {"planning", "product"}:
            return [f"{mode} implementation-evidence requires a non-empty requirements ledger"]
        return []
    if not isinstance(requirements, list):
        return ["implementation-evidence requirements must be an array"]
    if mode in {"planning", "product"} and not requirements:
        return [f"{mode} implementation-evidence requires a non-empty requirements ledger"]

    records = evidence.get("records", [])
    if not isinstance(records, list):
        return ["implementation-evidence records must be an array"]
    records_by_id = {
        record.get("id"): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }

    errors: list[str] = []
    requirement_ids = [
        requirement.get("id")
        for requirement in requirements
        if isinstance(requirement, dict)
    ]
    for duplicate in sorted(_duplicates(requirement_ids)):
        errors.append(f"duplicate implementation-evidence requirement id: {duplicate}")

    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            errors.append(f"requirement {index}: must be an object")
            continue
        requirement_id = requirement.get("id")
        owner = f"requirement {requirement_id!r}"
        required_kinds = requirement.get("requiredPositiveProofKinds")
        if not isinstance(required_kinds, list) or not required_kinds:
            errors.append(
                f"{owner}: requiredPositiveProofKinds must contain at least one proof kind"
            )
            required_kinds = []
        record_refs = requirement.get("recordIds")
        if not isinstance(record_refs, list):
            errors.append(f"{owner}: recordIds must be an array")
            continue
        if mode == "planning":
            if record_refs:
                errors.append(
                    f"{owner}: planning requirement recordIds must stay empty until product implementation records exist"
                )
            continue
        if not record_refs:
            errors.append(f"{owner}: recordIds must contain at least one record")
            continue
        for duplicate in sorted(_duplicates(record_refs)):
            errors.append(f"{owner}: duplicate record reference: {duplicate}")
        for record_id in record_refs:
            record = records_by_id.get(record_id)
            if record is None:
                errors.append(f"{owner}: unknown implementation-evidence record {record_id}")
                continue
            positive = record.get("positiveEvidence")
            if not isinstance(positive, list) or not any(
                isinstance(proof, dict)
                and proof.get("status") in {"verified", "deferred"}
                for proof in positive
            ):
                errors.append(
                    f"{owner}: linked record {record_id} has no traceable positive evidence"
                )
            if required_kinds:
                if not isinstance(positive, list) or not any(
                    isinstance(proof, dict)
                    and proof.get("kind") in required_kinds
                    for proof in positive
                ):
                    errors.append(
                        f"{owner}: linked record {record_id} has no positive proof "
                        f"with a required kind ({', '.join(sorted(required_kinds))})"
                    )
            gates = record.get("releaseGateIds")
            if not isinstance(gates, list) or not gates:
                errors.append(
                    f"{owner}: linked record {record_id} has no release gate"
                )
    return errors'''
replace_block(validator_path, 'def requirement_traceability_errors', 'def release_readiness_errors', new_traceability)

replace_exact(
    validator_path,
    '''    errors = requirement_traceability_errors(evidence)\n    records = evidence.get("records", [])\n''',
    '''    mode = evidence.get("mode")\n    if mode != "product":\n        return [\n            "release readiness blocked: implementation-evidence mode "\n            f"{mode!r} is not 'product'"\n        ]\n\n    errors = requirement_traceability_errors(evidence)\n    records = evidence.get("records", [])\n''',
)
replace_exact(
    validator_path,
    '''    if mode == "template":\n        if commands or gates or records or requirements:\n            errors.append("template implementation evidence must be empty")\n        return errors\n    if mode != "product":\n        return [f"unsupported implementation-evidence mode: {mode!r}"]\n\n    errors.extend(requirement_traceability_errors(evidence))\n''',
    '''    if mode == "template":\n        if commands or gates or records or requirements:\n            errors.append("template implementation evidence must be empty")\n        return errors\n    if mode == "planning":\n        if commands or gates or records:\n            errors.append(\n                "planning implementation evidence may contain only the requirement ledger"\n            )\n        errors.extend(requirement_traceability_errors(evidence))\n        return errors\n    if mode != "product":\n        return [f"unsupported implementation-evidence mode: {mode!r}"]\n\n    errors.extend(requirement_traceability_errors(evidence))\n''',
)
replace_exact(
    validator_path,
    '''    if not args.release_readiness and isinstance(evidence, dict):\n        deferred = [\n''',
    '''    if not args.release_readiness and isinstance(evidence, dict):\n        if evidence.get("mode") == "planning":\n            print(\n                "Release readiness: NOT READY "\n                "(planning requirement ledger is not yet linked to implementation evidence)"\n            )\n        deferred = [\n''',
)

# Webapp planning semantics and worklist projection.
web_validator = 'components/artifact.webapp-core/files/scripts/validate_webapp_evidence.py'
replace_exact(
    web_validator,
    '''        if evidence.get("mode") == "template":\n            print("Webapp evidence coverage: template mode OK")\n            return 0\n        actual = actual_targets(evidence)\n''',
    '''        mode = evidence.get("mode")\n        if mode == "template":\n            print("Webapp evidence coverage: template mode OK")\n            return 0\n        if mode == "planning":\n            print("Webapp evidence coverage: planning mode; product target coverage pending")\n            return 0\n        if mode != "product":\n            raise ValueError(f"unsupported implementation-evidence mode: {mode!r}")\n        actual = actual_targets(evidence)\n''',
)

scaffold_path = 'components/artifact.webapp-core/files/scripts/scaffold_webapp_evidence.py'
new_project = r'''def _project_requirements(
    evidence: dict[str, Any],
    record_statuses: dict[str, str],
    records_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    requirements = evidence.get("requirements", [])
    if requirements is None:
        return []
    if not isinstance(requirements, list):
        raise ValueError("canonical implementation evidence requirements must be an array")

    mode = evidence.get("mode")
    projected: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise ValueError(f"canonical requirement {index} must be an object")
        requirement_id = requirement.get("id")
        description = requirement.get("description")
        record_ids = requirement.get("recordIds")
        if not isinstance(requirement_id, str) or not isinstance(description, str):
            raise ValueError(
                f"canonical requirement {index} must have id and description text"
            )
        if not isinstance(record_ids, list):
            raise ValueError(
                f"canonical requirement {requirement_id!r} must have a recordIds array"
            )
        item: dict[str, Any] = {
            "id": requirement_id,
            "description": description,
            "recordIds": list(record_ids),
            "status": "missing",
        }
        required_kinds = requirement.get("requiredPositiveProofKinds")
        if not isinstance(required_kinds, list) or not required_kinds:
            raise ValueError(
                f"canonical requirement {requirement_id!r} has invalid proof kinds"
            )
        item["requiredPositiveProofKinds"] = list(required_kinds)

        if mode == "planning":
            if record_ids:
                raise ValueError(
                    f"planning requirement {requirement_id!r} must leave recordIds empty"
                )
            projected.append(item)
            continue

        if not record_ids:
            raise ValueError(
                f"canonical requirement {requirement_id!r} must reference records"
            )
        statuses = [
            record_statuses.get(record_id, "missing")
            for record_id in record_ids
            if isinstance(record_id, str)
        ]
        if len(statuses) != len(record_ids):
            raise ValueError(
                f"canonical requirement {requirement_id!r} has a non-text record reference"
            )
        item["status"] = _status_union(statuses)
        declared_kinds = {kind for kind in required_kinds if isinstance(kind, str)}
        for record_id_value in record_ids:
            linked_record = records_by_id.get(record_id_value)
            if linked_record is None:
                continue
            artifact_kinds = set(
                artifact_required_proof_kinds(linked_record.get("target"))
            )
            if artifact_kinds and declared_kinds.isdisjoint(artifact_kinds):
                item["status"] = "missing"
            positive = linked_record.get("positiveEvidence")
            if not isinstance(positive, list) or not any(
                isinstance(proof, dict) and proof.get("kind") in declared_kinds
                for proof in positive
            ):
                item["status"] = "missing"
        projected.append(item)
    return sorted(projected, key=lambda item: item["id"])'''
replace_block(scaffold_path, 'def _project_requirements', 'def _requirement_ledger_status', new_project)
replace_block(
    scaffold_path,
    'def _requirement_ledger_status',
    'def _artifact_proof_requirements',
    '''def _requirement_ledger_status(\n    evidence: dict[str, Any], projected_requirements: list[dict[str, Any]]\n) -> str:\n    mode = evidence.get("mode")\n    if mode == "template":\n        return "not-applicable"\n    if mode in {"planning", "product"}:\n        return "verified" if projected_requirements else "missing"\n    return "missing"''',
)
replace_exact(scaffold_path, '"formatVersion": 2,', '"formatVersion": 3,')

# Component bumps for managed behavior changes.
web_component = load('components/artifact.webapp-core/component.json')
web_component['version'] = 11
dump('components/artifact.webapp-core/component.json', web_component)
state_component = load('components/lifecycle.composition-state/component.json')
state_component['version'] = 6
dump('components/lifecycle.composition-state/component.json', state_component)
release_component = load('components/lifecycle.release-execution/component.json')
release_component['version'] = 4
dump('components/lifecycle.release-execution/component.json', release_component)

# Run generic implementation-evidence validation for template/planning/product; the validator owns mode semantics.
registry_path = 'components/lifecycle.composition-state/files/.template-composition/validation-registry.json'
registry = load(registry_path)
impl_entry = next(item for item in registry['validators'] if item['id'] == 'implementation-evidence')
impl_entry.pop('when', None)
impl_entry['purpose'] = 'Validate template, planning, and product implementation-evidence semantics, requirement ledgers, proof commands, and release-gate coverage.'
dump(registry_path, registry)

# Planning evidence can coexist with template release-execution because no authoritative commands exist yet.
release_validator = 'components/lifecycle.release-execution/files/.template-composition/validators/validate_release_execution.py'
replace_exact(
    release_validator,
    '''        if implementation_mode != "template":\n            errors.append(\n                "product implementation evidence requires product release execution"\n            )\n        return errors\n''',
    '''        if implementation_mode == "product":\n            errors.append(\n                "product implementation evidence requires product release execution"\n            )\n        elif implementation_mode not in {"template", "planning"}:\n            errors.append(\n                f"unsupported implementation-evidence mode: {implementation_mode!r}"\n            )\n        return errors\n''',
)

# Managed guidance.
arch_path = 'components/lifecycle.implementation-evidence/files/docs/architecture/implementation-evidence.md'
arch = (ROOT / arch_path).read_text(encoding='utf-8')
planning_section = '''\n## Planning requirement ledger\n\nUse `mode: "planning"` after explicit product requirements are known but before implementation records exist. Planning mode is deliberately narrow: `commands`, `releaseGates`, and `records` stay empty; `requirements` is non-empty; every requirement has a stable ID, description, empty `recordIds`, and non-empty `requiredPositiveProofKinds`. This gives coding agents a machine-readable requirement inventory before coding without pretending that implementation or proof already exists.\n\nPreserve the requirement IDs when moving to `product`. At that point connect `recordIds`, authoritative commands, positive/negative proofs, and release gates. `template` means no product requirement claim is active; `planning` means requirements are explicit but implementation is incomplete; `product` means the implementation/evidence graph is active. Only product mode can pass release readiness.\n'''
if '## Planning requirement ledger' not in arch:
    (ROOT / arch_path).write_text(arch.rstrip() + planning_section + '\n', encoding='utf-8')

release_doc = ROOT / 'components/lifecycle.release-execution/files/docs/architecture/release-execution.md'
rtext = release_doc.read_text(encoding='utf-8')
if 'Planning implementation evidence' not in rtext:
    rtext += '\n\nPlanning implementation evidence has no authoritative proof commands yet, so `release-execution` remains in template mode while implementation evidence is in planning mode. Product implementation evidence requires product release-execution bindings.\n'
    release_doc.write_text(rtext, encoding='utf-8')

replace_exact(
    'components/artifact.webapp-core/files/docs/architecture/validation-toolchain.md',
    'This separation is intentional: template mode requires an empty canonical evidence document, while product mode requires fully verified records. Fill the generated record skeletons with concrete implementation locators, proof metadata, commands, and release gates before placing them in the canonical product evidence document.',
    'This separation is intentional: template mode makes no product requirement claim; planning mode stores the stable requirement ledger before implementation records exist; product mode activates the implementation/evidence graph. Capture explicit caller-visible requirements in planning mode before coding, preserve those IDs, then fill generated record skeletons with concrete implementation locators, proof metadata, commands, and release gates when moving to product mode.',
)
replace_exact(
    'components/artifact.webapp-core/files/TEMPLATE.md',
    'Then switch `contracts/implementation-evidence.json` to product mode and provide one fully verified record for every current Webapp target.',
    'Capture explicit caller-visible requirements first in `planning` mode with stable IDs, empty `recordIds`, and their required positive proof kinds. Preserve those IDs. Then switch `contracts/implementation-evidence.json` to product mode and provide one fully verified record for every current Webapp target, linking the planned requirements to the records that implement them.',
)

# Consumer guidance and Japanese translation.
replace_exact(
    'docs/consumer-guide.md',
    '5. Add authoritative product test commands and positive/negative proofs, then switch `contracts/implementation-evidence.json` from `template` to `product` mode only when the claimed implementation boundaries and evidence actually exist.',
    '5. Before product coding, switch `contracts/implementation-evidence.json` from `template` to `planning` and capture the stable caller-visible requirement IDs, descriptions, empty `recordIds`, and `requiredPositiveProofKinds`. Preserve those IDs. After implementation boundaries and real proof definitions exist, connect the records/commands/gates and switch from `planning` to `product`.',
)
replace_exact(
    'translations/ja/docs/consumer-guide.md',
    '5. authoritative product test commands と positive/negative proofs を追加し、主張する implementation boundaries と evidence が実際に存在する場合にだけ `contracts/implementation-evidence.json` を `template` mode から `product` mode に切り替えます。',
    '5. product coding の前に `contracts/implementation-evidence.json` を `template` から `planning` mode に切り替え、stable な caller-visible requirement ID、description、空の `recordIds`、`requiredPositiveProofKinds` を記録します。これらの ID は維持します。implementation boundary と real proof definition ができた後で records / commands / gates を接続し、`planning` から `product` に切り替えます。',
)

# Clean-room prompt now names the supported pre-coding state explicitly.
prompt_path = 'examples/evaluations/small-model-clean-room-field-log.txt'
replace_exact(
    prompt_path,
    '2. Create a stable machine-readable requirement inventory before claiming implementation completion. Preserve one stable ID per explicit caller-visible requirement. Do not collapse unrelated requirements into one catch-all requirement.\n',
    '2. Before product coding, use the current implementation-evidence planning state to create a stable machine-readable requirement inventory. Keep commands, release gates, and implementation records empty at this stage; give each explicit caller-visible requirement its stable ID, description, empty recordIds, and requiredPositiveProofKinds. Preserve those IDs when later linking product records. Do not collapse unrelated requirements into one catch-all requirement.\n',
)

# Focused planning-state acceptance.
planning_test = r'''from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
SCHEMA = ROOT / "components" / "lifecycle.implementation-evidence" / "files" / "schemas" / "implementation-evidence.schema.json"
PROMPT = ROOT / "examples" / "evaluations" / "small-model-clean-room-field-log.txt"


class ImplementationEvidencePlanningTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def run_python(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, *args], cwd=cwd, text=True, capture_output=True, check=False)

    def planning_document(self) -> dict:
        return {
            "$schema": "../schemas/implementation-evidence.schema.json",
            "schemaVersion": 4,
            "mode": "planning",
            "commands": [],
            "releaseGates": [],
            "records": [],
            "requirements": [
                {
                    "id": "REQ-PLAN-BROWSER-FILTER",
                    "description": "The browser filters caller-visible records by severity.",
                    "recordIds": [],
                    "requiredPositiveProofKinds": ["end-to-end-test"],
                },
                {
                    "id": "REQ-PLAN-CLI-FILTER",
                    "description": "The packaged CLI filters caller-visible records by severity.",
                    "recordIds": [],
                    "requiredPositiveProofKinds": ["integration-test"],
                },
            ],
        }

    def materialize(self, root: Path) -> Path:
        target = root / "consumer"
        config = root / "composition.json"
        self.write_json(config, {"schema_version": 1, "recipe": "webapp", "components": {"include": [], "exclude": []}, "parameters": {}})
        result = self.run_python(ROOT, str(COMPOSER), "apply", "--config", str(config), "--target", str(target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return target

    def test_schema_and_validators_accept_truthful_planning_but_release_readiness_rejects_it(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        planning = self.planning_document()
        validator.validate(planning)

        bad = json.loads(json.dumps(planning))
        bad["requirements"][0]["recordIds"] = ["premature-record"]
        self.assertTrue(list(validator.iter_errors(bad)))

        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            evidence_path = target / "contracts" / "implementation-evidence.json"
            self.write_json(evidence_path, planning)

            generic = self.run_python(target, ".template-composition/validators/validate_implementation_evidence.py", ".")
            self.assertEqual(generic.returncode, 0, generic.stdout + generic.stderr)
            self.assertIn("planning requirement ledger", generic.stdout)
            self.assertIn("Release readiness: NOT READY", generic.stdout)

            webapp = self.run_python(target, "scripts/validate_webapp_evidence.py")
            self.assertEqual(webapp.returncode, 0, webapp.stdout + webapp.stderr)
            self.assertIn("planning mode", webapp.stdout)

            scaffold = self.run_python(target, "scripts/scaffold_webapp_evidence.py")
            self.assertEqual(scaffold.returncode, 0, scaffold.stdout + scaffold.stderr)
            worklist = json.loads(scaffold.stdout)
            self.assertEqual(worklist["formatVersion"], 3)
            self.assertEqual(worklist["requirementLedgerStatus"], "verified")
            self.assertEqual(worklist["status"], "missing")
            self.assertEqual([item["id"] for item in worklist["requirements"]], ["REQ-PLAN-BROWSER-FILTER", "REQ-PLAN-CLI-FILTER"])
            self.assertTrue(all(item["status"] == "missing" for item in worklist["requirements"]))
            self.assertTrue(all(item["recordIds"] == [] for item in worklist["requirements"]))

            readiness = self.run_python(target, ".template-composition/validators/validate_implementation_evidence.py", ".", "--release-readiness")
            self.assertNotEqual(readiness.returncode, 0)
            self.assertIn("mode 'planning' is not 'product'", readiness.stderr)

            planning["requirements"][1]["id"] = planning["requirements"][0]["id"]
            planning["requirements"][1]["description"] = "Different text, same stable ID."
            self.write_json(evidence_path, planning)
            duplicate = self.run_python(target, ".template-composition/validators/validate_implementation_evidence.py", ".")
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("duplicate implementation-evidence requirement id", duplicate.stderr)

    def test_template_is_not_release_ready_and_prompt_uses_planning_before_coding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize(Path(temp_dir))
            readiness = self.run_python(target, ".template-composition/validators/validate_implementation_evidence.py", ".", "--release-readiness")
            self.assertNotEqual(readiness.returncode, 0)
            self.assertIn("mode 'template' is not 'product'", readiness.stderr)

        prompt = PROMPT.read_text(encoding="utf-8")
        self.assertIn("Before product coding", prompt)
        self.assertIn("implementation-evidence planning state", prompt)
        self.assertIn("empty recordIds", prompt)
        self.assertIn("requiredPositiveProofKinds", prompt)
        self.assertIn("Preserve those IDs", prompt)


if __name__ == "__main__":
    unittest.main()
'''
(ROOT / 'tests/test_implementation_evidence_planning.py').write_text(planning_test, encoding='utf-8')

# Update direct scaffold format/schema expectations in the central acceptance.
replace_exact('tests/test_webapp_evidence_scaffold.py', 'self.assertEqual(worklist["formatVersion"], 2)', 'self.assertEqual(worklist["formatVersion"], 3)')
replace_exact('tests/test_webapp_evidence_scaffold.py', '"schemaVersion": 3,\n                    "mode": "product",', '"schemaVersion": 4,\n                    "mode": "product",')

# Translation binding for the changed canonical consumer guide.
manifest_path = ROOT / 'translations/manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
for entry in manifest['translations']:
    if entry['canonical'] == 'docs/consumer-guide.md':
        entry['canonical_blob_sha'] = subprocess.check_output(['git', 'hash-object', 'docs/consumer-guide.md'], text=True).strip()
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

# Compile touched Python sources without producing bytecode.
for path in (
    validator_path,
    web_validator,
    scaffold_path,
    release_validator,
    'tests/test_implementation_evidence_planning.py',
    'tests/test_webapp_evidence_scaffold.py',
):
    compile((ROOT / path).read_text(encoding='utf-8'), path, 'exec')

print('planning requirement-ledger patch applied')
