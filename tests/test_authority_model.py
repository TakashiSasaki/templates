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
    def test_site_role_and_provider_independence_are_consistent(self):
        model=normalized_prose(AUTHORITY_MODEL.read_text())
        for authority in ('Composition','Policy','Integration','Site'):
            self.assertIn('| '+authority+' |',AUTHORITY_MODEL.read_text())
        self.assertIn('Reviewed provider selection',model)
        self.assertIn('Presentation, browser runtime',model)
        self.assertIn('It has no independent provider publication lock',model)
        for file in ('README.md','PUBLISHING.md'):
            self.assertIn('integration-source.json',(ROOT/file).read_text())
        self.assertIn('independent authorities and Git histories',model)

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

    def test_machine_discovery_reaches_authority_model_directly(self):
        agent=json.loads((ROOT/'agent.json').read_text())
        self.assertEqual(set(agent['authorities']),{'composition','policy','integration','site'})
        self.assertEqual(agent['authorities']['site']['role'],'presentation-runtime-deployment')
        self.assertEqual(agent['integration_contracts']['authority_model']['owner'],'integration')
        self.assertEqual(agent['integration_contracts']['authority_model']['canonical_repository_path'],'authority.json')
        self.assertTrue(agent['integration_contracts']['authority_model']['human_projection'].endswith('/maintain/site/authority-model/'))
        self.assertEqual(agent['integration_source'],{'lock':'integration-source.json'})

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
