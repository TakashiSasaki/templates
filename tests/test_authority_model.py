from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_MODEL = ROOT / "docs" / "authority-model.md"
COEXISTENCE = ROOT / "docs" / "policy-composition-coexistence.md"


def normalized_prose(text: str) -> str:
    return " ".join(text.split())


class AuthorityModelTests(unittest.TestCase):
    def test_site_role_and_provider_independence_are_consistent(self) -> None:
        model = AUTHORITY_MODEL.read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        publishing = (ROOT / "PUBLISHING.md").read_text(encoding="utf-8")

        normalized_model = normalized_prose(model)
        normalized_readme = normalized_prose(readme)
        normalized_publishing = normalized_prose(publishing)

        required = "Site is the repository integration and publication authority"
        self.assertIn(required, normalized_model)
        self.assertIn(
            "repository integration and publication authority",
            normalized_readme.lower(),
        )
        self.assertIn(
            "repository integration and publication authority",
            normalized_publishing.lower(),
        )

        self.assertIn("not a parent, override, or super-authority", normalized_model)
        self.assertIn(
            "provider-specific semantics remain owned by their provider",
            normalized_model.lower(),
        )
        self.assertIn(
            "must not become a third umbrella management plane",
            normalized_model,
        )
        self.assertIn("site is not a parent or super-authority", normalized_readme.lower())

    def test_semantic_roles_do_not_infer_normativity_from_format(self) -> None:
        model = AUTHORITY_MODEL.read_text(encoding="utf-8")
        normalized_model = normalized_prose(model)

        for heading in (
            "### Normative authority",
            "### Normative requirement",
            "### Guidance",
            "### Evidence",
            "### Projection",
            "### Example",
            "### Explanation",
        ):
            self.assertIn(heading, model)

        self.assertIn(
            "determined by its owning authority and declared function, not by file format",
            normalized_model,
        )
        self.assertIn(
            "Guidance may cause a conformance failure only when the same rule is separately defined by the owning authority as a normative requirement",
            normalized_model,
        )
        self.assertIn("`SHOULD` must not be reduced to a casual recommendation", model)
        self.assertIn("Advisory material should avoid capitalized RFC keywords", model)

    def test_machine_discovery_reaches_authority_model_directly(self) -> None:
        agent = json.loads((ROOT / "agent.json").read_text(encoding="utf-8"))
        catalog = json.loads(
            (ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8")
        )
        coexistence = COEXISTENCE.read_text(encoding="utf-8")
        model = AUTHORITY_MODEL.read_text(encoding="utf-8")

        site = agent["authorities"]["site"]
        self.assertEqual(site["role"], "publication-integration")
        self.assertIs(site["consumer_repository_mutation"], False)

        authority_model = agent["integration_contracts"]["authority_model"]
        self.assertEqual(authority_model["owner"], "site")
        self.assertEqual(authority_model["repository_path"], "docs/authority-model.md")
        self.assertTrue((ROOT / authority_model["repository_path"]).is_file())

        coexistence_contract = agent["integration_contracts"][
            "policy_composition_coexistence"
        ]
        self.assertEqual(coexistence_contract["owner"], "site")
        self.assertEqual(
            coexistence_contract["document_id"],
            "site:policy-composition-coexistence",
        )

        document_id = coexistence_contract["document_id"].split(":", 1)[1]
        catalog_by_id = {entry["id"]: entry for entry in catalog["documents"]}
        self.assertEqual(
            catalog_by_id[document_id]["source"],
            "docs/policy-composition-coexistence.md",
        )
        self.assertIn("docs/authority-model.md", coexistence)
        self.assertIn(
            "agent.json\n  -> integration_contracts.authority_model",
            model,
        )

    def test_coexistence_contract_remains_provider_specific(self) -> None:
        coexistence = COEXISTENCE.read_text(encoding="utf-8")

        self.assertIn(
            "This coexistence contract applies that model to the Policy–Composition boundary",
            coexistence,
        )
        self.assertIn(
            "It does not become the authority for Policy or Composition semantics",
            coexistence,
        )
        self.assertIn(
            "does not perform consumer adoption, composition, update, render, recovery, or migration",
            coexistence,
        )


if __name__ == "__main__":
    unittest.main()
