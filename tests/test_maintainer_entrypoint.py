import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REVISION = "e9303fa4e7e2468e032985cc053b71ab6a6ca0d5"
CANONICAL_SKILL_BLOB = "06efa38681e374636bcabcbcb984be5ec43b47ee"
RULE_BLOB = "9761cdbcd21b0e8ba2f3eb2ffb306725a82f5eef"
PLANNER_BLOB = "91cb2617bfed51f69449c3c3b214ec3c33646983"
SHARED_GATE_REVISION = "412c525478d23ca889a649daf51b6261f6746ef3"
SHARED_GATE_BLOB = "2ef890673600f0f4c30b53cef7c19a78d34cf5bc"


class MaintainerEntrypointTests(unittest.TestCase):
    def test_integration_route_exposes_owner_sources_and_boundary(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        release = (ROOT / "RELEASE.md").read_text(encoding="utf-8")
        for required in (
            "Maintain the Integration authority in `templates`",
            "publication-sources.json",
            "Bundle artifacts, receipts",
            "run_integration_preflight.py fast",
            "ready",
            "providers",
            "exact full-SHA",
            "Site adoption",
            "Pages deployment",
            "Work ledger",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)
        self.assertIn("Maintainer routing and operational handoff", release)
        self.assertIn("release alone is not Site-adoption authorization", release)

    def test_maintenance_skill_is_thin_and_has_required_contract_sections(self):
        path = ROOT / ".agents/skills/integration-publication-maintenance/SKILL.md"
        skill = " ".join(path.read_text(encoding="utf-8").split())
        for heading in (
            "## Purpose",
            "## Use when",
            "## Do not use when",
            "## Canonical authorities",
            "## Inputs",
            "## Stop conditions",
            "## Evidence to report",
        ):
            self.assertIn(heading, skill)
        self.assertIn("publication-automation.md", skill)
        self.assertIn("unknown`, not `false`", skill)
        self.assertIn("does not define a new publication policy", skill)

    def test_authority_machine_projection_separates_capability_and_live_authorization(self):
        authority = json.loads((ROOT / "authority.json").read_text(encoding="utf-8"))
        self.assertEqual(authority["output_contract"], "Integrated Publication Bundle v4")
        self.assertIn("Integrated Publication Bundle v3", authority["historical_output_contracts"])
        adoption = authority["automatic_site_adoption"]
        self.assertEqual(adoption["default_mode"], "shadow")
        self.assertTrue(adoption["authorization_required"])
        self.assertEqual(
            adoption["live_state"],
            "external-repository-variables-credentials-protection-rules",
        )

    def test_maintainer_landing_and_gate_routes_are_immutable_and_separate(self):
        source = json.loads(
            (ROOT / ".agents/skills/land-templates-stack/source.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(source["kind"], "repository-maintainer-skill-reference")
        self.assertEqual(source["schema_version"], 2)
        self.assertEqual(source["repository"], "TakashiSasaki/templates")
        self.assertEqual(source["revision"], CANONICAL_REVISION)
        self.assertEqual(source["blob_sha"], CANONICAL_SKILL_BLOB)
        self.assertEqual(
            source["closure"],
            [
                {"path": "repository-policy/stacked-pr-landing.md", "blob_sha": RULE_BLOB},
                {
                    "path": "repository-skills/land-templates-stack/scripts/plan_review_scope.py",
                    "blob_sha": PLANNER_BLOB,
                },
            ],
        )
        self.assertEqual(source["path"], "repository-skills/land-templates-stack/SKILL.md")
        gate = json.loads(
            (ROOT / ".agents/skills/pr-merge-gate/source.json").read_text(encoding="utf-8")
        )
        self.assertEqual(gate["kind"], "policy-adapter-reference")
        self.assertEqual(gate["repository"], "TakashiSasaki/templates")
        self.assertEqual(gate["revision"], SHARED_GATE_REVISION)
        self.assertEqual(gate["path"], "skills/pr-merge-gate/SKILL.md")
        self.assertEqual(gate["blob_sha"], SHARED_GATE_BLOB)
        landing = (ROOT / ".agents/skills/land-templates-stack/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("same immutable snapshot", landing)
        self.assertIn("authorize merge", landing)
        self.assertNotIn("CI_DISCOVERY_MIN_OBSERVATION_MINUTES", landing)

    def test_integration_review_route_separates_tuple_qualification_and_expands(self):
        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        skill = " ".join(
            (ROOT / ".agents/skills/integration-publication-maintenance/SKILL.md")
            .read_text(encoding="utf-8")
            .split()
        )
        for required in (
            "immutable Policy planner",
            "exact provider tuple",
            "Bundle contract",
            "independent exact-head delta review",
            "trusted-controller",
            "Provider-source review and tuple qualification remain separate",
        ):
            with self.subTest(required=required):
                self.assertIn(required, instructions + " " + skill)
        self.assertNotIn("Request one cumulative review per logical stack", instructions)
        self.assertNotIn("targeted evidence whose bindings changed", instructions)


if __name__ == "__main__":
    unittest.main()
