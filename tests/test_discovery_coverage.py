"""Discovery is derived from real catalogs and Git, without a second source list."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "local_discovery", ROOT / "scripts/check_discovery.py"
)
discovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discovery)


class DiscoveryCoverageTests(unittest.TestCase):
    def fixture(self, root):
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "docs").mkdir()
        (root / "README.md").write_text("# Example\n")
        (root / "index.md").write_text("# Start\n\n[Materials](discovery/index.md)\n")
        (root / "docs/publication-catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "documents": [{"id": "home", "source": "README.md", "home": True}],
                    "assets": [],
                }
            )
        )
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        self.assertTrue(discovery.check(root, write=True)["valid"])

    def test_real_authority_catalog_is_exact_and_reachable(self):
        report = discovery.check(ROOT)
        self.assertTrue(report["valid"], "\n".join(report["errors"]))
        self.assertIn("docs/publication-catalog.json", report["routes"])

    def test_catalog_addition_and_removal_have_no_second_membership_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            catalog = root / "docs/publication-catalog.json"
            data = json.loads(catalog.read_text())
            data["documents"].append({"id": "new", "source": "docs/new.md"})
            (root / "docs/new.md").write_text("# New source\n")
            catalog.write_text(json.dumps(data))
            self.assertFalse(discovery.check(root)["valid"])
            report = discovery.check(root, write=True)
            self.assertTrue(report["valid"], report["errors"])
            self.assertEqual(
                report["routes"]["docs/new.md"],
                ["index.md", "discovery/index.md", "docs/new.md"],
            )
            data["documents"].pop()
            catalog.write_text(json.dumps(data))
            self.assertFalse(discovery.check(root)["valid"])
            self.assertTrue(discovery.check(root, write=True)["valid"])
            self.assertNotIn("docs/new.md", (root / "discovery/index.md").read_text())

    def test_disconnected_inventory_broken_link_and_extra_entry_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            index = root / "index.md"
            original = index.read_text()
            index.write_text("# Start\n[Directory](docs/)\n")
            self.assertFalse(discovery.check(root)["valid"])
            index.write_text(original + "\n[Missing](missing.md)\n")
            self.assertFalse(discovery.check(root)["valid"])
            index.write_text(original)
            with (root / "discovery/index.md").open("a") as stream:
                stream.write("\n[Spurious canonical entry](../README.md)\n")
            self.assertFalse(discovery.check(root)["valid"])
            self.assertTrue(discovery.check(root, write=True)["valid"])

    def test_unsafe_or_duplicate_canonical_entries_are_not_discoverable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            catalog = root / "docs/publication-catalog.json"
            data = json.loads(catalog.read_text())
            data["documents"].append(data["documents"][0])
            catalog.write_text(json.dumps(data))
            with self.assertRaises(discovery.DiscoveryError):
                discovery.check(root)
            data["documents"].pop()
            data["documents"][0]["source"] = "../outside.md"
            catalog.write_text(json.dumps(data))
            with self.assertRaises(discovery.DiscoveryError):
                discovery.check(root)
            data["documents"][0]["source"] = "alias.md"
            catalog.write_text(json.dumps(data))
            (root / "alias.md").symlink_to(root / "README.md")
            with self.assertRaises(discovery.DiscoveryError):
                discovery.check(root)

    def test_markdown_links_ignore_examples_and_follow_references(self):
        text = """# Start
[Inline](docs/a.md "title") and [reference][b].
[angle](<docs/a b.md>) and [parentheses](docs/a(b).md).
[b]: docs/b.md
`[example](missing.md)`
```md
[example](missing2.md)
```
<!-- [hidden](missing3.md) -->
"""
        self.assertEqual(
            set(discovery.links(text)),
            {"docs/a.md", "docs/b.md", "docs/a b.md", "docs/a(b).md"},
        )

    def test_existing_product_catalogs_and_git_supply_nonpublication_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            for directory in [
                "catalog",
                "components/example",
                "recipes",
                "src",
                "tests",
                ".github/workflows",
            ]:
                (root / directory).mkdir(parents=True, exist_ok=True)
            (root / "catalog/catalog.json").write_text(
                json.dumps({"components": ["example"], "recipes": ["minimal"]})
            )
            for name in [
                "components/example/component.json",
                "recipes/minimal.json",
                "src/main.py",
                "tests/check.py",
                ".github/workflows/check.yml",
            ]:
                (root / name).write_text("{}")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            report = discovery.check(root, write=True)
            self.assertTrue(report["valid"], report["errors"])
            for path in [
                "components/example/component.json",
                "recipes/minimal.json",
                "src",
                "tests",
                ".github",
            ]:
                self.assertIn(path, report["routes"])


if __name__ == "__main__":
    unittest.main()
