from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.glossary import integrate_glossaries


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "TakashiSasaki/templates"
PROVIDER_ORDER = ("skill", "policy", "webapp")
REQUIRED_PROVIDER_BY_TERM_ID = {
    "external-git-branch": "site",
    "templates-publication-catalog": "site",
    "templates-provider-branch": "site",
    "templates-integrated-publication": "site",
    "templates-publication-source-lock": "site",
    "templates-index-guided-navigation": "site",
    "templates-skill-profile": "skill",
    "templates-skill-template-scaffold": "skill",
    "templates-skill-mcp-extension": "skill",
    "templates-skill-runtime-decision-record": "skill",
    "templates-skill-public-interface-selection-contract": "skill",
    "templates-policy-module": "policy",
    "templates-policy-profile": "policy",
    "templates-policy-context": "policy",
    "templates-policy-renderer": "policy",
    "templates-shared-policy": "policy",
    "templates-context-policy": "policy",
    "templates-repository-local-policy": "policy",
    "templates-artifact-contract": "policy",
    "templates-adapter-renderer-requirement": "policy",
    "templates-explanatory-material": "policy",
    "templates-policy-override": "policy",
    "templates-webapp-template-mode": "webapp",
    "templates-webapp-contract-manifest": "webapp",
    "templates-webapp-implementation-evidence": "webapp",
    "templates-webapp-release-evidence": "webapp",
    "templates-webapp-template-source-artifact": "webapp",
    "templates-webapp-template-distribution-artifact": "webapp",
    "templates-webapp-product-repository-artifact": "webapp",
    "templates-webapp-product-mode": "webapp",
    "templates-webapp-release-bundle": "webapp",
    "templates-webapp-contract-family": "webapp",
}
REQUIRED_CANONICAL_TERM_IDS = set(REQUIRED_PROVIDER_BY_TERM_ID)
EXPECTED_JA_LABELS = {
    "templates-provider-branch": "プロバイダーブランチ",
    "templates-integrated-publication": "統合公開",
    "templates-skill-runtime-decision-record": "ランタイム決定記録",
    "templates-context-policy": "コンテキストポリシー",
    "templates-webapp-product-mode": "プロダクトモード",
}
EXPECTED_CROSS_PROVIDER_RELATED_TERMS = {
    "templates-skill-profile": {
        "templates-policy-profile",
    },
    "templates-policy-profile": {
        "templates-skill-profile",
    },
    "templates-skill-public-interface-selection-contract": {
        "templates-artifact-contract",
        "templates-adapter-renderer-requirement",
    },
    "templates-webapp-implementation-evidence": {
        "templates-artifact-contract",
    },
    "templates-webapp-release-evidence": {
        "templates-artifact-contract",
    },
    "templates-webapp-release-bundle": {
        "templates-artifact-contract",
    },
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
        missing = [
            name for name, path in providers.items()
            if not path.is_dir()
        ]
        if missing:
            self.skipTest(
                "provider checkouts are not available outside the Pages CI layout: "
                + ", ".join(missing)
            )

        locks = json.loads(
            (ROOT / "publication-sources.json").read_text(encoding="utf-8")
        )["publications"]
        revisions = {
            "site": "0" * 40,
            **{
                name: locks[name]["revision"]
                for name in PROVIDER_ORDER
            },
        }

        integrated = integrate_glossaries(providers, revisions, REPOSITORY)
        terms = integrated["terms"]
        by_id = {term["id"]: term for term in terms}

        self.assertEqual(len(by_id), len(terms))
        self.assertTrue(REQUIRED_CANONICAL_TERM_IDS <= set(by_id))

        for term_id, term in by_id.items():
            with self.subTest(term_id=term_id):
                provider = term["provider"]
                self.assertEqual(term["source_path"], "docs/glossary.yml")
                self.assertEqual(term["source_revision"], revisions[provider])

        for term_id, provider in REQUIRED_PROVIDER_BY_TERM_ID.items():
            with self.subTest(term_id=term_id, provider=provider):
                self.assertEqual(by_id[term_id]["provider"], provider)

        for term_id, expected_label in EXPECTED_JA_LABELS.items():
            with self.subTest(term_id=term_id, language="ja"):
                self.assertEqual(
                    by_id[term_id]["localized_labels"]["ja"]["term"],
                    expected_label,
                )

        for term_id, expected_related in EXPECTED_CROSS_PROVIDER_RELATED_TERMS.items():
            with self.subTest(term_id=term_id, relation_scope="cross-provider"):
                self.assertTrue(
                    expected_related <= set(by_id[term_id].get("related_terms", []))
                )
                for related_id in expected_related:
                    self.assertNotEqual(
                        by_id[term_id]["provider"],
                        by_id[related_id]["provider"],
                    )


if __name__ == "__main__":
    unittest.main()
