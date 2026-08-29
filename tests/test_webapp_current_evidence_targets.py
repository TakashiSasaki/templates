from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_MODULE = (
    ROOT
    / "components"
    / "artifact.webapp-core"
    / "files"
    / "scripts"
    / "webapp_evidence_targets.py"
)


def load_target_module():
    module = types.ModuleType("webapp_evidence_targets_under_test")
    module.__file__ = str(TARGET_MODULE)
    source = TARGET_MODULE.read_text(encoding="utf-8")
    exec(compile(source, str(TARGET_MODULE), "exec"), module.__dict__)
    return module


_targets = load_target_module()
allowed_targets = _targets.allowed_targets
expected_targets = _targets.expected_targets
target_key = _targets.target_key


class WebappCurrentEvidenceTargetTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def fixture(self, root: Path) -> None:
        self.write_json(
            root / "contracts" / "browser-identity.json",
            {"favicon": {"relation": "icon"}},
        )
        self.write_json(
            root / "contracts" / "surfaces.json",
            {"surfaces": [{"id": "main"}]},
        )
        self.write_json(
            root / "contracts" / "routes.json",
            {"routes": [{"id": "home"}]},
        )
        self.write_json(
            root / "contracts" / "ui-states.json",
            {"states": [{"id": "ready"}]},
        )
        self.write_json(
            root / "contracts" / "viewports.json",
            {
                "viewports": [{"id": "compact"}],
                "inputCapabilities": ["keyboard", "pointer"],
            },
        )
        self.write_json(
            root / "contracts" / "manifest.json",
            {
                "contracts": [
                    {
                        "id": "browser_identity",
                        "versionHistory": [{"version": 1}],
                    },
                    {
                        "id": "routes",
                        "versionHistory": [
                            {"version": 1},
                            {"version": 2},
                            {"version": 3},
                        ],
                    },
                    {
                        "id": "surfaces",
                        "versionHistory": [{"version": 1}, {"version": 2}],
                    },
                    {
                        "id": "ui_states",
                        "versionHistory": [{"version": 1}, {"version": 2}],
                    },
                    {
                        "id": "viewports",
                        "versionHistory": [{"version": 1}],
                    },
                    {
                        "id": "other_contract",
                        "versionHistory": [{"version": 1}, {"version": 2}],
                    },
                ]
            },
        )

    def test_required_targets_cover_only_current_product_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root)
            required = expected_targets(root)

            self.assertTrue(required)
            self.assertTrue(
                all(target["kind"] == "contract-item" for target in required),
                required,
            )
            self.assertEqual(
                {target_key(target) for target in required},
                {
                    ("contract-item", "browser_identity", "favicon", "favicon"),
                    ("contract-item", "surfaces", "surface", "main"),
                    ("contract-item", "routes", "route", "home"),
                    ("contract-item", "ui_states", "ui-state", "ready"),
                    ("contract-item", "viewports", "viewport", "compact"),
                    ("contract-item", "viewports", "input-capability", "keyboard"),
                    ("contract-item", "viewports", "input-capability", "pointer"),
                },
            )

    def test_allowed_targets_add_only_registered_webapp_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root)
            required = {target_key(target) for target in expected_targets(root)}
            allowed = {target_key(target) for target in allowed_targets(root)}

            self.assertTrue(required < allowed)
            self.assertEqual(
                allowed - required,
                {
                    ("contract-transition", "routes", 1, 2),
                    ("contract-transition", "routes", 2, 3),
                    ("contract-transition", "surfaces", 1, 2),
                    ("contract-transition", "ui_states", 1, 2),
                },
            )
            self.assertNotIn(
                ("contract-transition", "other_contract", 1, 2),
                allowed,
            )


if __name__ == "__main__":
    unittest.main()
