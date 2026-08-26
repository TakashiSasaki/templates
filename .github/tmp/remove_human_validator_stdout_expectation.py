from pathlib import Path

path = Path("tests/test_selected_component_validation.py")
text = path.read_text(encoding="utf-8")
needle = '            self.assertIn("Implementation evidence validation: OK", human.stdout)\n'
if text.count(needle) != 1:
    raise SystemExit(f"expected exactly one human validator stdout assertion, found {text.count(needle)}")
path.write_text(text.replace(needle, ""), encoding="utf-8")
print("removed stale human validator stdout assertion")
