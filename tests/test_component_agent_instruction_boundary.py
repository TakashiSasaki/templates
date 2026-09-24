from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "components"
COMPONENT = COMPONENTS / "artifact.skill-core"
COMPOSER = ROOT / "scripts" / "compose.py"


class ComponentAgentInstructionBoundaryTests(unittest.TestCase):
    def test_components_scope_instructions_define_distribution_boundary(self) -> None:
        guidance = (COMPONENTS / "AGENTS.md").read_text(encoding="utf-8")
        for required in (
            "files/**",
            "AGENTS.md.template",
            '"destination": "AGENTS.md"',
            "not as repository-maintainer instructions",
            "component version",
        ):
            self.assertIn(required, guidance)

    def test_distributable_agents_material_has_non_discoverable_source_name(self) -> None:
        discoverable_materials = []
        for files_root in COMPONENTS.glob("*/files"):
            discoverable_materials.extend(files_root.rglob("AGENTS.md"))
        self.assertEqual(discoverable_materials, [])

        descriptor = json.loads((COMPONENT / "component.json").read_text(encoding="utf-8"))
        material = next(
            item for item in descriptor["materials"] if item["destination"] == "AGENTS.md"
        )
        self.assertEqual(
            material,
            {
                "source": "files/AGENTS.md.template",
                "destination": "AGENTS.md",
                "ownership": "seed",
            },
        )
        self.assertTrue((COMPONENT / material["source"]).is_file())

    def test_skill_materialization_still_writes_root_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "composition.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "recipe": "skill",
                        "components": {"include": [], "exclude": []},
                        "parameters": {},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            target = root / "consumer"
            result = subprocess.run(
                [
                    sys.executable,
                    str(COMPOSER),
                    "apply",
                    "--config",
                    str(config),
                    "--target",
                    str(target),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                (target / "AGENTS.md").read_bytes(),
                (COMPONENT / "files" / "AGENTS.md.template").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
