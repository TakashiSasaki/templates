from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
CATALOG = ROOT / "catalog" / "catalog.json"
RECIPES = ROOT / "recipes"
COMPONENTS = ROOT / "components"


def config(recipe: str) -> dict:
    return {
        "schema_version": 1,
        "recipe": recipe,
        "components": {"include": [], "exclude": []},
        "parameters": {},
    }


class PolicyCompositionCoexistenceTests(unittest.TestCase):
    def run_composer(
        self,
        command: str,
        *,
        target: Path,
        config_path: Path | None = None,
        mode: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        arguments = [sys.executable, str(COMPOSER), command]
        if mode is not None:
            arguments.extend(["--mode", mode])
        if config_path is not None:
            arguments.extend(["--config", str(config_path)])
        arguments.extend(["--target", str(target)])
        result = subprocess.run(
            arguments,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"composer did not emit JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return result, payload

    def write_config(self, root: Path, recipe: str) -> Path:
        path = root / "composition.json"
        path.write_text(json.dumps(config(recipe), indent=2) + "\n", encoding="utf-8")
        return path

    def write_policy_state(self, target: Path) -> dict[str, bytes]:
        state = {
            ".agent-policy.yml": b"schema_version: 2\n# policy-owned config\n",
            ".agent-policy.lock": b"lock_version: 1\n# policy-owned lock\n",
            ".agent-policy/adoption.json": b'{"owner":"policy"}\n',
        }
        for relative, data in state.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return state

    def assert_policy_state_unchanged(self, target: Path, state: dict[str, bytes]) -> None:
        for relative, data in state.items():
            with self.subTest(relative=relative):
                self.assertEqual((target / relative).read_bytes(), data)

    def test_production_graph_does_not_model_policy_adoption_as_composition(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertNotIn("capability.agent-policy", catalog["components"])

        for component_id in catalog["components"]:
            descriptor = json.loads(
                (COMPONENTS / component_id / "component.json").read_text(encoding="utf-8")
            )
            self.assertNotEqual(descriptor["id"], "capability.agent-policy")
            self.assertNotIn("capability.agent-policy", descriptor["requires"])
            self.assertNotIn("capability.agent-policy", descriptor["conflicts"])

        for recipe_id in catalog["recipes"]:
            recipe = json.loads((RECIPES / f"{recipe_id}.json").read_text(encoding="utf-8"))
            exposed = {
                recipe["artifact"],
                *recipe["required_components"],
                *recipe["default_components"],
                *recipe["optional_components"],
            }
            self.assertNotIn("capability.agent-policy", exposed)

    def test_initial_composition_preserves_existing_policy_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            target.mkdir()
            policy_state = self.write_policy_state(target)
            config_path = self.write_config(root, "webapp")

            result, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["status"], "applied")
            self.assert_policy_state_unchanged(target, policy_state)
            lock = json.loads(
                (target / ".template-composition/lock.json").read_text(encoding="utf-8")
            )
            destinations = {entry["destination"] for entry in lock["files"]}
            self.assertTrue(destinations)
            self.assertFalse(
                any(
                    destination.casefold() == ".agent-policy"
                    or destination.casefold().startswith(".agent-policy/")
                    or destination.casefold() in {".agent-policy.yml", ".agent-policy.lock"}
                    for destination in destinations
                )
            )

    def test_update_preserves_policy_metadata_and_policy_rewritten_skill_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config_path = self.write_config(root, "skill")

            initial, _ = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

            agents = target / "AGENTS.md"
            policy_agents = b"# Policy-generated repository instructions\n\nconsumer handoff bytes\n"
            agents.write_bytes(policy_agents)
            policy_state = self.write_policy_state(target)

            planned, plan = self.run_composer("plan", target=target, mode="update")
            self.assertEqual(planned.returncode, 0, planned.stderr)
            preserved = {
                entry["destination"] for entry in plan["files"]["preserve"]
            }
            self.assertIn("AGENTS.md", preserved)

            applied, payload = self.run_composer("apply", target=target, mode="update")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(payload["status"], "updated")
            self.assertEqual(agents.read_bytes(), policy_agents)
            self.assert_policy_state_unchanged(target, policy_state)

            valid, validation = self.run_composer("validate", target=target)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertEqual(validation["status"], "valid")

    def test_reverse_handoff_conflict_preserves_policy_state_and_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            target.mkdir()
            policy_state = self.write_policy_state(target)
            agents = target / "AGENTS.md"
            original_agents = b"# Existing Policy-generated AGENTS\n"
            agents.write_bytes(original_agents)
            config_path = self.write_config(root, "skill")

            result, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["status"], "conflict")
            self.assertTrue(
                any(
                    conflict.startswith("AGENTS.md:")
                    and "different bytes" in conflict
                    for conflict in payload["conflicts"]
                )
            )
            self.assertEqual(agents.read_bytes(), original_agents)
            self.assert_policy_state_unchanged(target, policy_state)
            self.assertFalse((target / ".template-composition/lock.json").exists())

    def test_consumer_validator_rejects_lock_claiming_policy_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            config_path = self.write_config(root, "skill")
            applied, _ = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)

            policy_state = self.write_policy_state(target)
            lock_path = target / ".template-composition/lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            entry = next(item for item in lock["files"] if item["destination"] == "AGENTS.md")
            entry["destination"] = ".AGENT-POLICY.LOCK"
            lock["files"] = sorted(lock["files"], key=lambda item: item["destination"])
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

            validator = target / ".template-composition/validate_composition.py"
            result = subprocess.run(
                [sys.executable, str(validator), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("reserved provider metadata", result.stderr)
            self.assert_policy_state_unchanged(target, policy_state)


if __name__ == "__main__":
    unittest.main()
