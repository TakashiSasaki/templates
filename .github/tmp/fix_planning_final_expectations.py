from pathlib import Path

replacements = {
    "tests/test_implementation_evidence_planning.py": [
        (
            'Path(temp_dir), include=["lifecycle.release-execution"]',
            'Path(temp_dir), include=["lifecycle.release-bundle"]',
        ),
    ],
    "tests/test_small_model_clean_room_evaluation_prompt.py": [
        (
            'self.assertIn("before claiming implementation completion", self.text)',
            'self.assertIn("before the implemented-product milestone can be claimed", self.text)',
        ),
    ],
    "tests/test_selected_component_validation.py": [
        (
            '"Implementation evidence semantics: OK"',
            '"Implementation evidence validation: OK"',
        ),
    ],
}

for raw_path, changes in replacements.items():
    path = Path(raw_path)
    text = path.read_text(encoding="utf-8")
    for old, new in changes:
        count = text.count(old)
        expected = 2 if raw_path.endswith("test_selected_component_validation.py") else 1
        if count != expected:
            raise SystemExit(
                f"{raw_path}: expected {expected} occurrence(s) of {old!r}, found {count}"
            )
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"updated {raw_path}")
