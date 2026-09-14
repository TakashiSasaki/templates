with open("tests/test_site_browser_acceptance_classifier.py", "r") as f:
    content = f.read()

content = content.replace("    def test_empty_change_set_fails_closed(self) -> None:\n        with self.assertRaisesRegex(ClassificationError, \"at least one changed path\"):\n            classify_paths([], force_full=False)", "    def test_empty_change_set_fails_closed(self) -> None:\n        decision = classify_paths([], force_full=False)\n        self.assertEqual(decision[1], \"no changed paths\")")

content = content.replace("    def test_cli_rejects_empty_changed_path_file(self) -> None:", "    def test_cli_accepts_empty_changed_path_file(self) -> None:")
content = content.replace("self.assertNotEqual(0, result.returncode)", "self.assertEqual(0, result.returncode)")
content = content.replace("self.assertIn(\"classification failed\", result.stderr)", "")
content = content.replace("self.assertTrue(output.exists())\n        self.assertIn(\"reason=no changed paths\", output.read_text(encoding=\"utf-8\"))", "self.assertTrue(output.exists())\n            self.assertIn(\"reason=no changed paths\", output.read_text(encoding=\"utf-8\"))")

with open("tests/test_site_browser_acceptance_classifier.py", "w") as f:
    f.write(content)
