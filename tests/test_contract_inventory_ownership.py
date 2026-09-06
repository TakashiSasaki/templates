"""A mature consumer keeps unrelated files without weakening managed closure."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContractOwnershipTests(unittest.TestCase):
    def test_existing_consumer_files_are_preserved_but_registered_files_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "product"
            for relative in ("schemas/product.schema.json", "contracts/product.json", "docs/migrations/product.md"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("consumer-owned bytes\n")
            config = Path(tmp) / "intent.json"
            config.write_text(json.dumps({"schema_version":1,"recipe":"website","components":{"include":[],"exclude":[]},"parameters":{}}))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/compose.py"), "apply", "--target", str(root), "--config", str(config)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            def validate():
                return subprocess.run([sys.executable, str(root / ".template-composition/validators/validate_contract_evolution.py"), str(root)], capture_output=True, text=True)
            result = validate()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for relative in ("schemas/product.schema.json", "contracts/product.json", "docs/migrations/product.md"):
                self.assertEqual((root / relative).read_text(), "consumer-owned bytes\n")
            registered = root / "schemas/routes.schema.json"
            content = registered.read_bytes()
            registered.unlink()
            self.assertNotEqual(validate().returncode, 0)
            registered.write_bytes(content)
            lock_path = root / ".template-composition/lock.json"
            lock = json.loads(lock_path.read_text())
            lock["files"].append({"destination":"schemas/product.schema.json"})
            lock_path.write_text(json.dumps(lock))
            result = validate()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unregistered contract schema", result.stderr)


if __name__ == "__main__":
    unittest.main()
