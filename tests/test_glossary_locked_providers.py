from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.glossary import integrate_glossaries


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "TakashiSasaki/templates"
PROVIDER_ORDER = ("composition", "policy")
REQUIRED_PROVIDER_BY_TERM_ID = {
    "external-git-branch": "site",
    "templates-publication-catalog": "site",
    "templates-provider-branch": "site",
    "templates-integrated-publication": "site",
    "templates-publication-source-lock": "site",
    "templates-index-guided-navigation": "site",
    "templates-composition-component": "composition",
    "templates-composition-artifact-component": "composition",
    "templates-composition-capability-component": "composition",
    "templates-composition-lifecycle-component": "composition",
    "templates-composition-recipe": "composition",
    "templates-composition-lock": "composition",
    "templates-composition-material-ownership": "composition",
    "templates-composition-component-owner": "composition",
    "templates-composition-ownership-mode": "composition",
    "templates-composition-managed-material": "composition",
    "templates-composition-seed-material": "composition",
    "templates-composition-generated-material": "composition",
    "templates-skill-profile": "composition",
    "templates-skill-template-scaffold": "composition",
    "templates-implementation-runtime": "composition",
    "templates-runtime-decision-record": "composition",
    "templates-contract-manifest": "composition",
    "templates-implementation-evidence": "composition",
    "templates-release-evidence": "composition",
    "templates-release-bundle": "composition",
    "external-mcp-model-context-protocol": "composition",
    "templates-policy-module": "policy",
    "templates-policy-profile": "policy",
    "templates-policy-context": "policy",
    "templates-policy-renderer": "policy",
    "templates-shared-policy": "policy",
    "templates-context-policy": "policy",
    "templates-repository-local-policy": "policy",
    "templates-artifact-contract": "policy",
}
RETIRED_IDS = {
    "templates-skill-mcp-extension",
    "templates-skill-runtime-decision-record",
    "templates-skill-public-interface-selection-contract",
    "templates-webapp-template-source-artifact",
    "templates-webapp-template-distribution-artifact",
    "templates-webapp-implementation-evidence",
    "templates-webapp-release-evidence",
    "templates-webapp-release-bundle",
}


class LockedProviderGlossaryTests(unittest.TestCase):
    def test_checked_out_provider_glossaries_integrate_end_to_end(self) -> None:
        providers = {
            "site": ROOT,
            **{
                name: ROOT.parent / f"{name}-source"
                for name in PROVIDER_ORDER
            },
        }
        missing = [name for name, path in providers.items() if not path.is_dir()]
        if missing:
            self.skipTest(
                "provider checkouts are not available outside the Pages CI layout: "
                + ", ".join(missing)
            )

        # PR5 intentionally stores composition glossary YAML as strict JSON, a
        # YAML 1.2 subset. This test exercises those exact bytes through the
        # Site's PyYAML loader instead of merely reparsing them with json.loads.
        composition_glossary = providers["composition"] / "docs" / "glossary.yml"
        self.assertTrue(
            composition_glossary.read_text(encoding="utf-8").lstrip().startswith("{")
        )

        locks = json.loads(
            (ROOT / "publication-sources.json").read_text(encoding="utf-8")
        )["publications"]
        self.assertEqual(set(locks), set(PROVIDER_ORDER))
        revisions = {
            "site": "0" * 40,
            **{name: locks[name]["revision"] for name in PROVIDER_ORDER},
        }

        integrated = integrate_glossaries(providers, revisions, REPOSITORY)
        terms = integrated["terms"]
        by_id = {term["id"]: term for term in terms}
        self.assertEqual(len(by_id), len(terms))
        self.assertTrue(set(REQUIRED_PROVIDER_BY_TERM_ID) <= set(by_id))
        self.assertFalse(RETIRED_IDS & set(by_id))

        for term_id, provider in REQUIRED_PROVIDER_BY_TERM_ID.items():
            with self.subTest(term_id=term_id):
                term = by_id[term_id]
                self.assertEqual(term["provider"], provider)
                self.assertEqual(term["source_path"], "docs/glossary.yml")
                self.assertEqual(term["source_revision"], revisions[provider])

        self.assertEqual(
            by_id["templates-provider-branch"]["localized_labels"]["ja"]["term"],
            "プロバイダーブランチ",
        )
        self.assertEqual(
            by_id["templates-skill-profile"]["localized_labels"]["ja"]["term"],
            "スキルプロファイル",
        )

        ownership = by_id["templates-composition-material-ownership"]
        self.assertEqual(ownership["provider"], "composition")
        self.assertEqual(
            ownership["localized_labels"]["ja"]["term"],
            "マテリアル所有権",
        )
        self.assertNotIn("File ownership", ownership.get("aliases", []))

        implementation_runtime = by_id["templates-implementation-runtime"]
        self.assertEqual(implementation_runtime["provider"], "composition")
        self.assertEqual(implementation_runtime["term"], "Implementation runtime")
        self.assertEqual(
            implementation_runtime["localized_labels"]["ja"]["term"],
            "実装ランタイム",
        )
        self.assertNotIn("Runtime", implementation_runtime.get("aliases", []))

        runtime_record = by_id["templates-runtime-decision-record"]
        self.assertEqual(runtime_record["term"], "Implementation runtime decision record")
        self.assertIn("Runtime decision record", runtime_record["aliases"])
        self.assertIn(
            "templates-implementation-runtime", runtime_record["related_terms"]
        )

        mcp = by_id["external-mcp-model-context-protocol"]
        self.assertEqual(mcp["provider"], "composition")
        self.assertEqual(mcp["origin"], "external")
        self.assertEqual(mcp["aliases"], ["MCP"])
        self.assertEqual(mcp["authority"]["kind"], "normative")
        self.assertEqual(
            mcp["authority"]["sources"][0]["version"],
            "2026-07-28",
        )

        skill_profile = by_id["templates-skill-profile"]
        policy_profile = by_id["templates-policy-profile"]
        self.assertIn("templates-policy-profile", skill_profile["related_terms"])
        self.assertIn("templates-skill-profile", policy_profile["related_terms"])
        self.assertNotEqual(skill_profile["provider"], policy_profile["provider"])


if __name__ == "__main__":
    unittest.main()
