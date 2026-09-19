import hashlib
import json
from pathlib import Path
import re
import unittest
import jsonschema

from scripts.verify_maintainer_source import (
    CANONICAL_REVISION,
    CANONICAL_RULE_BLOB,
    CANONICAL_RULE_PATH,
    CANONICAL_PLANNER_BLOB,
    CANONICAL_PLANNER_PATH,
    CANONICAL_SKILL_BLOB,
    CANONICAL_SKILL_PATH,
    git_blob_sha,
    verify_source_reference,
)


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_REVISION = "9c2c538d5ee0b866379db40e5c24b29d60e155ba"
GENERATION_TOOLCHAIN_REVISION = "6d281bd17b2304eb867adbc812a0a6d041e1c9c8"
CANONICAL_SKILL_PATH = "repository-skills/land-templates-stack/SKILL.md"
CANONICAL_SKILL_BLOB = "06efa38681e374636bcabcbcb984be5ec43b47ee"
CANONICAL_RULE_PATH = "repository-policy/stacked-pr-landing.md"
CANONICAL_RULE_BLOB = "9761cdbcd21b0e8ba2f3eb2ffb306725a82f5eef"
CANONICAL_PLANNER_PATH = "repository-skills/land-templates-stack/scripts/plan_review_scope.py"
CANONICAL_PLANNER_BLOB = "16c0907a19e3f8d339fe81e29f7b204e791fc781"


class MaintainerOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.guide = (ROOT / "docs/maintainer-onboarding.md").read_text(encoding="utf-8")
        self.automation = (ROOT / "docs/publication-automation.md").read_text(encoding="utf-8")
        self.guide_flat = " ".join(self.guide.split())
        self.automation_flat = " ".join(self.automation.split())

    def test_site_entrypoint_preserves_consumer_route_and_adds_maintainer_route(self):
        self.assertIn("Five independent authorities", self.readme)
        self.assertIn("**Modeling**", self.readme)
        self.assertIn("Maintain this repository", self.readme)
        self.assertIn("maintainer-onboarding.md", self.readme)
        self.assertIn("A first-time application author normally starts", self.readme)
        self.assertIn("A new Integration release alone is not Site-adoption authorization", self.readme)

    def test_guide_maps_all_authorities_sources_checks_and_boundaries(self):
        for authority in ("Modeling", "Composition", "Policy", "Integration", "Site"):
            with self.subTest(authority=authority):
                self.assertIn(f"| {authority} |", self.guide)
        for required in (
            "branch name",
            "full SHA",
            "separate checkout",
            "records/",
            "generated/",
            ".agent-policy.yml",
            "publication-sources.json",
            "integration-source.json",
            "Policy Work-ledger",
            "Stack PRs only within one authority",
            "current capability",
            "selected input",
            "actually deployed",
            "unknown",
            "does not mean deployed",
            "Landing route for maintenance pull requests",
            ".agents/skills/land-templates-stack/SKILL.md",
            CANONICAL_REVISION,
            CANONICAL_RULE_BLOB,
            CANONICAL_SKILL_BLOB,
            CANONICAL_PLANNER_PATH,
            CANONICAL_PLANNER_BLOB,
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.guide_flat)

    def test_publication_runbook_and_guide_cover_current_event_chain(self):
        for workflow in (
            "modeling-ci.yml",
            "reference-consumer-publication.yml",
            "integration-compatibility.yml",
            "provider-publication-dispatch.yml",
            "integration-reconcile.yml",
            "integration-promotion-notify.yml",
            "publication-reconcile.yml",
            "site-publication-notify.yml",
            "deploy-pages.yml",
        ):
            with self.subTest(workflow=workflow):
                self.assertIn(workflow, self.guide)
        for event in (
            "publication.provider-qualified",
            "publication.integration-promoted",
            "automation/publication-*",
            "automation/site-publication-*",
            "automatic=true",
            "automatic=false",
        ):
            with self.subTest(event=event):
                self.assertIn(event, self.guide_flat)
        for distinction in (
            "notification carries a candidate fact",
            "auto-merge",
            "required review",
            "actual merge",
            "deployment",
            "kill switch",
            "mode change does not replay",
        ):
            with self.subTest(distinction=distinction):
                self.assertIn(distinction, self.guide_flat)
                self.assertIn(distinction, self.automation_flat)

    def test_branch_local_and_generated_routes_are_present(self):
        for path in (
            "docs/maintainer-onboarding.md",
            "docs/publication-automation.md",
            "MAINTENANCE.md",
            "PUBLISHING.md",
            "policy/project.md",
            ".agents/skills/site-publication-cutover/SKILL.md",
            ".agents/skills/land-templates-stack/SKILL.md",
            ".agents/skills/land-templates-stack/source.json",
        ):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
        for path in ("README.md", "MAINTENANCE.md", "PUBLISHING.md", "policy/project.md"):
            with self.subTest(path=path):
                self.assertIn("docs/publication-automation.md", (ROOT / path).read_text(encoding="utf-8"))
        for required in ("docs/maintainer-onboarding.md", "docs/publication-automation.md"):
            with self.subTest(required=required):
                self.assertIn(required, (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(".agents/skills/land-templates-stack/SKILL.md", agents)
        self.assertIn(CANONICAL_REVISION, agents)
        catalog = json.loads((ROOT / "docs/publication-catalog.json").read_text(encoding="utf-8"))
        catalog_sources = {entry["source"] for entry in catalog["documents"]}
        self.assertIn("docs/maintainer-onboarding.md", catalog_sources)
        self.assertIn("docs/publication-automation.md", catalog_sources)

    def test_machine_projection_labels_current_and_historical_contracts(self):
        agent = json.loads((ROOT / "agent.json").read_text(encoding="utf-8"))
        self.assertEqual(
            agent["maintainer_entrypoint"],
            {
                "repository": "TakashiSasaki/templates",
                "branch": "site",
                "path": "docs/maintainer-onboarding.md",
            },
        )
        integration = agent["authorities"]["integration"]
        self.assertEqual(integration["contract"], "Integrated Publication Bundle v4")
        self.assertIn("Integrated Publication Bundle v3", integration["historical_compatibility"])
        self.assertEqual(agent["publication_state"]["selected_input"], "integration-source.json")
        self.assertIn("Pages artifact", agent["publication_state"]["deployed_evidence"])

    def test_machine_maintainer_entrypoint_matches_schema_and_source(self):
        agent = json.loads((ROOT / "agent.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "schemas/agent-bootstrap.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(agent, schema)
        entrypoint = agent["maintainer_entrypoint"]
        self.assertEqual(entrypoint["repository"], "TakashiSasaki/templates")
        self.assertEqual(entrypoint["branch"], "site")
        self.assertEqual(entrypoint["path"], "docs/maintainer-onboarding.md")
        self.assertTrue((ROOT / entrypoint["path"]).is_file())

    def test_site_maintainer_landing_source_is_immutable_and_separate(self):
        source = json.loads(
            (ROOT / ".agents/skills/land-templates-stack/source.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(source["kind"], "repository-maintainer-skill-reference")
        self.assertEqual(source["schema_version"], 2)
        self.assertRegex(source["revision"], r"^[0-9a-f]{40}$")
        self.assertRegex(source["blob_sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(source["revision"], CANONICAL_REVISION)
        self.assertEqual(source["repository"], "TakashiSasaki/templates")
        self.assertEqual(source["path"], CANONICAL_SKILL_PATH)
        self.assertEqual(
            source["closure"],
            [
                {"path": CANONICAL_RULE_PATH, "blob_sha": CANONICAL_RULE_BLOB},
                {"path": CANONICAL_PLANNER_PATH, "blob_sha": CANONICAL_PLANNER_BLOB},
            ],
        )
        skill = (ROOT / ".agents/skills/land-templates-stack/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("same immutable snapshot", skill)
        self.assertIn("does not authorize", skill)
        self.assertNotIn("CI_DISCOVERY_MIN_OBSERVATION_MINUTES", skill)

        project = (ROOT / "policy/project.md").read_text(encoding="utf-8")
        for required in (
            "Adaptive Site review scope",
            "source-ready preflight",
            "fixed Bundle",
            "browser/PWA/cache lifecycle",
            "Independent review remains required",
        ):
            with self.subTest(required=required):
                self.assertIn(required, project)

    def test_finalized_adoption_inventory_matches_policy_projection(self):
        adoption = json.loads(
            (ROOT / ".agent-policy/adoption.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            adoption["toolchain"],
            {
                "repository": "TakashiSasaki/templates",
                "revision": GENERATION_TOOLCHAIN_REVISION,
            },
        )
        agents_entry = next(
            entry for entry in adoption["sources"] if entry["path"] == "AGENTS.md"
        )
        self.assertTrue(agents_entry["generated"])
        self.assertEqual(
            agents_entry["sha256"],
            hashlib.sha256((ROOT / "AGENTS.md").read_bytes()).hexdigest(),
        )
        self.assertTrue(adoption["sources"])
        for entry in adoption["sources"]:
            with self.subTest(source=entry["path"]):
                path = ROOT / entry["path"]
                self.assertTrue(path.is_file())
                self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertIs(type(entry["generated"]), bool)
                self.assertEqual(entry["generated"], entry["path"] == "AGENTS.md")

    def test_coexistence_languages_separate_maintenance_and_generation(self):
        for relative in (
            "docs/policy-composition-coexistence.md",
            "translations/ja/docs/policy-composition-coexistence.md",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(f"| Policy maintenance procedure | `{CANONICAL_REVISION}` |", text)
            self.assertIn(
                f"| Policy generation toolchain | `{GENERATION_TOOLCHAIN_REVISION}` |", text
            )
            self.assertNotIn("| Policy consumer |", text)

    def test_source_reference_rejects_invalid_and_mismatched_fixtures(self):
        skill = b"canonical landing skill fixture"
        rule = b"canonical maintenance rule fixture"
        source = {
            "schema_version": 2,
            "kind": "repository-maintainer-skill-reference",
            "repository": "TakashiSasaki/templates",
            "revision": "a" * 40,
            "path": CANONICAL_SKILL_PATH,
            "blob_sha": git_blob_sha(skill),
            "closure": [
                {"path": CANONICAL_RULE_PATH, "blob_sha": git_blob_sha(rule)},
                {"path": CANONICAL_PLANNER_PATH, "blob_sha": git_blob_sha(b"planner")},
            ],
        }
        files = {
            (source["repository"], source["revision"], CANONICAL_SKILL_PATH): skill,
            (source["repository"], source["revision"], CANONICAL_RULE_PATH): rule,
            (source["repository"], source["revision"], CANONICAL_PLANNER_PATH): b"planner",
        }

        def fixture_fetch(repository, revision, path):
            return files[(repository, revision, path)]

        fixture_rule_blob = git_blob_sha(rule)
        verified = verify_source_reference(
            source,
            fixture_fetch,
            expected_rule_blob=fixture_rule_blob,
            expected_planner_blob=git_blob_sha(b"planner"),
        )
        self.assertEqual(verified["skill_blob"], source["blob_sha"])
        self.assertEqual(verified["rule_blob"], fixture_rule_blob)
        self.assertEqual(verified["planner_blob"], git_blob_sha(b"planner"))

        malformed = dict(source, revision="policy")
        with self.assertRaisesRegex(ValueError, "immutable full SHA"):
            verify_source_reference(malformed, fixture_fetch, expected_rule_blob=fixture_rule_blob)

        mismatch = dict(source, blob_sha="b" * 40)
        with self.assertRaisesRegex(ValueError, "Skill blob mismatch"):
            verify_source_reference(mismatch, fixture_fetch, expected_rule_blob=fixture_rule_blob)

        missing_path = dict(source, path="repository-policy/missing.md")
        with self.assertRaisesRegex(ValueError, "canonical Skill path"):
            verify_source_reference(
                missing_path, fixture_fetch, expected_rule_blob=fixture_rule_blob
            )

        files.pop((source["repository"], source["revision"], CANONICAL_RULE_PATH))
        with self.assertRaises(KeyError):
            verify_source_reference(
                source, fixture_fetch, expected_rule_blob=fixture_rule_blob
            )

        files[(source["repository"], source["revision"], CANONICAL_RULE_PATH)] = b"tampered"
        with self.assertRaisesRegex(ValueError, "rule blob mismatch"):
            verify_source_reference(
                source,
                fixture_fetch,
                expected_rule_blob=fixture_rule_blob,
                expected_planner_blob=git_blob_sha(b"planner"),
            )

        files[(source["repository"], source["revision"], CANONICAL_RULE_PATH)] = rule
        files.pop((source["repository"], source["revision"], CANONICAL_PLANNER_PATH))
        with self.assertRaises(KeyError):
            verify_source_reference(
                source,
                fixture_fetch,
                expected_rule_blob=fixture_rule_blob,
                expected_planner_blob=git_blob_sha(b"planner"),
            )

    def test_clean_room_route_matrix_has_required_columns_and_all_scenarios(self):
        lines = self.guide.splitlines()
        header_index = next(
            index for index, line in enumerate(lines)
            if line.startswith("| Scenario | Semantic owner and authority branch |")
        )
        header = lines[header_index]
        for column in (
            "Semantic owner and authority branch",
            "First document and skill",
            "Editable source versus generated material",
            "Cheapest useful validation, PR base, and cross-authority dependency",
            "Stop, next safe action, and authorization",
        ):
            self.assertIn(column, header)
        rows = []
        for line in lines[header_index + 2:]:
            if not line.startswith("|"):
                break
            rows.append(line)
        self.assertEqual(len(rows), 10)
        required_scenarios = (
            "Register or revise an information-model record",
            "Change a Composition schema, component, or recipe",
            "Change a generic Policy maintenance or review procedure",
            "Make a Site-only CSS or presentation fix",
            "Diagnose a provider change that merged but is not visible on the published Web site",
            "Diagnose a successful shadow qualification",
            "Handle an auto-publication lock PR waiting for review",
            "Resume interrupted work from an existing PR or checkpoint",
            "Handle an expired artifact or active publication kill switch",
            "Explain why Site may still select an older Integration Bundle while Integration has newer capability",
        )
        for scenario in required_scenarios:
            with self.subTest(scenario=scenario):
                self.assertTrue(any(row.startswith(f"| {scenario} |") for row in rows))

    def test_live_state_retrieval_is_tool_neutral(self):
        self.assertIn("authenticated GitHub read surface", self.guide)
        self.assertIn("connector/API or `gh`", self.guide)
        self.assertIn("`gh` example, not a repository-specific tool requirement", self.guide)
        self.assertIn("branch", self.guide)
        self.assertIn("full 40-character `HEAD`", self.guide)
        self.assertIn("git status --short --branch", self.guide)

    def test_cross_authority_routes_are_branch_qualified(self):
        remote_links = re.findall(
            r"https://github\.com/TakashiSasaki/templates/blob/([^/]+)/([^ )]+)",
            self.guide,
        )
        self.assertGreaterEqual(len(remote_links), 10)
        allowed_branches = {"modeling", "composition", "policy", "integration", "site"}
        for branch, path in remote_links:
            self.assertIn(branch, allowed_branches)
            self.assertTrue(path)
        relative_links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", self.guide)
        for relative_authority in ("../modeling", "../composition", "../policy", "../integration"):
            self.assertFalse(any(target.startswith(relative_authority) for target in relative_links))


if __name__ == "__main__":
    unittest.main()
