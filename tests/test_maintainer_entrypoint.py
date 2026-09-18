import json
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


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
        self.assertEqual(source["revision"], "5af977020fca701bcf6b7fb7ce12ca077b2d7220")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", source["blob_sha"]))
        observed = subprocess.check_output(
            ["git", "rev-parse", f"{source['revision']}:{source['path']}"],
            cwd=ROOT,
            text=True,
        ).strip()
        self.assertEqual(observed, source["blob_sha"])
        gate = json.loads(
            (ROOT / ".agents/skills/pr-merge-gate/source.json").read_text(encoding="utf-8")
        )
        self.assertEqual(gate["revision"], "733c86941f8154f301a225054d88c6b8a477058a")
        landing = (ROOT / ".agents/skills/land-templates-stack/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("same immutable snapshot", landing)
        self.assertIn("authorize merge", landing)
        self.assertNotIn("CI_DISCOVERY_MIN_OBSERVATION_MINUTES", landing)


if __name__ == "__main__":
    unittest.main()
