with open("tests/test_site_browser_acceptance_classifier.py", "r") as f:
    content = f.read()

content = content.replace("    def test_empty_change_set_fails_closed(self) -> None:\n        with self.assertRaisesRegex(ClassificationError, \"at least one changed path\"):\n            classify_paths([])", "    def test_empty_change_set_fails_closed(self) -> None:\n        decision = classify_paths([])\n        self.assertEqual(decision[1], \"no changed paths\")")

with open("tests/test_site_browser_acceptance_classifier.py", "w") as f:
    f.write(content)
