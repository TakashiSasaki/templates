"""Integration regressions for independent reference adoption and projections."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import yaml
from scripts import render_reference_consumer as reference
from scripts import site_website_contract as website

ROOT = Path(__file__).resolve().parents[1]


class ReferenceConsumerTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "site"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        return root

    def test_projection_is_derived_and_publication_is_independent(self):
        root = self.fixture()
        before = reference.project(root)
        lock_bytes = (root / ".template-composition/lock.json").read_bytes()
        policy_bytes = (root / ".agent-policy.lock").read_bytes()
        publication = json.loads((root / "publication-sources.json").read_text())
        publication["publications"]["composition"]["revision"] = "a" * 40
        (root / "publication-sources.json").write_text(json.dumps(publication))
        after = reference.project(root)
        self.assertEqual(before["composition"], after["composition"])
        self.assertEqual(before["policy"], after["policy"])
        self.assertNotEqual(before["publication"], after["publication"])
        self.assertEqual(lock_bytes, (root / ".template-composition/lock.json").read_bytes())
        self.assertEqual(policy_bytes, (root / ".agent-policy.lock").read_bytes())

    def test_policy_configuration_is_not_a_publication_or_product_pin(self):
        root = self.fixture()
        before = reference.project(root)
        path = root / ".agent-policy.yml"
        policy = yaml.safe_load(path.read_text())
        policy["toolchain"]["revision"] = "b" * 40
        path.write_text(yaml.safe_dump(policy))
        after = reference.project(root)
        self.assertEqual(before["composition"], after["composition"])
        self.assertEqual(before["publication"], after["publication"])
        self.assertNotEqual(before["policy"], after["policy"])

    def test_managed_tampering_fails_but_site_schema_and_seed_remain_consumer_owned(self):
        root = self.fixture()
        validator = ROOT / ".template-composition/validate_composition.py"
        def validate():
            return subprocess.run([sys.executable, str(validator), str(root)], capture_output=True, text=True)
        self.assertEqual(validate().returncode, 0)
        (root / "schemas/agent-bootstrap.schema.json").write_text("consumer change")
        with (root / "contracts/routes.json").open("a") as handle:
            handle.write("\n")
        self.assertEqual(validate().returncode, 0)
        with (root / "schemas/routes.schema.json").open("a") as handle:
            handle.write("\n")
        self.assertNotEqual(validate().returncode, 0)

    def test_current_discovery_and_website_worksheets_are_fresh(self):
        for path, content in reference.outputs(ROOT).items():
            self.assertEqual((ROOT / path).read_text(), content, path)
        for path, value in website.documents(ROOT).items():
            self.assertEqual(json.loads((ROOT / path).read_text()), value, path)
        manifest = yaml.safe_load((ROOT / ".agent-policy.yml").read_text())
        workflow = yaml.safe_load((ROOT / ".github/workflows/check-agent-policy.yml").read_text())
        actions = [s.get("uses", "") for s in workflow["jobs"]["policy"]["steps"]]
        self.assertIn(manifest["toolchain"]["repository"] + "@" + manifest["toolchain"]["revision"], actions)
        adapter = json.loads((ROOT / ".agents/skills/pr-merge-gate/source.json").read_text())
        self.assertEqual(adapter["revision"], manifest["toolchain"]["revision"])


if __name__ == "__main__":
    unittest.main()
