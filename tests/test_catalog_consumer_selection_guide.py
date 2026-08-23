from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APPLICATION_CAPABILITIES = {
    "capability.cli",
    "capability.mcp",
    "capability.mcp-apps",
    "capability.runtime",
    "capability.service",
    "capability.web-interface",
}
SKILL_LIFECYCLE_OPTIONS = {
    "lifecycle.contract-evolution",
    "lifecycle.implementation-evidence",
    "lifecycle.release-bundle",
    "lifecycle.release-evidence",
    "lifecycle.release-execution",
}
WEBAPP_LIFECYCLE_OPTIONS = {"lifecycle.release-bundle"}
WEBAPP_BASELINE_LIFECYCLE = {
    "lifecycle.contract-evolution",
    "lifecycle.implementation-evidence",
}
RELEASE_LIFECYCLE_CLOSURE = {
    "lifecycle.contract-evolution",
    "lifecycle.implementation-evidence",
    "lifecycle.release-bundle",
    "lifecycle.release-evidence",
    "lifecycle.release-execution",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dependency_closure(*component_ids: str) -> set[str]:
    selected = set(component_ids)
    queue = list(component_ids)
    while queue:
        component_id = queue.pop()
        descriptor = load_json(
            ROOT / "components" / component_id / "component.json"
        )
        for dependency in descriptor["requires"]:
            if dependency not in selected:
                selected.add(dependency)
                queue.append(dependency)
    return selected


class CatalogConsumerSelectionGuideTests(unittest.TestCase):
    def test_consumer_selection_guide_is_discoverable(self) -> None:
        guide = (ROOT / "catalog" / "README.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")

        self.assertIn("## Consumer selection guide", guide)
        self.assertIn(
            "[Choosing a recipe and components](../catalog/README.md)",
            docs_index,
        )

    def test_recipe_exposure_matches_consumer_selection_model(self) -> None:
        skill = load_json(ROOT / "recipes" / "skill.json")
        webapp = load_json(ROOT / "recipes" / "webapp.json")

        self.assertEqual(skill["artifact"], "artifact.skill-core")
        self.assertEqual(
            set(skill["optional_components"]),
            APPLICATION_CAPABILITIES | SKILL_LIFECYCLE_OPTIONS,
        )
        self.assertEqual(webapp["artifact"], "artifact.webapp-core")
        self.assertEqual(
            set(webapp["optional_components"]),
            APPLICATION_CAPABILITIES | WEBAPP_LIFECYCLE_OPTIONS,
        )

    def test_machine_readable_dependency_closures_match_selection_contract(self) -> None:
        self.assertEqual(
            dependency_closure("artifact.skill-core"),
            {"artifact.skill-core", "lifecycle.composition-state"},
        )
        self.assertEqual(
            dependency_closure("artifact.skill-core", "capability.mcp-apps"),
            {
                "artifact.skill-core",
                "capability.mcp",
                "capability.mcp-apps",
                "capability.runtime",
                "lifecycle.composition-state",
            },
        )
        self.assertEqual(
            dependency_closure("artifact.skill-core", "lifecycle.release-bundle"),
            {
                "artifact.skill-core",
                "lifecycle.composition-state",
                *RELEASE_LIFECYCLE_CLOSURE,
            },
        )

        minimal_webapp = dependency_closure("artifact.webapp-core")
        self.assertEqual(
            minimal_webapp,
            {
                "artifact.webapp-core",
                "lifecycle.composition-state",
                *WEBAPP_BASELINE_LIFECYCLE,
            },
        )
        self.assertFalse(minimal_webapp & APPLICATION_CAPABILITIES)
        self.assertFalse(
            minimal_webapp
            & {
                "lifecycle.release-execution",
                "lifecycle.release-evidence",
                "lifecycle.release-bundle",
            }
        )

        runtime_webapp = dependency_closure(
            "artifact.webapp-core", "capability.runtime"
        )
        self.assertEqual(
            runtime_webapp,
            minimal_webapp | {"capability.runtime"},
        )

        release_webapp = dependency_closure(
            "artifact.webapp-core", "lifecycle.release-bundle"
        )
        self.assertEqual(
            release_webapp,
            {
                "artifact.webapp-core",
                "lifecycle.composition-state",
                *RELEASE_LIFECYCLE_CLOSURE,
            },
        )


if __name__ == "__main__":
    unittest.main()
