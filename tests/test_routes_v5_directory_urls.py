import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "components/foundation.web/files"


class DirectoryRoutesTests(unittest.TestCase):
    def test_canonical_and_alias_paths_preserve_directory_identity(self):
        schema = json.loads((FILES / "schemas/routes.schema.json").read_text())
        validator = Draft202012Validator(schema)
        for path in ("/", "/guide", "/guide/", "/nested/guide/", "/Account.HTML/"):
            for field in ("path", "aliases"):
                with self.subTest(path=path, field=field):
                    doc = json.loads((FILES / "contracts/routes.json").read_text())
                    doc["routes"][0][field] = [path] if field == "aliases" else path
                    self.assertEqual(list(validator.iter_errors(doc)), [])

    def test_unsafe_and_ambiguous_paths_remain_invalid(self):
        validator = Draft202012Validator(json.loads((FILES / "schemas/routes.schema.json").read_text()))
        for path in ("//", "/a//", "/a//b/", "/./", "/../", "/a/../", "/a/./", "/a\\b/", "/a?b/", "/a#b/", "/%2f/", "/café/", "/a/\n"):
            with self.subTest(path=path):
                doc = json.loads((FILES / "contracts/routes.json").read_text())
                doc["routes"][0]["path"] = path
                self.assertTrue(list(validator.iter_errors(doc)))


if __name__ == "__main__":
    unittest.main()
