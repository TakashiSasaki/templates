from pathlib import Path

schema_path = Path("components/lifecycle.implementation-evidence/files/schemas/implementation-evidence.schema.json")
schema = schema_path.read_text(encoding="utf-8")
replacements = [
    (
        '"required":["id","description","targets","recordIds","requiredPositiveProofKinds"]',
        '"required":["id","description","recordIds","requiredPositiveProofKinds"]',
    ),
    (
        '"items":{"properties":{"recordIds":{"maxItems":0}}}',
        '"items":{"required":["targets"],"properties":{"recordIds":{"maxItems":0}}}',
    ),
]
for old, new in replacements:
    if schema.count(old) != 1:
        raise SystemExit(f"schema guard failed for {old!r}: count={schema.count(old)}")
    schema = schema.replace(old, new)
schema_path.write_text(schema, encoding="utf-8")

validator_path = Path("components/lifecycle.implementation-evidence/files/.template-composition/validators/validate_implementation_evidence.py")
validator = validator_path.read_text(encoding="utf-8")
old = '''        targets = requirement.get("targets")
        if not isinstance(targets, list) or not targets:
            errors.append(f"{owner}: targets must contain at least one contract target")
            targets = []
        target_signatures = [_target_signature(target) for target in targets]
'''
new = '''        targets = requirement.get("targets")
        if mode == "planning":
            if not isinstance(targets, list) or not targets:
                errors.append(
                    f"{owner}: planning targets must contain at least one contract target"
                )
                targets = []
        elif targets is None:
            targets = []
        elif not isinstance(targets, list) or not targets:
            errors.append(
                f"{owner}: product targets, when present, must contain at least one contract target"
            )
            targets = []
        target_signatures = [_target_signature(target) for target in targets]
'''
if validator.count(old) != 1:
    raise SystemExit(f"validator guard failed: count={validator.count(old)}")
validator = validator.replace(old, new)
validator_path.write_text(validator, encoding="utf-8")
