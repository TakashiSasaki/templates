from pathlib import Path

path = Path("scripts/smoke_test_materialized_validation.py")
text = path.read_text(encoding="utf-8")
old = '''        evidence_check = cold_checks.get("implementation-evidence")
        if evidence_check is None or evidence_check.get("status") != "deferred":
            raise RuntimeError(
                f"template implementation evidence was not explicitly deferred: {cold}"
            )
        evidence_message = evidence_check.get("stderr", "")
        if "TEMPLATE mode" not in evidence_message or "no product implementation claim" not in evidence_message:
            raise RuntimeError(
                f"template implementation evidence lacks maturity guidance: {evidence_check}"
            )
'''
new = '''        evidence_check = cold_checks.get("implementation-evidence")
        if evidence_check is None or evidence_check.get("status") != "passed":
            raise RuntimeError(
                f"template implementation evidence was not semantically validated: {cold}"
            )
        evidence_message = evidence_check.get("stdout", "")
        if "Implementation evidence validation: OK" not in evidence_message:
            raise RuntimeError(
                f"template implementation evidence lacks semantic validation result: {evidence_check}"
            )
'''
if text.count(old) != 1:
    raise SystemExit("materialized template evidence expectation changed")
path.write_text(text.replace(old, new), encoding="utf-8")
print("materialized template expectation migrated")
