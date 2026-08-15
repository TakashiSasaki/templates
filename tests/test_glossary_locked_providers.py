from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.glossary import integrate_glossaries


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "TakashiSasaki/templates"
PROVIDER_ORDER = ("skill", "policy", "webapp")
REQUIRED_CANONICAL_TERM_IDS = {
    "external-git-branch",
    "templates-publication-catalog",
    "templates-provider-branch",
    "templates-integrated-publication",
    "templates-publication-source-lock",
    "templates-skill-profile",
    "templates-skill-template-scaffold",
    "templates-skill-mcp-extension",
    "templates-skill-runtime-decision-record",
    "templates-skill-public-interface-selection-contract",
    "templates-policy-module",
    "templates-policy-profile",
    "templates-policy-context",
    "templates-policy-renderer",
    "templates-shared-policy",
    "templates-context-policy",
    "templates-repository-local-policy",
    "templates-artifact-contract",
    "templates-adapter-renderer-requirement",
    "templates-explanatory-material",
    "templates-policy-override",
    "templates-webapp-template-mode",
    "templates-webapp-contract-manifest",
    "templates-webapp-implementation-evidence",
    "templates-webapp-release-evidence",
    "templates-webapp-template-source-artifact",
    "templates-webapp-template-distribution-artifact",
    "templates-webapp-product-repository-artifact",
    "templates-webapp-product-mode",
    "templates-webapp-release-bundle",
    "templates-webapp-contract-family",
}
FIRST_EXPANSION_PROVIDER_BY_ID = {
    "templates-integrated-publication": "site",
    "templates-publication-source-lock": "site",
    "templates-skill-runtime-decision-record": "skill",
    "templates-skill-public-interface-selection-contract": "skill",
    "templates-shared-policy": "policy",
    "templates-context-policy": "policy",
    "templates-repository-local-policy": "policy",
    "templates-artifact-contract": "policy",
    "templates-adapter-renderer-requirement": "policy",
    "templates-explanatory-material": "policy",
    "templates-policy-override": "policy",
    "templates-webapp-template-source-artifact": "webapp",
    "templates-webapp-template-distribution-artifact": "webapp",
    "templates-webapp-product-repository-artifact": "webapp",
    "templates-webapp-product-mode": "webapp",
    "templates-webapp-release-bundle": "webapp",
    "templates-webapp-contract-family": "webapp",
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

        for term_id, provider in FIRST_EXPANSION_PROVIDER_BY_ID.items():
            with self.subTest(term_id=term_id, provider=provider):
                self.assertEqual(by_id[term_id]["provider"], provider)

        self.assertEqual(
            by_id["templates-provider-branch"]["localized_labels"]["ja"]["term"],
            "プロバイダーブランチ",
        )
        self.assertEqual(
            by_id["templates-integrated-publication"]["localized_labels"]["ja"]["term"],
            "統合公開",
        )
        self.assertEqual(
            by_id["templates-skill-runtime-decision-record"]["localized_labels"]["ja"]["term"],
            "ランタイム決定記録",
        )
        self.assertEqual(
            by_id["templates-context-policy"]["localized_labels"]["ja"]["term"],
            "コンテキストポリシー",
        )
        self.assertEqual(
            by_id["templates-webapp-product-mode"]["localized_labels"]["ja"]["term"],
            "プロダクトモード",
        )


if __name__ == "__main__":
    unittest.main()
