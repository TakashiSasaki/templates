from pathlib import Path

path = Path("tests/test_selected_component_validation.py")
text = path.read_text(encoding="utf-8")
old = '''            self.assertEqual(checks["implementation-evidence"]["status"], "deferred")
            self.assertIn("TEMPLATE mode", checks["implementation-evidence"]["stderr"])
            self.assertIn(
                "no product implementation claim",
                checks["implementation-evidence"]["stderr"],
            )
            self.assertTrue(
                all(
                    check["status"] == "passed"
                    for check_id, check in checks.items()
                    if check_id != "implementation-evidence"
                )
            )
'''
new = '''            self.assertEqual(checks["implementation-evidence"]["status"], "passed")
            self.assertIn(
                "Implementation evidence semantics: OK",
                checks["implementation-evidence"]["stdout"],
            )
            self.assertTrue(all(check["status"] == "passed" for check in checks.values()))
'''
if text.count(old) != 1:
    raise SystemExit("minimal Webapp template evidence expectation changed")
text = text.replace(old, new)
old_human = '''            self.assertIn("DEFERRED: implementation-evidence", human.stdout)
            self.assertIn("TEMPLATE mode", human.stdout)
            self.assertIn("no product implementation claim", human.stdout)
'''
new_human = '''            self.assertIn("PASSED: implementation-evidence", human.stdout)
            self.assertIn("Implementation evidence semantics: OK", human.stdout)
'''
if text.count(old_human) != 1:
    raise SystemExit("human template evidence expectation changed")
text = text.replace(old_human, new_human)
if text.count('checks["implementation-evidence"]["status"], "deferred"') != 4:
    raise SystemExit("expected four remaining deferred status assertions")
text = text.replace(
    'checks["implementation-evidence"]["status"], "deferred"',
    'checks["implementation-evidence"]["status"], "passed"',
)
old_release = '''            self.assertTrue(
                all(
                    check["status"] == "passed"
                    for check_id, check in checks.items()
                    if check_id != "implementation-evidence"
                )
            )
'''
if text.count(old_release) != 1:
    raise SystemExit("release-ready template all-pass expectation changed")
text = text.replace(
    old_release,
    '            self.assertTrue(all(check["status"] == "passed" for check in checks.values()))\n',
)
path.write_text(text, encoding="utf-8")
print("selected-component template evidence expectations migrated")
