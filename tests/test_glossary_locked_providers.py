from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.glossary import integrate_glossaries


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "TakashiSasaki/templates"
PROVIDER_ORDER = ("skill", "policy", "webapp")
EXPECTED_TERM_IDS = {
    "external-git-branch",
    "templates-publication-catalog",
    "templates-provider-branch",
    "templates-skill-profile",
    "templates-skill-template-scaffold",
    "templates-skill-mcp-extension",
    "templates-policy-module",
    "templates-policy-profile",
    "templates-policy-context",
    "templates-policy-renderer",
    "templates-webapp-template-mode",
    "templates-webapp-contract-manifest",
    "templates-webapp-implementation-evidence",
    "templates-webapp-release-evidence",
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

        self.assertEqual(set(by_id), EXPECTED_TERM_IDS)
        self.assertEqual(len(terms), len(EXPECTED_TERM_IDS))

        for term_id, term in by_id.items():
            with self.subTest(term_id=term_id):
                provider = term["provider"]
                self.assertEqual(term["source_path"], "docs/glossary.yml")
                self.assertEqual(term["source_revision"], revisions[provider])

        self.assertEqual(by_id["templates-skill-profile"]["provider"], "skill")
        self.assertEqual(by_id["templates-policy-module"]["provider"], "policy")
        self.assertEqual(
            by_id["templates-webapp-template-mode"]["provider"],
            "webapp",
        )
        self.assertEqual(
            by_id["templates-provider-branch"]["localized_labels"]["ja"]["term"],
            "プロバイダーブランチ",
        )
        self.assertEqual(
            by_id["templates-policy-context"]["localized_labels"]["ja"]["term"],
            "ポリシーコンテキスト",
        )


if __name__ == "__main__":
    unittest.main()
