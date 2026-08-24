from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


class ConsumerReadmeEntrypointTests(unittest.TestCase):
    def test_task_entrypoint_precedes_maintainer_authority_details(self) -> None:
        readme = README.read_text(encoding="utf-8")
        start = readme.index("## Start here")
        repository_authority = readme.index("## Repository authority model")
        publication_model = readme.index("## Publication model")
        local_validation = readme.index("## Local publication validation")
        self.assertLess(start, repository_authority)
        self.assertLess(repository_authority, publication_model)
        self.assertLess(publication_model, local_validation)

    def test_start_here_routes_common_reader_tasks(self) -> None:
        readme = README.read_text(encoding="utf-8")
        start = readme.index("## Start here")
        end = readme.index("## Repository authority model")
        entrypoint = readme[start:end]
        for expected in (
            "Composition",
            "Policy",
            "Capabilities",
            "Lifecycle",
            "Skill",
            "Webapp",
            "Glossary",
            "Repository trees",
            "https://templates.moukaeritai.work/composition/",
            "https://templates.moukaeritai.work/policy/",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, entrypoint)
        self.assertIn(
            "You do not need to understand Site publication internals",
            entrypoint,
        )


if __name__ == "__main__":
    unittest.main()
