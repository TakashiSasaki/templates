from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "examples/evaluations/evaluation-scorecard.schema.json"
GUIDE = ROOT / "examples/evaluations/evaluation-scorecard.txt"


class EvaluationScorecardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.text = GUIDE.read_text(encoding="utf-8")

    def payload(
        self,
        *,
        lifecycle_status: str = "PASS",
        applicable: bool = True,
        staged: bool = False,
        transcript_completeness: str = "complete",
    ) -> dict:
        score = {"status": "PASS", "attribution": "repository defect", "notes": "controlled"}
        environment = {
            "model": "test-model",
            "fresh_conversation": True,
            "outside_maintainer_workspace": True,
            "inherited_instructions_recorded": True,
            "available_tools": ["github"],
            "git_availability": "available",
            "browser_availability": "available",
            "network_restrictions": "none",
            "user_intervention_count": 0,
            "transcript_completeness": transcript_completeness,
        }
        dimensions = {
            key: dict(score)
            for key in self.schema["properties"]["dimensions"]["required"]
        }
        dimensions["lifecycle_correctness"]["status"] = lifecycle_status
        chronology = {
            "checkpoint_lifecycle_applicable": applicable,
            "planning_checkpoint_preceded_product_coding": True if applicable else None,
            "product_checkpoint_preceded_release_readiness": True if applicable else None,
            "planning_boundary_evidence": "planning checkpoint observed before first product mutation",
            "product_boundary_evidence": "product checkpoint observed before readiness evaluation",
        }
        if staged:
            staged_chronology = {
                "applicable": True,
                "change_event_id": "change-1",
                "disclosure_order": 20,
                "prerequisite_product_checkpoint_id": "product-1",
                "added_requirement_ids": ["REQ-CHANGE-ONE"],
                "product_checkpoint_preceded_change_event": True,
                "future_requirement_visible_before_event": False,
                "first_post_change_mutation_order": 24,
                "change_event_preceded_first_post_change_mutation": True,
                "post_change_planning_checkpoint_id": "planning-2",
                "post_change_planning_checkpoint_preceded_first_mutation": True,
                "post_change_product_checkpoint_id": "product-2",
                "post_change_evidence_preceded_product_checkpoint": True,
                "disclosure_evidence": "event 20 disclosed REQ-CHANGE-ONE after product-1",
                "first_post_change_mutation_evidence": "event 24 was the first changed product mutation",
                "visibility_evidence": "the requirement was created only after product-1",
                "post_change_checkpoint_evidence": "planning-2 preceded mutation and product-2 followed evidence",
            }
        else:
            staged_chronology = {
                "applicable": False,
                "change_event_id": None,
                "disclosure_order": None,
                "prerequisite_product_checkpoint_id": None,
                "added_requirement_ids": [],
                "product_checkpoint_preceded_change_event": None,
                "future_requirement_visible_before_event": None,
                "first_post_change_mutation_order": None,
                "change_event_preceded_first_post_change_mutation": None,
                "post_change_planning_checkpoint_id": None,
                "post_change_planning_checkpoint_preceded_first_mutation": None,
                "post_change_product_checkpoint_id": None,
                "post_change_evidence_preceded_product_checkpoint": None,
                "disclosure_evidence": "staged disclosure not exercised",
                "first_post_change_mutation_evidence": "staged disclosure not exercised",
                "visibility_evidence": "staged disclosure not exercised",
                "post_change_checkpoint_evidence": "staged disclosure not exercised",
            }
        return {
            "schema_version": 3,
            "evaluation_id": "test",
            "environment_fingerprint": environment,
            "dimensions": dimensions,
            "lifecycle_chronology": chronology,
            "staged_change_chronology": staged_chronology,
            "next_clean_room_rerun_conditions": ["fresh independent conversation"],
        }

    def test_schema_contains_fixed_statuses_attributions_and_dimensions(self) -> None:
        score = self.schema["$defs"]["score"]
        self.assertEqual(
            score["properties"]["status"]["enum"],
            ["PASS", "FAIL", "BLOCKED", "NOT TESTED"],
        )
        self.assertEqual(
            score["properties"]["attribution"]["enum"],
            [
                "repository defect",
                "documentation/discoverability defect",
                "machine-contract defect",
                "evaluation-methodology defect",
                "evaluator mistake",
                "environment limitation",
                "evidence-capture limitation",
            ],
        )
        dimensions = self.schema["properties"]["dimensions"]
        self.assertEqual(len(dimensions["required"]), 13)
        self.assertEqual(set(dimensions["required"]), set(dimensions["properties"]))
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 3)
        self.assertIn("lifecycle_chronology", self.schema["required"])
        self.assertIn("staged_change_chronology", self.schema["required"])
        self.assertEqual(self.schema["properties"]["next_clean_room_rerun_conditions"]["minItems"], 1)

    def test_guide_covers_requested_dimensions_environment_and_chronology(self) -> None:
        for phrase in (
            "Entry-point discovery",
            "Machine bootstrap discovery",
            "Canonical bootstrap execution",
            "Integrity verification",
            "Installer / Skill / toolchain role separation",
            "Lifecycle correctness",
            "Managed/generated boundary",
            "Product evidence completion",
            "Browser proof handling",
            "Release-readiness honesty",
            "Recovery quality",
            "User intervention",
            "Dead ends",
            "fresh conversation",
            "complete transcript capture",
            "planning_checkpoint_preceded_product_coding",
            "product_checkpoint_preceded_release_readiness",
            "does not retroactively make the planning boundary pass",
            "Staged requirement-change chronology",
            "future_requirement_visible_before_event",
            "evaluation-methodology defect",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_valid_scorecard_instance_and_invalid_common_shapes(self) -> None:
        payload = self.payload()
        validator = Draft202012Validator(self.schema)
        validator.validate(payload)
        invalid_cases = (
            ("invalid status", lambda value: value["dimensions"]["dead_ends"].__setitem__("status", "UNKNOWN")),
            ("invalid attribution", lambda value: value["dimensions"]["dead_ends"].__setitem__("attribution", "unknown attribution")),
            ("invalid transcript completeness", lambda value: value["environment_fingerprint"].__setitem__("transcript_completeness", "other")),
            ("negative intervention count", lambda value: value["environment_fingerprint"].__setitem__("user_intervention_count", -1)),
            ("empty rerun conditions", lambda value: value.__setitem__("next_clean_room_rerun_conditions", [])),
            ("empty model", lambda value: value["environment_fingerprint"].__setitem__("model", "")),
            ("empty rerun condition", lambda value: value.__setitem__("next_clean_room_rerun_conditions", [""])),
            ("extra root property", lambda value: value.__setitem__("unexpected", True)),
            ("extra score property", lambda value: value["dimensions"]["dead_ends"].__setitem__("unexpected", True)),
            ("missing chronology", lambda value: value.pop("lifecycle_chronology")),
            ("missing staged chronology", lambda value: value.pop("staged_change_chronology")),
            ("empty planning evidence", lambda value: value["lifecycle_chronology"].__setitem__("planning_boundary_evidence", "")),
        )
        for name, mutate in invalid_cases:
            with self.subTest(case=name):
                invalid = json.loads(json.dumps(payload))
                mutate(invalid)
                with self.assertRaises(ValidationError):
                    validator.validate(invalid)

    def test_lifecycle_pass_requires_both_checkpoint_boundaries_in_order(self) -> None:
        validator = Draft202012Validator(self.schema)
        for field in (
            "planning_checkpoint_preceded_product_coding",
            "product_checkpoint_preceded_release_readiness",
        ):
            with self.subTest(field=field):
                payload = self.payload(lifecycle_status="PASS", applicable=True)
                payload["lifecycle_chronology"][field] = False
                with self.assertRaises(ValidationError):
                    validator.validate(payload)

        failed = self.payload(lifecycle_status="FAIL", applicable=True)
        failed["lifecycle_chronology"]["planning_checkpoint_preceded_product_coding"] = False
        validator.validate(failed)

    def test_applicable_checkpoint_lifecycle_allows_unknown_when_not_tested(self) -> None:
        validator = Draft202012Validator(self.schema)
        payload = self.payload(
            lifecycle_status="NOT TESTED",
            applicable=True,
            transcript_completeness="unavailable",
        )
        payload["lifecycle_chronology"]["planning_checkpoint_preceded_product_coding"] = None
        payload["lifecycle_chronology"]["product_checkpoint_preceded_release_readiness"] = None
        validator.validate(payload)

        payload["dimensions"]["lifecycle_correctness"]["status"] = "PASS"
        with self.assertRaises(ValidationError):
            validator.validate(payload)

    def test_non_applicable_checkpoint_lifecycle_requires_null_chronology_flags(self) -> None:
        validator = Draft202012Validator(self.schema)
        payload = self.payload(applicable=False)
        validator.validate(payload)
        for field in (
            "planning_checkpoint_preceded_product_coding",
            "product_checkpoint_preceded_release_readiness",
        ):
            with self.subTest(field=field):
                invalid = self.payload(applicable=False)
                invalid["lifecycle_chronology"][field] = True
                with self.assertRaises(ValidationError):
                    validator.validate(invalid)

    def test_staged_change_pass_requires_true_chronology_and_no_early_visibility(self) -> None:
        validator = Draft202012Validator(self.schema)
        validator.validate(self.payload(staged=True))
        invalid_fields = (
            ("product_checkpoint_preceded_change_event", False),
            ("future_requirement_visible_before_event", True),
            ("change_event_preceded_first_post_change_mutation", False),
            ("post_change_planning_checkpoint_preceded_first_mutation", False),
            ("post_change_evidence_preceded_product_checkpoint", False),
        )
        for field, bad_value in invalid_fields:
            with self.subTest(field=field):
                payload = self.payload(staged=True)
                payload["staged_change_chronology"][field] = bad_value
                with self.assertRaises(ValidationError):
                    validator.validate(payload)

    def test_staged_change_event_identity_required_even_when_lifecycle_fails(self) -> None:
        validator = Draft202012Validator(self.schema)
        payload = self.payload(lifecycle_status="FAIL", staged=True)
        payload["staged_change_chronology"]["change_event_id"] = None
        with self.assertRaises(ValidationError):
            validator.validate(payload)

        payload = self.payload(lifecycle_status="FAIL", staged=True)
        payload["staged_change_chronology"]["added_requirement_ids"] = []
        with self.assertRaises(ValidationError):
            validator.validate(payload)

    def test_transcript_unavailable_can_record_staged_chronology_as_unknown(self) -> None:
        validator = Draft202012Validator(self.schema)
        payload = self.payload(
            lifecycle_status="NOT TESTED",
            staged=True,
            transcript_completeness="unavailable",
        )
        for field in (
            "disclosure_order",
            "prerequisite_product_checkpoint_id",
            "product_checkpoint_preceded_change_event",
            "future_requirement_visible_before_event",
            "first_post_change_mutation_order",
            "change_event_preceded_first_post_change_mutation",
            "post_change_planning_checkpoint_id",
            "post_change_planning_checkpoint_preceded_first_mutation",
            "post_change_product_checkpoint_id",
            "post_change_evidence_preceded_product_checkpoint",
        ):
            payload["staged_change_chronology"][field] = None
        payload["lifecycle_chronology"]["planning_checkpoint_preceded_product_coding"] = None
        payload["lifecycle_chronology"]["product_checkpoint_preceded_release_readiness"] = None
        validator.validate(payload)

        payload["dimensions"]["lifecycle_correctness"]["status"] = "PASS"
        with self.assertRaises(ValidationError):
            validator.validate(payload)

    def test_non_applicable_staged_change_requires_null_facts_and_empty_requirements(self) -> None:
        validator = Draft202012Validator(self.schema)
        validator.validate(self.payload(staged=False))

        invalid = self.payload(staged=False)
        invalid["staged_change_chronology"]["change_event_id"] = "change-1"
        with self.assertRaises(ValidationError):
            validator.validate(invalid)

        invalid = self.payload(staged=False)
        invalid["staged_change_chronology"]["added_requirement_ids"] = ["REQ-CHANGE-ONE"]
        with self.assertRaises(ValidationError):
            validator.validate(invalid)

    def test_guide_preserves_clean_room_boundary(self) -> None:
        self.assertIn("future clean-room run", self.text)
        self.assertIn("this maintenance conversation is not an eligible evaluator", self.text)
        self.assertIn("Do not convert BLOCKED or NOT TESTED into PASS", self.text)
        self.assertIn("not later filesystem state", self.text)
        self.assertIn("must not be committed in the evaluation repository", self.text)


if __name__ == "__main__":
    unittest.main()
